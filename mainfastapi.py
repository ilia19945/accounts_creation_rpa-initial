# import logging
# import sys
import json

import requests
import re
# import celery
# import json
import time
from datetime import datetime
import funcs as f
import fast_api_logging as fl
from tasks import send_gmail_message

from fastapi import Body, FastAPI, HTTPException, Query  # BackgroundTasks
from typing import Optional
from elasticapm.contrib.starlette import ElasticAPM

# run server: uvicorn mainfastapi:app --reload --port 80
# run ngrok: -> ngrok http 80
# if run through ngrok - don't forget to update uri and redirect urin in:
# jira webhook https://junehomes.atlassian.net/plugins/servlet/webhooks#
# google api - https://console.cloud.google.com/apis/credentials/oauthclient/675261997418-4pfe4aep6v3l3pl13lii6p8arsd4md3m.apps.googleusercontent.com?project=test-saml-accounts-creation
# google json
# to use celery on windows the gevent lib should be  installed https://stackoverflow.com/questions/62524908/task-receive-but-doesnt-excute
# because celery version +4.x  doesn't support windows
# run docker with redis
# to run celery with 3 queues type in terminal:
# celery -A tasks worker -E --loglevel=INFO -Q new_emps,terminations,other -P gevent
# more commands in tasks.py
# to use flower use command in terminal: celery -A tasks flower
# when finished need to finish the notion article
# https://www.notion.so/junehomes/Automatic-user-accounts-creation-82fe3380c2f749ef9d1b37a1e22abe7d


app = FastAPI()

# https://www.elastic.co/guide/en/apm/agent/python/current/starlette-support.html#starlette-fastapi
# app.add_middleware(ElasticAPM, client=fl.apm)
global jira_key
jira_key = ''

# triggers
# @app.get("/")
# async def simple_get():
#     return {"message": "Hello World"}
# print("jira_key: " + jira_key)
# fl.info("jira key: " + jira_key)

if __name__ == 'mainfastapi':

    fl.info('Fast API server has successfully started.')


    # # thanks atlassian for the "perfect" solution for mentions 🤦‍
    # suggested_email = 'Test@test.com'
    # f.send_jira_comment(message={
    #     "version": 1,
    #     "type": "doc",
    #     "content": [{
    #         "type": "paragraph",
    #         "content": [{
    #             "type": "mention",
    #             "attrs": {
    #                 "id": "60cb1687c90cb20068f6bd9e",
    #                 "text": "@Ilya Konovalov",
    #                 "accessLevel": ""
    #             }},
    #             {
    #                 "type": "text",
    #                 "text": " can you please add "},
    #             {
    #                 "type": "text",
    #                 "text": suggested_email,
    #                 "marks": [
    #                     {
    #                         "type": "link",
    #                         "attrs": {
    #                             "href": f"mailto:{suggested_email}"
    #                         }}]},
    #             {
    #                 "type": "text",
    #                 "text": " to:"
    #             }]},
    #         {
    #             "type": "orderedList",
    #             "content": [{
    #                 "type": "listItem",
    #                 "content": [{
    #                     "type": "paragraph",
    #                     "content": [{
    #                         "type": "text",
    #                         "text": "CI/CD",
    #                         "marks": [{
    #                             "type": "link",
    #                             "attrs": {"href": "https://ci.junehomes.net/role-strategy/assign-roles"}},
    #                             {"type": "strong"}]}]}]},
    #                 {
    #                     "type": "listItem",
    #                     "content": [{
    #                         "type": "paragraph",
    #                         "content": [{
    #                             "type": "text",
    #                             "text": "Gitlab",
    #                             "marks": [{
    #                                 "type": "link",
    #                                 "attrs": {"href": "https://gitlab.com/junehomes"}},
    #                                 {"type": "strong"}]}]}]}]}]},
    #     jira_key='AUS2-25')

    @app.get("/"
             # , name="Don't touch!! :P",
             # description='This method is a technical restriction of oAuth2.0 Google Authorization process.\n Never use it w/o a direct purpose'
             )
    async def redirect_from_google(code: Optional[str] = Query(None,
                                                               description='authorization code from google '
                                                                           'https://developers.google.com/identity/protocols/oauth2/web'
                                                                           '-serverexchange-authorization-code'),
                                   error: str = Query(None,
                                                      description='The error param google send us when the user denies to confirm authorization')
                                   ):
        if code and error:
            raise HTTPException(status_code=400, detail=f"Bad request. Parameters 'code'={code} and 'error'={error} can\'t be at the same query")

        elif code:
            if 60 < len(code) < 85:  # assuming that auth code from Google is about to 73-75 symbols
                fl.info('Received a request with code from google')
                file = open('authorization_codes.txt', 'a')
                file.write(str(time.asctime()) + ";" + code + '\n')  # add auth code to authorization_codes.txt
                file.close()

                # fl.info("Jira key: " + jira_key)
                fl.info(f"Jira key: {jira_key}")
                f.exchange_auth_code_to_access_refresh_token(code, jira_key)
                return {"event": "The authorization code has been caught and saved."
                                 f"Close this page and go back to jira ticket tab, please."
                        }
            else:
                fl.info(f'seems like a wrong value has been sent in the code parameter: {code}')
                return "Are you serious, bro? Is that really code from google?"
        elif error:
            fl.error('User denied to confirm the permissions!\nMain flow is stopped!')
            return 'User denied to confirm the permissions! Main flow is stopped!'
        else:
            fl.error('Received a random request')
            return 'Why are you on this page?=.='


    # webhook from jira
    @app.post("/webhook", status_code=200)
    async def main_flow(
            body: dict = Body(...)
    ):
        global jira_key
        jira_key = body['issue']['key']

        detect_change_type = body['changelog']['items'][0]['field']
        detect_action = body['changelog']['items'][0]['toString']
        fl.info(f"Change type: {detect_change_type}")
        if detect_change_type == 'status':

            jira_old_status = body['changelog']['items'][0]['fromString']
            jira_new_status = body['changelog']['items'][0]['toString']
            jira_description = re.split(': |\n', body['issue']['fields']['description'])
            fl.info(f"Key: {jira_key}")
            fl.info(f"Old Status: {jira_old_status}; New Status: {jira_new_status}")

            # print(jira_description)

            organizational_unit = jira_description[jira_description.index('*Organizational unit*') + 1]
            position_title = jira_description[jira_description.index('*Position title*') + 1]
            first_name = jira_description[jira_description.index('*First name*') + 1]
            last_name = jira_description[jira_description.index('*Last name*') + 1]
            if organizational_unit == 'Sales':
                last_name = last_name[0]
            personal_email = jira_description[jira_description.index('*Personal email*') + 1].split("|")[0][
                             0:(len(jira_description[jira_description.index('*Personal email*') + 1]))]
            #  avoid sending email address in "[name@junehomes.com|mailto:name@junehomes.com] - string"
            if personal_email[0:1] == '[':
                personal_email = personal_email[1:]
            elif personal_email == '':
                personal_email = jira_description[jira_description.index('h4. Personal email') + 1].split("|")[0]
                if personal_email[0:1] == '[':
                    personal_email = personal_email[1:]

            suggested_email = jira_description[jira_description.index('*Suggested name@junehomes.com*') + 1].split("|")[0]
            # avoid sending email address in "[name@junehomes.com|mailto:name@junehomes.com]" string format
            if suggested_email[0:1] == '[':
                suggested_email = suggested_email[1:]
            elif suggested_email == '':
                suggested_email = jira_description[jira_description.index(
                    '*Suggested name@junehomes.com*') + 1].split("|")[0]
                if suggested_email[0:1] == '[':
                    suggested_email = suggested_email[1:]

            personal_phone = jira_description[jira_description.index('*Personal phone number (with country code)*') + 1]
            supervisor_email = jira_description[jira_description.index('*Supervisor*') + 1]

            gmail_groups = jira_description[jira_description.index('*Gmail - which groups needs access to*') + 1].split(',')

            gmail_groups_refined = []
            for i in range(len(gmail_groups)):
                gmail_groups_refined.append(gmail_groups[i].strip())
            if 'team@junehomes.com' not in gmail_groups_refined:
                gmail_groups_refined.append('team@junehomes.com')
            gmail_groups_refined = [i for i in gmail_groups_refined if i]  # check for empty values like after last , ''
            # print(gmail_groups_refined)

            frontapp_role = jira_description[jira_description.index('*If needs FrontApp, select a user role*') + 1]
            hire_start_date = jira_description[jira_description.index('*Start date (IT needs 3 WORKING days to create accounts)*') + 1]
            unix_hire_start_date = datetime.strptime(hire_start_date, '%m/%d/%Y').timestamp()  # unix by the 00:00 AM
            user_email_analogy = jira_description[jira_description.index(
                '*If needs access to the telephony system, describe details (e.g. permissions and settings like which existing user?)*') + 1]

            if organizational_unit in ['Technology', 'Brand Marketing']:
                unix_hire_start_date += 28800
            else:
                unix_hire_start_date += 46800

            fl.info(f"The type of the date is now {str(unix_hire_start_date)}")
            unix_countdown_time = unix_hire_start_date - round(time.time())
            if unix_countdown_time <= 0:
                unix_countdown_time = 0

            fl.info(f"time for task countdown in hours: {str(unix_countdown_time / 3600)}")
            # print(f.password)

            # detect only the specific status change
            # creates a google account + assigns a google groups +
            # assigns a license depending on the orgunit
            # + creates a main google email + sends it policies + adds them as celery tasks.
            # + creates juneosDEV user if org_unit = IT and sends email as celery task
            if jira_old_status == "In Progress" and jira_new_status == "Create a google account":
                fl.info(f"Key: {jira_key}")
                fl.info(f"Correct event to create user Google account detected. Perform user creation attempt ...")
                fl.info(f"timestamp: {str(body['timestamp'])}")
                fl.info(f"webhookEvent: {body['webhookEvent']}")
                fl.info(f"user: {body['user']['accountId']}")
                try:
                    access_token = f.get_actual_token('access_token')
                    fl.debug(access_token)
                    expires_in = f.get_actual_token('expires_in')
                    fl.info(expires_in)
                    token_datetime = f.get_actual_token('datetime')
                    fl.info(token_datetime)
                except Exception as error:
                    return fl.error(error)
                fl.info(msg=f"Access_token: {access_token}\n"
                            f"datetime: {expires_in}"
                            f"first_name: {first_name}"
                            f"last_name: {last_name}"
                            f"personal_email: {personal_email}"
                            f"suggested_email: {suggested_email}"
                            f"organizational_unit: {organizational_unit}"
                            f"personal_phone:{personal_phone}"
                            f"gmail_groups (list): {str(gmail_groups_refined)}"
                            f"hire_start_date: {hire_start_date}"
                            f"Token lifetime: {str(int(str(time.time_ns())[0:10]) - int(expires_in))}"
                            f"token_datetime:{token_datetime}"
                        )
                if int(str(time.time_ns())[0:10]) - int(token_datetime) >= expires_in:  # token was refreshed more than 1h ago
                    fl.info('Access token expired! Try to get get_actual_token("refresh_token"):')

                    try:  # look for refresh token in .json file
                        refresh_token = f.get_actual_token('refresh_token')
                        fl.info(f"Refresh_token: {refresh_token}")

                    except KeyError:  # if there is no refresh token -> new app permission should be requested.

                        fl.info("Refresh token wasn't found.")
                        new_access_token = f.get_new_access_token()
                        fl.info(new_access_token)
                        jira_comment_response = f.send_jira_comment(
                            "*Access token expired!*\nNew access token should be requested before moving forward. "
                            "Press {color:red}*[Pass Google Authorization|" + new_access_token
                            + "]""*{color} button "
                              "and accept app permissions (if asked).\n"
                              "⚠ *REMEMBER: IT'S ONE TIME LINK! SHOULD BE DELETED AFTER REFRESHING* ⚠\n"
                              "(It's recommended to open in a new browser tab)\n",
                            jira_key)
                        if jira_comment_response[0] > 300:
                            fl.error(f"Jira comment wasn't added. {jira_comment_response[1]}")

                        fl.info("Jira comment was added successfully")

                    else:  # if refresh token was found in .json file
                        fl.info('Refresh token was provided by google. Refresh token_func() is executed \n')
                        f.refresh_token_func()
                        f.send_jira_comment("Current access_token expired. It was automatically refreshed. "
                                            "Please try to create google account for the user again.\n"
                                            "(Switch the ticket status -> \"In Progress\" -> \" Create a Google account\")", jira_key)

                else:

                    # add emails for tests here if needed.

                    fl.info('Access token is actual. Suggested user email will be checked to the uniqueness.')
                    url = f"https://admin.googleapis.com/admin/directory/v1/users/{suggested_email}"
                    payload = {}
                    headers = {
                        'Authorization': f'Bearer {f.get_actual_token("access_token")}'
                    }
                    # check if the user with this email already exists
                    check_for_user_existence = requests.get(url=url, headers=headers, data=payload)

                    if check_for_user_existence.status_code < 300:
                        """google response with 200 status which means that the account we're trying to create is already exists"""
                        print(f"The account ({suggested_email}) is already exist!")
                        f.send_jira_comment(f"The account ({suggested_email}) *is already exist*!\n"
                                            f"Check suggested email field and try again.", jira_key)
                    else:
                        """Suggested email is unique"""
                        google_user = f.create_google_user_req(first_name, last_name, suggested_email, organizational_unit)
                        if google_user[0] < 300:  # user created successfully
                            fl.info(f"User {first_name} {last_name} is created. Username: {suggested_email}\n")
                            f.send_jira_comment(f"(1/3) User *{first_name} {last_name}* is successfully created!\n"
                                                f"User Email: *{suggested_email}*\n", jira_key)

                            # proceeding to licence assignment according the department.

                            if organizational_unit == 'Sales':
                                assigned_license = f.assign_google_license('1010020020', suggested_email)

                                if assigned_license[0] < 300:  # if success
                                    f.send_jira_comment(
                                        "(2/3) *Google Workspace Enterprise Plus* license, successfully assigned!", jira_key)
                                    fl.info("Google Workspace Enterprise Plus license, assigned")

                                elif assigned_license[0] == 412:
                                    f.send_jira_comment(f"Not enough licenses. Google error:\n{assigned_license[1]}", jira_key)
                                    fl.error(f"Not enough licenses. Google error:\n{assigned_license[1]}")

                                else:  # if error
                                    f.send_jira_comment("An error appeared while assigning google license.\n"
                                                        f"Error code: {assigned_license[0]}\n"
                                                        f"Error message: {assigned_license[1]['error']['message']}", jira_key)

                                    fl.error(f"Error code: {assigned_license[0]}\n"
                                             f"Error message: {assigned_license[1]['error']['message']}")

                            # other department
                            else:
                                assigned_license = f.assign_google_license('Google-Apps-Unlimited', suggested_email)

                                if assigned_license[0] < 300:  # if success
                                    f.send_jira_comment("(2/3) G Suite Business license, successfully assigned!", jira_key)
                                    fl.info("G Suite Business license, assigned!")

                                elif assigned_license[0] == 412:
                                    f.send_jira_comment(f"Not enough licenses. Google error:\n{assigned_license[1]}", jira_key)
                                    fl.error(f"Not enough licenses. Google error:\n{assigned_license[1]}")

                                else:  # if error
                                    f.send_jira_comment("An error appeared while assigning google license.\n"
                                                        f"Error code: {assigned_license[0]}\n"
                                                        f"Error message: {assigned_license[1]['error']['message']}", jira_key)

                                    fl.error(f"Error code: {assigned_license[0]}\n"
                                             f"Error message: {assigned_license[1]['error']['message']}")

                            fl.info(f"gmail_groups to assign: {str(gmail_groups_refined)}")

                            # errors are inside the function
                            final_row = f.adding_user_to_google_group(gmail_groups_refined, suggested_email)

                            fl.info(f"Groups assigned: {final_row}")

                            f.send_jira_comment(f"(3/3) Assigned google groups:\n"
                                                f"{final_row}", jira_key)
                            # creating email template for sending later from gmail interface
                            # email templates are in \email_templates folder. need to update them there.

                            if organizational_unit == 'Technology':

                                # Ping Idelia to add the new IT emp to Gitlab and CI/CD
                                message = open("C:\PythonProjects\Fastapi\mention_idelia.txt", "r", encoding="UTF-8").read()
                                f.send_jira_comment(message=json.loads(message.replace('suggested_email', suggested_email)),
                                                    jira_key=jira_key)

                                # adding IT emp to calendar
                                calendar_id = 'junehomes.com_6f1l2kssibhmsg10e7fvnmdv1o@group.calendar.google.com'
                                adding_to_calendar_result = f.adding_to_junehomes_dev_calendar(suggested_email=suggested_email,
                                                                                               calendar_id=calendar_id)

                                if adding_to_calendar_result[0] < 300:  # user created successfully
                                    fl.info(f"User *{suggested_email}* is added to *[junehomes-dev calendar|]*.")
                                    f.send_jira_comment(f"User *{suggested_email}* is added to *[junehomes-dev "
                                                        f"calendar|https://calendar.google.com/calendar/u/0/r/settings/calendar"
                                                        f"/anVuZWhvbWVzLmNvbV82ZjFsMmtzc2liaG1zZzEwZTdmdm5tZHYxb0Bncm91cC5jYWxlbmRhci5nb29nbGUuY29t"
                                                        f"?pli=1]*.", jira_key)

                                else:
                                    f.send_jira_comment(
                                        f"An error occured while trying to add a User: *{suggested_email}* to *[junehomes-dev calendar|]*.\n"
                                        f"Error code: *{adding_to_calendar_result[0]}*\n"
                                        f"Error body: {adding_to_calendar_result[1]}")
                                    fl.info(f"An error occured while trying to add a User: *{suggested_email}* to *[junehomes-dev calendar|]*.\n"
                                            f"Error code: *{adding_to_calendar_result[0]}*\n"
                                            f"Error body: {adding_to_calendar_result[1]}")

                                adding_user_to_jira = f.adding_jira_cloud_user(suggested_email=suggested_email)

                                if adding_user_to_jira[0] < 300:
                                    fl.info(f"Jira user *{suggested_email}* is created.")
                                    f.send_jira_comment(f"Jira user *{suggested_email}* is created.", jira_key)

                                    # jira_account_id =adding_user_to_jira[1]['accountId']

                                    # when user is created - necessary groups are assigned automatically.
                                    # "name": "confluence-users","groupId": "8f022c21-2ba6-4242-ada9-45c7bf922ff9",

                                    # "name": "jira-software-users","groupId": "30e206a9-d09a-418f-90f5-5144c3ece85a",
                                     # try:
                                    #     group_confluence_users = f.adding_jira_user_to_group(account_id=jira_account_id,
                                    #                                                             group_id="8f022c21-2ba6-4242-ada9-45c7bf922ff9")
                                    #     group_jira_software_users = f.adding_jira_user_to_group(account_id=jira_account_id,
                                    #                                                             group_id="30e206a9-d09a-418f-90f5-5144c3ece85a")
                                    # except Exception as error:
                                    #     fl.info(f"An error occurred while trying to add to add Jira user *{suggested_email}* to a group.\n"
                                    #             f"Error: {error}")
                                    #     f.send_jira_comment(f"An error occurred while creating Jira user *{suggested_email}*  to a group.\n"
                                    #                         f"Error: {error}", jira_key)

                                else:
                                    fl.info(f"An error occurred while creating Jira user *{suggested_email}*.\n"
                                            f"Error code: {adding_user_to_jira[0]} \n"
                                            f"Error body: {adding_user_to_jira[1]}")
                                    f.send_jira_comment(f"An error occurred while creating Jira user *{suggested_email}*.\n"
                                                        f"Error code: {adding_user_to_jira[0]} \n"
                                                        f"Error body: {adding_user_to_jira[1]}", jira_key)

                            # create a template for email
                            with open("C:\PythonProjects\Fastapi\email_templates\google_mail.txt", "r") as data:
                                email_template = data.read()
                                username = email_template.replace('{username}', f'<b>{first_name}</b>')
                                final_draft = username.replace('{STRINGTOREPLACE}',
                                                               f'<p style="font-family:verdana">- username:  <b>{suggested_email}</b></p>\n\n'
                                                               f'<p style="font-family:verdana">- password:  <b>{f.password}</b></p>')
                                fl.info(final_draft)

                            send_gmail_message.apply_async(
                                ('ilya.konovalov@junehomes.com',
                                 [personal_email],
                                 ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com', supervisor_email],
                                 'June Homes: corporate email account',
                                 final_draft,
                                 round(unix_countdown_time / 3600)),
                                queue='new_emps',
                                countdown=round(unix_countdown_time))
                            fl.info(f'June Homes: corporate email account will be sent in {round((unix_countdown_time / 3600), 2)}')

                            # calculates the time before sending the email
                            # countdown=60
                            f.send_jira_comment(f"*June Homes: corporate email account* email will be sent to\n "
                                                f"User: *{personal_email}*\n"
                                                f"In: *{round((unix_countdown_time / 3600), 2)}* hours.\n", jira_key)

                            # at the end, when all services are created, an IT security policies email should be sent
                            if organizational_unit == 'Resident Experience':
                                with open("C:\PythonProjects\Fastapi\email_templates\it_services_and_policies_support.txt", "r") as data:
                                    final_draft = data.read()

                                # sends IT services and policies for member success
                                send_gmail_message.apply_async(
                                    ('ilya.konovalov@junehomes.com',
                                     [suggested_email],
                                     [],
                                     'IT services and policies',
                                     final_draft,
                                     round(unix_countdown_time / 3600)),
                                    queue='new_emps',
                                    countdown=(round(unix_countdown_time) + 300))
                                # calculates the time before sending the email
                                fl.info(f'June Homes: corporate email account will be sent in {round((unix_countdown_time / 3600), 2)}')

                            else:
                                with open("C:\PythonProjects\Fastapi\email_templates\it_services_and_policies_wo_trello_zendesk.txt", "r") as data:
                                    final_draft = data.read()

                                # sends it_services_and_policies_wo_trello_zendesk email to gmail
                                send_gmail_message(to=f"{suggested_email}",
                                                     sender='ilya.konovalov@junehomes.com',
                                                     cc='',
                                                     subject='IT services and policies',
                                                     message_text=final_draft)

                                send_gmail_message.apply_async(
                                    ('ilya.konovalov@junehomes.com',
                                     [suggested_email],
                                     [],
                                     'IT services and policies',
                                     final_draft,
                                     round(unix_countdown_time / 3600)),
                                    queue='new_emps',
                                    countdown=(round(unix_countdown_time) + 300))
                                # calculates the time before sending the email
                                fl.info(f"IT services and policies email will be sent in {round((unix_countdown_time + 300) / 3600, 2)} hours.")
                                # send event status as comment
                            f.send_jira_comment("Final is reached!\n"
                                                f"*IT services and policies* email will be sent in *{round((unix_countdown_time + 300) / 3600, 2)}* "
                                                "hours.",
                                                jira_key=jira_key)

                        # if the normal flow is violated
                        # error creating google user
                        else:
                            f.send_jira_comment("An error occurred while creating a google user!\n"
                                                f"Error code: {google_user[0]}\n"
                                                f"Error response: {google_user[1]}", jira_key)

            # creates an account on frontapp
            elif jira_new_status == "Create a FrontApp account":
                fl.info(f"Frontapp role: {frontapp_role}")

                # new roles should be added to the dict in future
                roles_dict = {
                    "Sales regular user": "tea_14r7o",
                    "Team member": "tea_14rd0",
                    "Success team lead": "tea_14res",
                    "Nutiliti Tiger Team": "tea_15c1w"
                }

                try:
                    fl.info(f"Frontapp role_id: {roles_dict[frontapp_role]}")
                    frontapp_user = f.create_frontapp_user(suggested_email=suggested_email,
                                                           first_name=first_name,
                                                           last_name=last_name,
                                                           frontapp_role=roles_dict[f"{frontapp_role}"])

                    fl.info(f'Status code: {str(frontapp_user[0])}')
                    fl.info(frontapp_user[1])

                    f.send_jira_comment(jira_key=jira_key,
                                        message='Frontapp User *successfully* created!\n'
                                                f'User email: *{suggested_email}*.\n'
                                                f'User Role: *{frontapp_role}*.')
                except KeyError:
                    fl.error("the role doesn't exist")
                    f.send_jira_comment(jira_key=jira_key, message=f'The role specified for a frontapp user: "{frontapp_role}" - *doesn\'t exist!*\n'
                                                                   f'The list of the roles:\n {roles_dict.keys()}')

            elif jira_new_status == "Create an Amazon account":
                fl.info(f'Analogy to create the User on Amazon: "{user_email_analogy}"')
                if user_email_analogy in ('', 'N/A ', ' ', '-'):
                    f.send_jira_comment('not a user email!',
                                        jira_key=jira_key)
                    fl.error(f'not a user email: "{user_email_analogy}"')
                else:
                    amazon_result = f.create_amazon_user(suggested_email=suggested_email,
                                                         first_name=first_name,
                                                         last_name=last_name,
                                                         user_email_analogy=user_email_analogy
                                                         )
                    if amazon_result is None:  # if no user was found
                        fl.error(f'No user with this email: {user_email_analogy}')
                        f.send_jira_comment(f'No user with this email: *{user_email_analogy}*.\n'
                                            f'Check the user email and try again.',
                                            jira_key=jira_key)

                    else:
                        try:
                            amazon_password = amazon_result[1]
                            fl.info(f"Amazon password: {amazon_password}")

                            f.send_jira_comment('*Amazon account* is created successfully!\n'
                                                f'An email with Amazon account credentials will be sent to *{suggested_email}*\n'
                                                f' In *{round(unix_countdown_time / 3600, 2)}* hours.',
                                                jira_key=jira_key)

                            fl.info(f'Amazon account for *{suggested_email}* is created.')

                            with open(r"C:\PythonProjects\Fastapi\email_templates\amazon_connect.txt", "r") as data:
                                email_template = data.read()
                                username = email_template.replace('{username}', f'<b>{first_name}</b>')
                                final_draft = username.replace('{STRINGTOREPLACE}',
                                                               f'<p style="font-family:verdana">- username:  <b>{suggested_email}</b></p>\n\n'
                                                               f'<p style="font-family:verdana">- password:  <b>{amazon_password}</b></p>')

                            # print(final_draft)
                            send_gmail_message.apply_async(
                                ('ilya.konovalov@junehomes.com',
                                 [suggested_email],
                                 ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com'],
                                 'Access to Amazon Connect call center',
                                 final_draft,
                                 round(unix_countdown_time / 3600)),
                                queue='new_emps',
                                countdown=round(unix_countdown_time))

                            fl.info(f'message was sent to celery. {round(unix_countdown_time / 3600)}')

                        except:

                            fl.error(amazon_result)

                            f.send_jira_comment('Error message:\n'
                                                f'*{amazon_result}*.',
                                                jira_key=jira_key)

            elif jira_new_status == 'Create a JuneOS account':

                fl.info(organizational_unit)

                if organizational_unit == 'Technology':
                    '''Группы добавлять вручную в json файле'''
                    '''Для Technology всегда ставится галка супер юзер вручную'''

                    try:
                        groups = f.get_juneos_groups_from_position_title(file_name='groups_technology.json')[position_title]
                    except Exception as error:
                        fl.error(error)
                        f.send_jira_comment(f'An error occurred while trying to search a user position:\n'
                                            f'*{error}* for *{organizational_unit}*.\n'
                                            f'Check if position exists in /permissions_by_orgunits/*groups_technology.json*'
                                            f' in and update json. Then try again.',
                                            jira_key=jira_key)
                        return KeyError(error)

                    juneos_user = f.create_juneos_user(first_name=first_name,
                                                       last_name=last_name,
                                                       suggested_email=suggested_email,
                                                       personal_phone=personal_phone,
                                                       dev_or_prod='dev',
                                                       )

                    if juneos_user[0] < 300:

                        fl.info('JuneOS user created!')
                        # send event status as comment
                        f.send_jira_comment("*JuneOS development* user created.\n"
                                            f"Username: *{suggested_email}*, \n"
                                            f"*[User link|https://dev.junehomes.net/december_access/users/user/{juneos_user[2]}/change/] "
                                            f"(Don't forget to make him a superuser on Dev.)*.\n"
                                            f"Credentials will be sent in: *{round(unix_countdown_time / 3600, 2)}* hours.",
                                            jira_key=jira_key)

                        with open("C:\PythonProjects\Fastapi\email_templates\juneos_dev.txt", "r") as data:
                            email_template = data.read()
                            username = email_template.replace('{username}', f'<b>{first_name}</b>')
                            final_draft = username.replace('{email}', f'<b>{suggested_email}</b>')

                        send_gmail_message.apply_async(
                            (
                                'ilya.konovalov@junehomes.com',
                                [suggested_email],
                                ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com'],
                                'Access to JuneOS.Development property management system',
                                final_draft,
                                round(unix_countdown_time / 3600)
                            ),
                            queue='new_emps',
                            countdown=round(unix_countdown_time)
                        )

                        fl.info(f"Tome to send: {str(round(unix_countdown_time / 3600))}")

                    else:

                        fl.error('An error occurred while creating a JuneOS.Development user.\n'
                                 f'Error code: *{juneos_user[0]}* \n\n'
                                 f'*{juneos_user[1]}*')
                        f.send_jira_comment('An error occurred while creating a JuneOS.Development user.\n'
                                            f'Error code: *{juneos_user[0]}* \n\n'
                                            f'*{juneos_user[1]}*',
                                            jira_key=jira_key)

                # other deps are not ready, due to not released update on prod
                elif organizational_unit == 'Sales':
                    fl.info('Sales, WIP')

                    try:
                        groups = f.get_juneos_groups_from_position_title(file_name='groups_sales.json')[position_title]
                        fl.info(f"the group was found! \n{str(groups)}")

                    except Exception as error:
                        fl.error(error)
                        f.send_jira_comment(f'An error occurred while trying to search a user position:\n'
                                            f'*{error}* for *{organizational_unit}*.\n'
                                            f'Check if position exists in /permissions_by_orgunits/*groups_sales.json*'
                                            f' in and update json. Then try again.',
                                            jira_key=jira_key)
                        return KeyError(error)

                    juneos_user = f.create_juneos_user(first_name=first_name,
                                                       last_name=last_name,
                                                       suggested_email=suggested_email,
                                                       personal_phone=personal_phone,
                                                       dev_or_prod='prod',
                                                       )

                    if juneos_user[0] < 300:
                        # send event status as comment
                        fl.info('user created sucessfully!')
                        with open("C:\PythonProjects\Fastapi\email_templates\juneos_prod.txt", "r") as data:
                            email_template = data.read()
                            username = email_template.replace('{username}', f'<b>{first_name}</b>')
                            final_draft = username.replace('{email}', f'<b>{suggested_email}</b>')

                        send_gmail_message.apply_async(
                            ('ilya.konovalov@junehomes.com',
                             [suggested_email],
                             ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com'],
                             'Access to JuneOS property management system',
                             final_draft,
                             round(unix_countdown_time / 3600)
                             ),
                            queue='new_emps',
                            countdown=round(unix_countdown_time)
                        )
                        fl.info(f"email 'Access to JuneOS property management system' will be sent in: {round(unix_countdown_time / 3600)}*, \n")
                        f.send_jira_comment("*JuneOS* user created.\n"
                                            f"Username: *{suggested_email}*, \n"
                                            f"*[User link|https://junehomes.com/december_access/users/user/{juneos_user[2]}/change/]*.\n"
                                            f"Credentials will be sent in: *{round(unix_countdown_time / 3600, 2)}* hours.",
                                            jira_key=jira_key)
                        try:
                            juneos_auth = f.juneOS_devprod_authorization(dev_or_prod='prod')
                        except Exception as error:
                            fl.error(error)

                        if juneos_auth[0] < 300:
                            statuscode = juneos_auth[0]
                            csrftoken = juneos_auth[1]
                            sessionid = juneos_auth[2]
                            token = juneos_auth[3]

                            juneos_user_id = juneos_user[2]

                            fl.info(f"successfully authenticated in JuneOS production: {str(statuscode)}")
                            fl.info('Trying to Assign groups')

                            try:
                                assigned_groups = f.assign_groups_to_user(user_id=juneos_user_id,
                                                                          groups=groups,
                                                                          dev_or_prod='prod',
                                                                          token=token,
                                                                          csrftoken=csrftoken,
                                                                          sessionid=sessionid
                                                                          )
                            except Exception as error:
                                fl.error(error)

                            if assigned_groups[0] < 300:
                                fl.info('groups assigned')
                                f.send_jira_comment('Groups in JuneOS are assigned to *[user|https://junehomes.com/december_access/'
                                                    f'users/user/{juneos_user_id}/change/]*.\n',
                                                    jira_key=jira_key)

                            else:

                                f.send_jira_comment('An error occurred while assigning groups to JuneOS user.\n'
                                                    f'Error code: *{assigned_groups[0]}* \n\n'
                                                    f'*{assigned_groups[1]}*',
                                                    jira_key=jira_key)

                                fl.error('An error occurred while assigning groups to JuneOS user.\n'
                                         f'Error code: *{assigned_groups[0]}* \n\n'
                                         f'*{assigned_groups[1]}')

                        else:
                            fl.error('An error occurred while trying to authenticate on JuneOS.\n'
                                     f'Error code: *{juneos_auth[0]}* \n\n'
                                     f'*{juneos_auth[1]}*')
                            f.send_jira_comment('An error occurred while trying to authenticate on JuneOS.\n'
                                                f'Error code: *{juneos_auth[0]}* \n\n'
                                                f'*{juneos_auth[1]}*',
                                                jira_key=jira_key)
                    else:
                        fl.error('An error occurred while creating a JuneOS user.\n'
                                 f'Error code: *{juneos_user[0]}* \n\n'
                                 f'*{juneos_user[1]}*')
                        f.send_jira_comment('An error occurred while creating a JuneOS user.\n'
                                            f'Error code: *{juneos_user[0]}* \n\n'
                                            f'*{juneos_user[1]}*',
                                            jira_key=jira_key)

                elif organizational_unit == 'Resident Experience':
                    fl.info('Got into Support, WIP section.')
                    try:
                        groups = f.get_juneos_groups_from_position_title(file_name='groups_resident_experience.json')[position_title]
                        fl.info(f"Group was found! \n{str(groups)}")
                    except Exception as error:
                        fl.error(error)
                        f.send_jira_comment(f'An error occurred while trying to search a user position:\n'
                                            f'*{error}* for *{organizational_unit}*.\n'
                                            f'Check if position exists in /permissions_by_orgunits/*groups_resident_experience.json*'
                                            f' in and update json. Then try again.',
                                            jira_key=jira_key)
                        return KeyError(error)

                    fl.info(msg="Trying to create a JuneOS user")

                    juneos_user = f.create_juneos_user(first_name=first_name,
                                                       last_name=last_name,
                                                       suggested_email=suggested_email,
                                                       personal_phone=personal_phone,
                                                       dev_or_prod='prod',  # change to prod when prod will be released
                                                       )

                    if juneos_user[0] < 300:
                        # send event status as comment

                        fl.info(f"*JuneOS* user created. Username: *{suggested_email}*, \n")

                        with open("C:\PythonProjects\Fastapi\email_templates\juneos_prod.txt", "r") as data:
                            email_template = data.read()
                            username = email_template.replace('{username}', f'<b>{first_name}</b>')
                            final_draft = username.replace('{email}', f'<b>{suggested_email}</b>')

                        send_gmail_message.apply_async(
                            ('ilya.konovalov@junehomes.com',
                             [suggested_email],
                             ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com'],
                             'Access to JuneOS property management system',
                             final_draft,
                             round(unix_countdown_time / 3600)
                             ),
                            queue='new_emps',
                            countdown=round(unix_countdown_time)
                        )

                        fl.info(f"email 'Access to JuneOS property management system' will be sent in: {round(unix_countdown_time / 3600)}*, \n")

                        f.send_jira_comment("*JuneOS* user created.\n"
                                            f"Username: *{suggested_email}*, \n"
                                            f"*[User link|https://junehomes.com/december_access/users/user/{juneos_user[2]}/change/]*.\n"
                                            f"Credentials will be sent in: *{round(unix_countdown_time / 3600, 2)}* hours.",
                                            jira_key=jira_key)

                        juneos_auth = f.juneOS_devprod_authorization(dev_or_prod='prod')
                        if juneos_auth[0] < 300:
                            statuscode = juneos_auth[0]
                            csrftoken = juneos_auth[1]
                            sessionid = juneos_auth[2]
                            token = juneos_auth[3]

                            juneos_user_id = juneos_user[2]

                            fl.info(f"successfully authenticated in JuneOS production: {str(statuscode)}")
                            fl.info("Trying to Assign groups")

                            assigned_groups = f.assign_groups_to_user(user_id=juneos_user_id,
                                                                      groups=groups,
                                                                      dev_or_prod='prod',
                                                                      token=token,
                                                                      csrftoken=csrftoken,
                                                                      sessionid=sessionid
                                                                      )

                            if assigned_groups[0] < 300:
                                fl.info('JuneOS groups have been assigned successfully')
                                f.send_jira_comment('Groups in JuneOS are assigned to *[user|https://junehomes.com/december_access/'
                                                    f'users/user/{juneos_user_id}/change/]*.\n',
                                                    jira_key=jira_key)

                            else:
                                fl.error('An error occurred while assigning groups to JuneOS user.\n'
                                         f'Error code: *{assigned_groups[0]}* \n\n'
                                         f'*{assigned_groups[1]}')
                                f.send_jira_comment('An error occurred while assigning groups to JuneOS user.\n'
                                                    f'Error code: *{assigned_groups[0]}* \n\n'
                                                    f'*{assigned_groups[1]}*',
                                                    jira_key=jira_key)

                        else:
                            fl.error('An error occurred while trying to authenticate on JuneOS.\n'
                                     f'Error code: *{juneos_auth[0]}* \n\n'
                                     f'*{juneos_auth[1]}*')
                            f.send_jira_comment('An error occurred while trying to authenticate on JuneOS.\n'
                                                f'Error code: *{juneos_auth[0]}* \n\n'
                                                f'*{juneos_auth[1]}*',
                                                jira_key=jira_key)
                    else:
                        fl.error('An error occurred while creating a JuneOS user.\n'
                                 f'Error code: *{juneos_user[0]}* \n\n'
                                 f'*{juneos_user[1]}*')
                        f.send_jira_comment('An error occurred while creating a JuneOS user.\n'
                                            f'Error code: *{juneos_user[0]}* \n\n'
                                            f'*{juneos_user[1]}*',
                                            jira_key=jira_key)

                elif organizational_unit == 'Performance Marketing':
                    print('Performance Marketing, WIP')

                    try:
                        groups = f.get_juneos_groups_from_position_title(file_name='groups_performance_marketing.json')[position_title]
                        print("Group was found! ", groups)
                    except Exception as error:
                        print(KeyError(error))
                        f.send_jira_comment(f'An error occurred while trying to search a user position:\n'
                                            f'*{error}* for *{organizational_unit}*.\n'
                                            f'Check if position exists in /permissions_by_orgunits/*groups_performance_marketing.json*'
                                            f' in and update json. Then try again.',
                                            jira_key=jira_key)
                        return KeyError(error)

                    juneos_user = f.create_juneos_user(first_name=first_name,
                                                       last_name=last_name,
                                                       suggested_email=suggested_email,
                                                       personal_phone=personal_phone,
                                                       dev_or_prod='prod',
                                                       )

                    if juneos_user[0] < 300:
                        # send event status as comment

                        with open("C:\PythonProjects\Fastapi\email_templates\juneos_prod.txt", "r") as data:
                            email_template = data.read()
                            username = email_template.replace('{username}', f'<b>{first_name}</b>')
                            final_draft = username.replace('{email}', f'<b>{suggested_email}</b>')

                        send_gmail_message.apply_async(
                            ('ilya.konovalov@junehomes.com',
                             [suggested_email],
                             ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com'],
                             'Access to JuneOS property management system',
                             final_draft,
                             round(unix_countdown_time / 3600)
                             ),
                            queue='new_emps',
                            countdown=round(unix_countdown_time)
                        )
                        fl.info(f"email 'Access to JuneOS property management system' will be sent in: {round(unix_countdown_time / 3600)}*, \n")
                        f.send_jira_comment("*JuneOS* user created.\n"
                                            f"Username: *{suggested_email}*, \n"
                                            f"*[User link|https://junehomes.com/december_access/users/user/{juneos_user[2]}/change/]*.\n"
                                            f"Credentials will be sent in: *{round(unix_countdown_time / 3600, 2)}* hours.",
                                            jira_key=jira_key)

                        juneos_auth = f.juneOS_devprod_authorization(dev_or_prod='prod')
                        if juneos_auth[0] < 300:
                            statuscode = juneos_auth[0]
                            csrftoken = juneos_auth[1]
                            sessionid = juneos_auth[2]
                            token = juneos_auth[3]

                            juneos_user_id = juneos_user[2]

                            fl.info(f"successfully authenticated in JuneOS production: {str(statuscode)}")
                            fl.info("Trying to Assign groups")

                            assigned_groups = f.assign_groups_to_user(user_id=juneos_user_id,
                                                                      groups=groups,
                                                                      dev_or_prod='prod',
                                                                      token=token,
                                                                      csrftoken=csrftoken,
                                                                      sessionid=sessionid
                                                                      )

                            if assigned_groups[0] < 300:
                                fl.info('groups assigned')
                                if position_title in ["Property manager", "Property Manager"]:
                                    f.send_jira_comment(f"Groups in JuneOS are successfully assigned to *[user|https://junehomes.com/december_access/"
                                                        f"users/user/{juneos_user_id}/change/]*.\n"
                                                        f"*Don't forget to add user to {position_title}s on juneOS.*\n"
                                                        f"*[LINK|https://junehomes.com/december_access/staff/propertymanager/add/]*",
                                                        jira_key=jira_key)
                                else:
                                    f.send_jira_comment('Groups in JuneOS are successfully assigned to *[user|https://junehomes.com/december_access/'
                                                        f'users/user/{juneos_user_id}/change/]*.\n',
                                                        jira_key=jira_key)

                            else:
                                fl.error('An error occurred while assigning groups to JuneOS user.\n'
                                         f'Error code: *{assigned_groups[0]}* \n\n'
                                         f'*{assigned_groups[1]}')
                                f.send_jira_comment('An error occurred while assigning groups to JuneOS user.\n'
                                                    f'Error code: *{assigned_groups[0]}* \n\n'
                                                    f'*{assigned_groups[1]}*',
                                                    jira_key=jira_key)

                        else:
                            fl.error('An error occurred while trying to authenticate on JuneOS.\n'
                                     f'Error code: *{juneos_auth[0]}* \n\n'
                                     f'*{juneos_auth[1]}*')
                            f.send_jira_comment('An error occurred while trying to authenticate on JuneOS.\n'
                                                f'Error code: *{juneos_auth[0]}* \n\n'
                                                f'*{juneos_auth[1]}*',
                                                jira_key=jira_key)
                    else:
                        fl.error('An error occurred while creating a JuneOS user.\n'
                                 f'Error code: *{juneos_user[0]}* \n\n'
                                 f'*{juneos_user[1]}*')
                        f.send_jira_comment('An error occurred while creating a JuneOS user.\n'
                                            f'Error code: *{juneos_user[0]}* \n\n'
                                            f'*{juneos_user[1]}*',
                                            jira_key=jira_key)

                else:
                    print(organizational_unit)

            elif jira_new_status == "Create a Zendesk account":
                print("WIP Zendesk, probably will never be done ;')")
                f.send_jira_comment('Zendesk users should be added either via SAML or manually *[here|https://junehomes.zendesk.com/agent/users/new]*'
                                    ' under [mailto:admin+zendesk@junehomes.com] account.\n'
                                    'New license can be bought *[here|https://junehomes.zendesk.com/admin/account/billing/subscription]*.\n'
                                    'Notion instruction on how to add new agents is *['
                                    'here|https://www.notion.so/junehomes/How-to-create-accounts-for-new-Employees-6b78fbc2a124400687df01cd73a14d4e'
                                    '#6fc1aec9f79a44de93919fefa19095fd]*.',
                                    jira_key=jira_key)
                pass

            else:
                fl.info('Got a status change different from what triggers the user account creation.')

        else:
            fl.info(f"The field \"{detect_change_type}\" was changed to: \"{detect_action}\". \n"
                    "Nothing will be done. Awaiting for the other request")
            pass


    @app.post("/maintenance_hiring", status_code=200)
    async def main_flow(
            body: dict = Body(...)
    ):
        jira_key = body['issue']['key']

        detect_change_type = body['changelog']['items'][0]['field']
        detect_action = body['changelog']['items'][0]['toString']
        fl.info(f"Change type: {detect_change_type}")
        if detect_change_type == 'status':
            jira_old_status = body['changelog']['items'][0]['fromString']
            jira_new_status = body['changelog']['items'][0]['toString']
            jira_description = re.split(': |\n', body['issue']['fields']['description'])
            fl.info(f"Key: {jira_key}")
            fl.info(f"Old Status: {jira_old_status}; New Status: {jira_new_status}")
            print(jira_description)

            position_title = jira_description[jira_description.index('*Position title*') + 1]
            first_name = jira_description[jira_description.index('*First name*') + 1]
            last_name = jira_description[jira_description.index('*Last name*') + 1]

            personal_email = jira_description[jira_description.index('*Personal email*') + 1].split("|")[0][
                             0:(len(jira_description[jira_description.index('*Personal email*') + 1]))]
            #  avoid sending email address in "[name@junehomes.com|mailto:name@junehomes.com]" - string format
            if personal_email[0:1] == '[':
                personal_email = personal_email[1:]
            elif personal_email == '':
                personal_email = jira_description[jira_description.index('h4. Personal email') + 1].split("|")[0]
                if personal_email[0:1] == '[':
                    personal_email = personal_email[1:]

            personal_phone = jira_description[jira_description.index('*Personal phone number*') + 1]
            # supervisor_email = jira_description[jira_description.index('*Supervisor (whom reports to)*') + 1]

            hire_start_date = jira_description[jira_description.index('*Start date (IT needs 3 working days to create accounts)*') + 1]
            unix_hire_start_date = datetime.strptime(hire_start_date, '%m/%d/%Y').timestamp()  # unix by the 00:00 AM

            fl.info(f"The type of the date is now {str(unix_hire_start_date)}")
            unix_countdown_time = unix_hire_start_date - round(time.time())
            print(unix_countdown_time)
            if unix_countdown_time <= 0:
                unix_countdown_time = 0

            groups = f.get_juneos_groups_from_position_title(file_name='groups_maintenance.json')[position_title]
            print(f"the group was found! \n{str(groups)}")

            fl.info(f"time for task countdown in hours: {str(unix_countdown_time / 3600)}")
            if jira_new_status == 'Create a JuneOS account':

                fl.info('Maintenance employee')

                try:
                    groups = f.get_juneos_groups_from_position_title(file_name='groups_maintenance.json')[position_title]
                    fl.info(f"the group was found!: \n{str(groups)}")

                except Exception as error:
                    fl.error(error)
                    f.send_jira_comment(f'An error occurred while trying to search a user position:\n'
                                        f'*{error}* for *{position_title}*.\n'
                                        f'Check if position exists in /permissions_by_orgunits/*groups_maintenance.json*'
                                        f' in and update json. Then try again.',
                                        jira_key=jira_key)
                    return KeyError(error)

                juneos_user = f.create_juneos_user(first_name=first_name,
                                                   last_name=last_name,
                                                   suggested_email=personal_email,
                                                   personal_phone=personal_phone,
                                                   dev_or_prod='prod',
                                                   )

                if juneos_user[0] < 300:
                    # send event status as comment
                    fl.info(f'User: {personal_email} is created successfully!')
                    with open("C:\PythonProjects\Fastapi\email_templates\juneos_prod.txt", "r") as data:
                        email_template = data.read()
                        username = email_template.replace('{username}', f'<b>{first_name}</b>')
                        final_draft = username.replace('{email}', f'<b>{personal_email}</b>')

                    send_gmail_message.apply_async(
                        ('ilya.konovalov@junehomes.com',
                         [personal_email],
                         ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com'],
                         'Access to JuneOS property management system',
                         final_draft,
                         round(unix_countdown_time / 3600)
                         ),
                        queue='new_emps',
                        countdown=round(unix_countdown_time)
                    )
                    fl.info(f"email 'Access to JuneOS property management system' will be sent in: {round(unix_countdown_time / 3600)}*, \n")

                    with open("C:\PythonProjects\Fastapi\email_templates\it_services_and_policies_wo_trello_zendesk.txt", "r") as data:
                        final_draft = data.read()

                    send_gmail_message.apply_async(
                        ('ilya.konovalov@junehomes.com',
                         [personal_email],
                         [],
                         'IT services and policies',
                         final_draft,
                         round(unix_countdown_time / 3600)),
                        queue='new_emps',
                        countdown=(round(unix_countdown_time) + 300))
                    # calculates the time before sending the email
                    fl.info(f"IT services and policies email will be sent in {round((unix_countdown_time + 300) / 3600, 2)} hours.")
                    # send event status as comment
                    f.send_jira_comment(f"*IT services and policies* email will be sent in *{round((unix_countdown_time + 300) / 3600, 2)}* hours.",
                                        jira_key=jira_key)

                    # creating a proper link for juneos reference

                    if position_title == "Property manager":
                        link = "propertymanager/add/"
                    elif position_title == "Housekeeper":
                        link = "housekeeper/add/"
                    elif position_title == "City manager":
                        link = "citymanager/add/"
                    else:
                        link = "/"

                    f.send_jira_comment("*JuneOS* user created.\n"
                                        f"Username: *{personal_email}*, \n"
                                        f"*[User link|https://junehomes.com/december_access/users/user/{juneos_user[2]}/change/]*.\n"
                                        f"Credentials will be sent in: *{round(unix_countdown_time / 3600, 2)}* hours.\n"
                                        f"*Don\'t forget to add user to {position_title}s on juneOS.*\n"
                                        f"*[LINK|https://junehomes.com/december_access/staff/{link}]*",
                                        jira_key=jira_key)
                    try:
                        juneos_auth = f.juneOS_devprod_authorization(dev_or_prod='prod')
                    except Exception as error:
                        fl.error(error)

                    if juneos_auth[0] < 300:
                        statuscode = juneos_auth[0]
                        csrftoken = juneos_auth[1]
                        sessionid = juneos_auth[2]
                        token = juneos_auth[3]

                        juneos_user_id = juneos_user[2]

                        fl.info(f"successfully authenticated in JuneOS production: {str(statuscode)}")
                        fl.info('Trying to Assign groups')

                        try:
                            assigned_groups = f.assign_groups_to_user(user_id=juneos_user_id,
                                                                      groups=groups,
                                                                      dev_or_prod='prod',
                                                                      token=token,
                                                                      csrftoken=csrftoken,
                                                                      sessionid=sessionid
                                                                      )
                        except Exception as error:
                            fl.error(error)

                        if assigned_groups[0] < 300:
                            fl.info('groups assigned')

                            f.send_jira_comment('Groups in JuneOS are assigned to *[user|https://junehomes.com/december_access/'
                                                f'users/user/{juneos_user_id}/change/]*.\n',
                                                jira_key=jira_key)



                        else:

                            f.send_jira_comment('An error occurred while assigning groups to JuneOS user.\n'
                                                f'Error code: *{assigned_groups[0]}* \n\n'
                                                f'*{assigned_groups[1]}*',
                                                jira_key=jira_key)

                            fl.error('An error occurred while assigning groups to JuneOS user.\n'
                                     f'Error code: *{assigned_groups[0]}* \n\n'
                                     f'*{assigned_groups[1]}')

                    else:
                        fl.error('An error occurred while trying to authenticate on JuneOS.\n'
                                 f'Error code: *{juneos_auth[0]}* \n\n'
                                 f'*{juneos_auth[1]}*')
                        f.send_jira_comment('An error occurred while trying to authenticate on JuneOS.\n'
                                            f'Error code: *{juneos_auth[0]}* \n\n'
                                            f'*{juneos_auth[1]}*',
                                            jira_key=jira_key)
                else:
                    fl.error('An error occurred while creating a JuneOS user.\n'
                             f'Error code: *{juneos_user[0]}* \n\n'
                             f'*{juneos_user[1]}*')
                    f.send_jira_comment('An error occurred while creating a JuneOS user.\n'
                                        f'Error code: *{juneos_user[0]}* \n\n'
                                        f'*{juneos_user[1]}*',
                                        jira_key=jira_key)

            elif jira_new_status not in ["To Do", "Done", "In Progress", "Rejected", "Waiting for dev", "Waiting for reply"]:
                f.send_jira_comment('*Creating a JuneOS account* is the only available for the maintenance employees.',
                                    jira_key=jira_key)
            else:
                pass

        else:
            fl.info(f"The field \"{detect_change_type}\" was changed to: \"{detect_action}\". \n"
                    "Nothing will be done. Awaiting for the other request")
            pass

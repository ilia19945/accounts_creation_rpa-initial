import requests
import re
import json
import time
# import random
# import string
import funcs as f
from fastapi import Body, FastAPI, HTTPException, Query  # BackgroundTasks
from typing import Optional

# run server: uvicorn mainfastapi:app --reload --port 80
# run ngrok: -> ngrok http 80
# if run through ngrok - don't forget to update uri and redirect urin in:
# jira webhook https://junehomes.atlassian.net/plugins/servlet/webhooks#
# google api - https://console.cloud.google.com/apis/credentials/oauthclient/675261997418-4pfe4aep6v3l3pl13lii6p8arsd4md3m.apps.googleusercontent.com?project=test-saml-accounts-creation
# google json

# import settings

app = FastAPI()

jira_key = ''

# triggers
# @app.get("/")
# async def simple_get():
#     return {"message": "Hello World"}
print("jira_key: " + jira_key)
if __name__ == 'mainfastapi':

    @app.get("/"
             # , name="Don't touch!! :P",
             # description='This method is a technical restriction of oAuth2.0 Google Authorization process.\n Never use it w/o a direct purpose'
             )
    async def redirect_from_google(code: Optional[str] = Query(None,
                                                               description='authorization code from google '
                                                                           'https://developers.google.com/identity/protocols/oauth2/web-serverexchange-authorization-code'),
                                   error: str = Query(None,
                                                      description='The error param google send us when the user denies to confirm authorization')
                                   ):
        if code and error:
            raise HTTPException(status_code=400, detail=f"Bad request. Parameters 'code'={code} and 'error'={error} can\'t be at the same query")

        elif code:
            if len(code) > 60 and len(code) < 85:  # assuming that auth code from Google is about to 73-75 symbols
                print('Received a request with code from google')
                file = open('authorization_codes.txt', 'a')
                file.write(str(time.asctime()) + ";" + code + '\n')  # add auth code to authorization_codes.txt
                file.close()

                print("Jira key: " + jira_key)
                f.exchange_auth_code_to_access_refresh_token(code, jira_key)
                return {"event": "The authorization code has been caught and saved."
                                 f"Close this page and go back to jira ticket tab, please."
                        }
            else:
                print('seems like a wrong value has been sent in the code parameter: ', code)
                return "Are you serious, bro? Is that really code from google?"
        elif error:
            print('User denied to confirm the permissions!\nMain flow is stopped!')
            return 'User denied to confirm the permissions! Main flow is stopped!'
        else:
            print('Received a random request')
            return 'Why are you on this page?=.='


    # webhook from jira

    @app.post("/webhook")
    async def main_flow(
            body: dict = Body(...)
    ):
        global jira_key
        jira_key = body['issue']['key']

        detect_change_type = body['changelog']['items'][0]['field']
        detect_action = body['changelog']['items'][0]['toString']
        print("Change type:", detect_change_type)
        if detect_change_type == 'status':
            jira_old_status = body['changelog']['items'][0]['fromString']
            jira_new_status = body['changelog']['items'][0]['toString']
            jira_description = re.split(': |\n', body['issue']['fields']['description'])
            print("Key: " + jira_key)
            print("Old Status: " + jira_old_status + "\nNew Status: " + jira_new_status)

            # print(jira_description)

            # detect only the specific status change
            if jira_old_status == "In Progress" and jira_new_status == "Create user accounts!":
                print("Correct event to create user accounts detected. Perform user creation attempt ...")
                print("timestamp: " + str(body['timestamp']))
                print("webhookEvent: " + body['webhookEvent'])
                print("user: " + body['user']['accountId'])

                organizational_unit = jira_description[jira_description.index('*Organizational unit*') + 1]
                first_name = jira_description[jira_description.index('*First name*') + 1]
                last_name = jira_description[jira_description.index('*Last name*') + 1]
                if organizational_unit == 'Member Success':
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
                # avoid sending email address in "[name@junehomes.com|mailto:name@junehomes.com] - string"
                if suggested_email[0:1] == '[':
                    suggested_email = suggested_email[1:]
                elif suggested_email == '':
                    suggested_email = jira_description[jira_description.index(
                        '*Suggested name@junehomes.com*') + 1].split("|")[0]
                    if suggested_email[0:1] == '[':
                        suggested_email = suggested_email[1:]

                personal_phone = jira_description[jira_description.index('*Personal phone number (with country code)*') + 1]

                gmail_groups = jira_description[jira_description.index('*Gmail - which groups needs access to*') + 1].split(',')
                # добавить сюда .strip() чтобы обрезать пробелы

                if '' in gmail_groups:
                    gmail_groups.remove('')
                if ' ' in gmail_groups:
                    gmail_groups.remove(' ')
                if 'team@junehomes.com' or ' team@junehomes.com' not in gmail_groups:
                    gmail_groups.append('team@junehomes.com')

                access_token = f.get_actual_token('access_token')
                datetime = f.get_actual_token('datetime')
                print("Access_token: " + access_token)
                print("datetime: " + datetime)
                print("first_name: " + first_name)
                print("last_name: " + last_name)
                print("personal_email: " + personal_email)
                print("suggested_email: " + suggested_email)
                print("organizational_unit: " + organizational_unit)
                print("personal_phone:" + personal_phone)
                print("gmail_groups (list):" + str(gmail_groups))
                print('Token lifetime:')
                print(int(str(time.time_ns())[0:10]) - int(datetime))

                if int(str(time.time_ns())[0:10]) - int(datetime) >= 3200:  # token was refreshed more than 1h ago
                    print('Access token expired! Try to get get_actual_token("refresh_token"):')

                    try:  # look for refresh token in .json file
                        refresh_token = f.get_actual_token('refresh_token')
                        print("Refresh_token: " + refresh_token)

                    except KeyError:  # if there is no refresh token -> new app permission should be requested.
                        print("Refresh token wasn't found.\nNew access token should be requested before moving forward."
                              "Prompt the user to follow the link and accept app permissions (if asked):")
                        new_access_token = f.get_new_access_token()
                        print(new_access_token)
                        jira_comment_response = f.send_jira_comment(
                            "*Access token expired!*\nNew access token should be requested before moving forward. "
                            "Press the ☢ {color:red}*[BIG RED BUTTON|" + new_access_token + "]""*{color} ☢ "
                                                                                            "and accept app permissions (if asked).\n"
                                                                                            "⚠ *REMEMBER: IT'S ONE TIME LINK! SHOULD BE DELETED AFTER REFRESHING* ⚠\n"
                                                                                            "(It's recommended to open in a new browser tab)\n",
                            jira_key)
                        if jira_comment_response[0] > 300:
                            print("Jira comment wasn't added")

                        print("Jira comment was added successfully")

                    else:  # if refresh token was found in .json file
                        print('Refresh token was provided by google. Refresh token_func() is executed \n')
                        f.refresh_token_func()
                        f.send_jira_comment("Current access_token expired. It was automatically refreshed. "
                                            "Please try to create user again.\n"
                                            "(Switch the ticket status -> \"In Progress\" -> \" Create user accounts!\")", jira_key)

                else:
                    print('Access token is actual. Suggested user email will be checked to the uniqueness.')
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
                            print(f"(1/3) User {first_name} {last_name} is successfully created!\n"
                                  f"Username: {suggested_email}\n")
                            f.send_jira_comment(f"(1/3) User *{first_name} {last_name}* is successfully created!\n"
                                                f"User Email: *{suggested_email}*\n", jira_key)

                            # creating draft message for sending later from gmail interface
                            # email templates are in \email_templates folder. need to update them there.

                            # create a temlate for draft
                            with open("C:\PythonProjects\Fastapi\email_templates\google_mail.txt", "r") as data:
                                email_template = data.read()
                                username = email_template.replace('{username}', f'<b>{first_name}</b>')
                                final_draft = username.replace('{STRINGTOREPLACE}',
                                                               f'<p style="font-family:verdana">- username:  <b>{suggested_email}</b></p>\n\n'
                                                               f'<p style="font-family:verdana">- password:  <b>{f.password}</b></p>')
                                print(final_draft)

                            # creates a draft in "Sender" gmail inbox
                            f.create_draft_message(to="ilya.konovalov@junehomes.com;",
                                                   sender='ilya.konovalov@junehomes.com',
                                                   cc='idelia@junehomes.com;ivan@junehomes.com;artyom@junehomes.com; PUT EMP\'S SV-s HERE <emp@supervisor.com>',
                                                   subject='June Homes: corporate email account',
                                                   message_text=final_draft)

                            # proceeding to licence assignment according the department.

                            if organizational_unit == 'Member Success':  # additional if check needs because that's another function
                                assigned_license = f.assign_google_license('1010020020', suggested_email)
                                if assigned_license[0] < 300:  # if success
                                    print("(2/3) Google Workspace Enterprise Plus license, successfully assigned!")
                                    f.send_jira_comment(
                                        "(2/3) *Google Workspace Enterprise Plus* license, successfully assigned!", jira_key)
                                elif assigned_license[0] == 412:
                                    f.send_jira_comment(f"Not enough licenses. Google error:\n{assigned_license[1]}", jira_key)
                                else:  # if error
                                    f.send_jira_comment("An error appeared while assigning google license.\n"
                                                        f"Error code: {assigned_license[0]}\n"
                                                        f"Error message: {assigned_license[1]['error']['message']}", jira_key)
                                    print(assigned_license[0])
                                    print(assigned_license[1])  # response body 

                            # other department
                            else:
                                assigned_license = f.assign_google_license('Google-Apps-Unlimited', suggested_email)
                                if assigned_license[0] < 300:  # if success
                                    print("(2/3) *G Suite Business* license, successfully assigned!")
                                    f.send_jira_comment("(2/3) G Suite Business license, successfully assigned!", jira_key)
                                elif assigned_license[0] == 412:
                                    f.send_jira_comment(f"Not enough licenses. Google error:\n{assigned_license[1]}", jira_key)
                                else:  # if error
                                    f.send_jira_comment("An error appeared while assigning google license.\n"
                                                        f"Error code: {assigned_license[0]}\n"
                                                        f"Error message: {assigned_license[1]['error']['message']}", jira_key)
                                    print(assigned_license[0])
                                    print(assigned_license[1])  # response body

                            print("gmail_groups to assign:", gmail_groups)
                            final_row = f.adding_user_to_google_group(gmail_groups, suggested_email)
                            print(f"(3/3) {final_row}")
                            f.send_jira_comment(f"(3/3) Assigned google groups:\n"
                                                f"{final_row}", jira_key)

                            # need to create user in juneos but impossible due to point 4 & 5
                            # https://www.notion.so/junehomes/Automatic-user-accounts-creation-82fe3380c2f749ef9d1b37a1e22abe7d

                            # Create user in dev.junehomes.com
                            if organizational_unit == 'IT':
                                juneos_dev_user = f.create_juneos_dev_user(first_name=first_name,
                                                                           last_name=last_name,
                                                                           suggested_email=suggested_email,
                                                                           personal_phone=personal_phone,
                                                                           password=f.password
                                                                           )

                                if juneos_dev_user[0] < 300:

                                    # creates an email template from juneos_dev.txt
                                    with open("C:\PythonProjects\Fastapi\email_templates\juneos_dev.txt", "r") as data:
                                        email_template = data.read()
                                        username = email_template.replace('{username}', f'<b>{first_name}</b>')
                                        final_draft = username.replace('{email}', f'<b>{suggested_email}</b>')
                                        # print(main)

                                    # sends JuneOS.Development corporate email account to gmail
                                    f.send_gmail_message(to=f"{suggested_email}",
                                                         sender='ilya.konovalov@junehomes.com',
                                                         cc='idelia@junehomes.com;ivan@junehomes.com;artyom@junehomes.com',
                                                         subject='Access to JuneOS.Development property management system',
                                                         message_text=final_draft)

                                    # send event status as comment
                                    f.send_jira_comment("*JuneOS development* user created.\n"
                                                        f"Username: *{suggested_email}*, \n"
                                                        f"*User [link|https://dev.junehomes.net/december_access/users/user/{juneos_dev_user[3]}/change/]*.\n"
                                                        f"Credentials are sent to *{suggested_email}*.",
                                                        jira_key=jira_key)

                                else:
                                    print('error')
                                    # send event status as comment
                                    f.send_jira_comment(f"An error occurred while creating a juneOS dev user.\n Error: \n{juneos_dev_user[0]}",
                                                        jira_key=jira_key)

                            # other services ...........
                            # amazon_user = create_amazon_user()
                            # if amazon_user[0] < 300 :

                            # at the end, when all services are created, an IT security policies email should be sent
                            if organizational_unit == 'Member Support':
                                with open("C:\PythonProjects\Fastapi\email_templates\it_services_and_policies_support.txt", "r") as data:
                                    final_draft = data.read()

                                # sends June Homes: corporate email account  to gmail
                                f.send_gmail_message(to=f"{suggested_email}",
                                                     sender='ilya.konovalov@junehomes.com',
                                                     cc='',
                                                     subject='IT services and policies',
                                                     message_text=final_draft)

                            else:

                                with open("C:\PythonProjects\Fastapi\email_templates\it_services_and_policies_wo_trello_zendesk.txt", "r") as data:
                                    final_draft = data.read()

                                # sends it_services_and_policies_wo_trello_zendesk email to gmail
                                f.send_gmail_message(to=f"{suggested_email}",
                                                     sender='ilya.konovalov@junehomes.com',
                                                     cc='',
                                                     subject='IT services and policies',
                                                     message_text=final_draft)

                                # send event status as comment
                                f.send_jira_comment("Final is reached!\n"
                                                    "*IT services and policies* email is sent. Please check your 'Sent'",
                                                    jira_key=jira_key)

                        # if the normal flow is violated
                        # error creating google user
                        else:
                            f.send_jira_comment("An error occurred while creating google user attempt\n"
                                                f"Error code: {google_user[0]}\n"
                                                f"Error response: {google_user[1]}", jira_key)

            else:
                print('Got a status change different from what triggers the user account creation.')

        else:
            print(f"The field \"{detect_change_type}\" was changed to: \"{detect_action}\". \n"
                  "Nothing will be done. Awaiting for the other request")
            pass

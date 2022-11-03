import json
import os
import time
from pprint import pprint
import re
import boto3

from config import email_cc_list
from funcs import gmail_app_password, send_jira_comment, notion_search_for_role, notion_search_for_permission_block_children, get_notion_page_title, compare_permissions_by_name, full_compare_by_name_and_permissions_with_file, checking_config_for_service_existence, compare_role_configs_google, \
    comparing_permission_from_notion_vs_config_on_disk, create_google_user_req, assign_google_license, adding_user_to_google_group, adding_to_junehomes_dev_calendar, create_elk_user, adding_jira_cloud_user, compare_role_configs_juneos
from celery import Celery

from email.mime.text import MIMEText
import smtplib
import fast_api_logging as fl

from jinja2 import Environment, FileSystemLoader

loader = FileSystemLoader("email_templates")
env = Environment(loader=loader)

celery_app = Celery('tasks', backend='redis://localhost', broker='redis://localhost', queue='new_emps,terminations,other')
celery_app.conf.broker_transport_options = {'visibility_timeout': 2592000}  # 30 days
fl.info('Celery server has successfully initialised.')


# to run celery with 3 queues type in terminal:
# celery -A tasks worker -E --loglevel=INFO -Q new_emps,terminations,other -P gevent
# to run flower with admin user:
# celery -A tasks flower --basic_auth=admin:admin

@celery_app.task
def send_gmail_message(sender, to, cc, subject, message_text, countdown):
    fl.info(f'A new task is received. Email subject: {subject}. To: {to}. Countdown (in hours):{countdown}.')

    message = MIMEText(message_text, 'html')
    message['from'] = sender
    message['to'] = ",".join(to)
    message['cc'] = ",".join(cc)
    message['subject'] = subject

    recipients = to + cc

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender, gmail_app_password)
    server.sendmail(from_addr=sender, to_addrs=recipients, msg=message.as_string())
    server.quit()
    fl.info(f'Message will be sent to:{to}, hours to send: {countdown}')
    return f'Message was successfully sent to:{to}, hours to send was: {countdown}'


@celery_app.task
def async_google_account_license_groups_calendar_creation(
        first_name,
        last_name,
        suggested_email,
        organizational_unit,
        gmail_groups,
        unix_countdown_time,
        personal_email,
        supervisor_email,
        role_title,
        jira_key, ):
    google_user = create_google_user_req(first_name, last_name, suggested_email, organizational_unit)

    if google_user[0] < 300:  # user created successfully
        google_password = google_user[2]

        print('This is your google password:', google_password)

        fl.info(f"User {first_name} {last_name} is created. Username: {suggested_email}\n")
        send_jira_comment(f"(1/3) User *{first_name} {last_name}* is successfully created!\n"
                          f"User Email: *{suggested_email}*\n", jira_key)

        # proceeding to licence assignment according the department.

        if organizational_unit == 'Sales' and role_title != 'Vendor Tour Manager':
            assigned_license = assign_google_license('1010020020', suggested_email)

            if assigned_license[0] < 300:  # if success
                send_jira_comment(
                    "(2/3) *Google Workspace Enterprise Plus* license, successfully assigned!", jira_key)
                fl.info("Google Workspace Enterprise Plus license, assigned")

            elif assigned_license[0] == 412:
                send_jira_comment(f"Not enough licenses. Google error:\n{assigned_license[1]}", jira_key)
                fl.error(f"Not enough licenses. Google error:\n{assigned_license[1]}")

            else:  # if error
                send_jira_comment("An error appeared while assigning google license.\n"
                                  f"Error code: {assigned_license[0]}\n"
                                  f"Error message: {assigned_license[1]['error']['message']}", jira_key)

                fl.error(f"Error code: {assigned_license[0]}\n"
                         f"Error message: {assigned_license[1]['error']['message']}")

        # other department
        else:
            assigned_license = assign_google_license('Google-Apps-Unlimited', suggested_email)

            if assigned_license[0] < 300:  # if success
                send_jira_comment("(2/3) *G Suite Business* license, successfully assigned!", jira_key)
                fl.info("G Suite Business license, assigned!")

            elif assigned_license[0] == 412:
                send_jira_comment(f"Not enough licenses. Google error:\n{assigned_license[1]}", jira_key)
                fl.error(f"Not enough licenses. Google error:\n{assigned_license[1]}")

            else:  # if error
                send_jira_comment("An error appeared while assigning google license.\n"
                                  f"Error code: {assigned_license[0]}\n"
                                  f"Error message: {assigned_license[1]['error']['message']}", jira_key)

                fl.error(f"Error code: {assigned_license[0]}\n"
                         f"Error message: {assigned_license[1]['error']['message']}")

        fl.info(f"gmail_groups to assign: {str(gmail_groups)}")

        # errors are inside the function
        final_row = adding_user_to_google_group(gmail_groups, suggested_email)

        fl.info(f"Groups assigned: {final_row}")

        send_jira_comment(f"(3/3) Assigned google groups:\n"
                          f"{final_row}", jira_key)

        if organizational_unit == 'Technology':

            # !!!!!!!!!!!!!!!! dont forget to turn on again!
            # ----------------------------------------------
            # Ping Idelia to add the new IT emp to Gitlab and CI/CD
            message = open("mention_idelia.txt", "r", encoding="UTF-8").read()
            send_jira_comment(message=json.loads(message.replace('suggested_email', suggested_email)),
                              jira_key=jira_key)

            # надо все через Try except сделать, иначе будет падать(
            # adding IT emp to calendar
            calendar_id = 'junehomes.com_6f1l2kssibhmsg10e7fvnmdv1o@group.calendar.google.com'
            adding_to_calendar_result = adding_to_junehomes_dev_calendar(suggested_email=suggested_email,
                                                                         calendar_id=calendar_id)

            if adding_to_calendar_result[0] < 300:  # user created successfully
                fl.info(f"User *{suggested_email}* is added to *[junehomes-dev calendar|]*.")
                send_jira_comment(f"User *{suggested_email}* is added to *[junehomes-dev "
                                  f"calendar|https://calendar.google.com/calendar/u/0/r/settings/calendar/anVuZWhvbWVzLmNvbV82ZjFsMmtzc2liaG1zZzEwZTdmdm5tZHYxb0Bncm91cC5jYWxlbmRhci5nb29nbGUuY29t?pli=1]*.",
                                  jira_key)

            else:
                send_jira_comment(
                    f"An error occured while trying to add a User: *{suggested_email}* to *[junehomes-dev calendar|]*.\n"
                    f"Error code: *{adding_to_calendar_result[0]}*\n"
                    f"Error body: {adding_to_calendar_result[1]}",
                    jira_key=jira_key)
                fl.info(f"An error occured while trying to add a User: *{suggested_email}* to *[junehomes-dev calendar|]*.\n"
                        f"Error code: *{adding_to_calendar_result[0]}*\n"
                        f"Error body: {adding_to_calendar_result[1]}")
            # ----------------------------------------------
            # ^^^^ all related to calendar!!!

            adding_user_to_jira = adding_jira_cloud_user(suggested_email=suggested_email)

            if adding_user_to_jira[0] < 300:
                fl.info(f"Jira user *{suggested_email}* is created.")
                send_jira_comment(f"Jira user *{suggested_email}* is created.", jira_key)

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
                send_jira_comment(f"An error occurred while creating Jira user *{suggested_email}*.\n"
                                  f"Error code: {adding_user_to_jira[0]} \n"
                                  f"Error body: {adding_user_to_jira[1]}", jira_key)

            # creating account on ELK Development
            try:
                adding_user_to_elk_dev = create_elk_user(firstname=first_name,
                                                         lastname=last_name,
                                                         suggested_email=suggested_email,
                                                         role='viewer',
                                                         dev_or_prod='dev'
                                                         )
            except Exception as e:
                send_jira_comment('An error occurred when trying to add a user on ELK DEV:\n'
                                  f'{e}', jira_key)
            else:

                if adding_user_to_elk_dev[0].status_code < 300:

                    fl.info(f'ELK Dev user is created. ELK dev credentials will be sent in: '
                            f'*{round(unix_countdown_time / 3600)} hours*.')
                    send_jira_comment(f'ELK Dev user is created. ELK dev credentials will be sent in: '
                                      f'*{round(unix_countdown_time / 3600)} hours*.', jira_key)

                    template = env.get_template(name="kibana_jinja.txt")

                    final_draft = template.render(first_name=first_name,
                                                  suggested_email=suggested_email,
                                                  stage="Development",
                                                  password=adding_user_to_elk_dev[1]
                                                  )

                    send_gmail_message.apply_async(
                        ('ilya.konovalov@junehomes.com',
                         [personal_email],
                         email_cc_list + [supervisor_email],
                         'Your Kibana.Development credentials.',
                         final_draft,
                         round(unix_countdown_time / 3600)),
                        queue='new_emps',
                        countdown=round(unix_countdown_time) + 120
                    )

                else:
                    fl.info(f'ELK Dev user is NOT created!\n'
                            f'Response:{adding_user_to_elk_dev[0].status_code}\n'
                            f'{adding_user_to_elk_dev[0].json()}')

                    send_jira_comment(f'ELK Dev user is *NOT created*!\n'
                                      f'Response:{adding_user_to_elk_dev[0].status_code}\n'
                                      f'{adding_user_to_elk_dev[0].json()}', jira_key)

            # creating account on ELK Production
            try:
                adding_user_to_elk_prod = create_elk_user(firstname=first_name,
                                                          lastname=last_name,
                                                          suggested_email=suggested_email,
                                                          role='viewer',
                                                          dev_or_prod='prod'
                                                          )
            except Exception as e:
                send_jira_comment('An error occurred when trying to add a user on ELK PROD:\n'
                                  f'{e}', jira_key)
            else:

                if adding_user_to_elk_prod[0].status_code < 300:

                    template = env.get_template(name="kibana_jinja.txt")

                    final_draft = template.render(first_name=first_name,
                                                  suggested_email=suggested_email,
                                                  stage="Production",
                                                  password=adding_user_to_elk_dev[1]
                                                  )

                    send_gmail_message.apply_async(
                        ('ilya.konovalov@junehomes.com',
                         [personal_email],
                         email_cc_list + [supervisor_email],
                         'Your Kibana.Production credentials.',
                         final_draft,
                         round(unix_countdown_time / 3600)),
                        queue='new_emps',
                        countdown=round(unix_countdown_time) + 120
                    )

                    fl.info(f'ELK Prod user is created. ELK Prod credentials will be sent in: '
                            f'*{round((unix_countdown_time / 3600), 2)} hours*.')
                    send_jira_comment(f'ELK Prod user is created. ELK Prod credentials will be sent in: '
                                      f'*{round((unix_countdown_time / 3600), 2)} hours*.', jira_key)
                else:

                    fl.info(f'ELK Prod user is *NOT created!*'
                            f'Response: {adding_user_to_elk_prod[0].status_code} '
                            f'{adding_user_to_elk_prod[0].json()}')

                    send_jira_comment(f'ELK Prod user is NOT created!\n'
                                      f'Response:{adding_user_to_elk_prod[0].status_code}\n'
                                      f'{adding_user_to_elk_prod[0].json()}', jira_key)
        google_password = google_user[2]
        # create a template for email
        template = env.get_template(name="google_mail_jinja.txt")
        final_draft = template.render(first_name=first_name,
                                      suggested_email=suggested_email,
                                      password=google_password
                                      )
        print(final_draft)

        ## Sending a corporate email
        send_gmail_message.apply_async(
            ('ilya.konovalov@junehomes.com',
             [personal_email],
             email_cc_list + [supervisor_email],
             'June Homes: corporate email account',
             final_draft,
             round(unix_countdown_time / 3600)),
            queue='new_emps',
            countdown=round(unix_countdown_time) + 120
        )
        fl.info(f'June Homes: corporate email account will be sent in {round((unix_countdown_time / 3600), 2)}')

        # calculates the time before sending the email
        # countdown=60
        send_jira_comment(f"*June Homes: corporate email account* email will be sent to\n "
                          f"User: *{personal_email}*\n"
                          f"In: *{round((unix_countdown_time / 3600), 2)}* hours.\n", jira_key)

        template = env.get_template('it_services_and_policies_wo_trello_zendesk.txt')
        final_draft = template.render()

        # at the end, when all services are created, an IT security policies email should be sent
        if organizational_unit == 'Resident Experience':

            template = env.get_template('it_services_and_policies_support.txt')
            final_draft = template.render()

            # sends IT services and policies for residents experience
            send_gmail_message.apply_async(
                ('ilya.konovalov@junehomes.com',
                 [suggested_email],
                 [],
                 'IT services and policies',
                 final_draft,
                 round(unix_countdown_time / 3600)),
                queue='new_emps',
                countdown=round(unix_countdown_time) + 600
            )

            # calculates the time before sending the email
            fl.info(f'June Homes: corporate email account will be sent in {round((unix_countdown_time / 3600), 2)}')

        else:

            template = env.get_template('it_services_and_policies_wo_trello_zendesk.txt')
            final_draft = template.render()

            # sends it_services_and_policies_wo_trello_zendesk email to gmail
            send_gmail_message.apply_async(
                ('ilya.konovalov@junehomes.com',
                 [suggested_email],
                 [],
                 'IT services and policies',
                 final_draft,
                 round(unix_countdown_time / 3600)),
                queue='new_emps',
                countdown=round(unix_countdown_time) + 600
            )

            # calculates the time before sending the email
            fl.info(f"IT services and policies email will be sent in {round((unix_countdown_time + 300) / 3600, 2)} hours.")
        send_jira_comment("Final is reached!\n"
                          f"*IT services and policies* email will be sent in *{round((unix_countdown_time + 300) / 3600, 2)}* "
                          "hours.",
                          jira_key=jira_key)

    else:
        send_jira_comment("An error occurred while creating a google user!\n"
                          f"Error code: {google_user[0]}\n"
                          f"Error response: {google_user[1]}", jira_key)


@celery_app.task
def create_amazon_user(suggested_email,
                       first_name,
                       last_name,
                       user_email_analogy,
                       password,
                       final_draft,
                       unix_countdown_time,
                       jira_key):
    client = boto3.client('connect')
    instance_id = 'a016cbe1-24bf-483a-b2cf-a73f2f389cb4'

    send_jira_comment(f'*Celery task* to create Amazon account for *"{suggested_email}"* is added.\n'
                      'Please, wait...', jira_key)

    # receives a list of users
    response = client.list_users(
        InstanceId=instance_id,
        MaxResults=100
    )
    # print(len(response['UserSummaryList']))
    i = 0
    user_list = []

    # creating a list of users
    # async with aiohttp.ClientSession() as session:
    while True:
        i += 1
        try:
            # print(response['NextToken'])
            user_list += response['UserSummaryList']
            response = client.list_users(
                InstanceId=instance_id,
                MaxResults=1,
                NextToken=response['NextToken']
            )
            fl.info(f'Iteration number: {str(i)}')
        except KeyError:
            break
    # pprint(user_list, indent=1)

    analogy_user_exists = False

    # check if the user is already created
    for i in range(len(user_list)):
        if suggested_email in user_list[i]['Username']:
            send_jira_comment(f'User: *{suggested_email}* is already created!', jira_key=jira_key)
            fl.info(f'User: *{suggested_email}* is already created!')
            return
        else:
            pass

    # check if the analogy user exists on amazon
    for i in range(len(user_list)):
        if user_email_analogy in user_list[i]['Username']:
            amazon_user_id = user_list[i]['Id']
            fl.info(amazon_user_id)
            # receive a user description from amazon
            response = client.describe_user(
                UserId=str(amazon_user_id),
                InstanceId=instance_id
            )

            analogy_user_exists = True

            # creating a user
            try:
                response = client.create_user(
                    Username=suggested_email,
                    Password=password,
                    IdentityInfo={
                        'FirstName': first_name,
                        'LastName': last_name,
                        'Email': suggested_email
                    },
                    PhoneConfig={
                        'PhoneType': response['User']['PhoneConfig']['PhoneType'],
                        'AutoAccept': response['User']['PhoneConfig']['AutoAccept'],
                        'AfterContactWorkTimeLimit': 60
                    },
                    # DirectoryUserId='string',
                    SecurityProfileIds=response['User']['SecurityProfileIds'],
                    RoutingProfileId=response['User']['RoutingProfileId'],
                    # HierarchyGroupId='string',
                    InstanceId=instance_id,
                    Tags={}
                )
                fl.info(response)
                # fl.info(f"Amazon password: {password}")
                fl.info(f'Amazon account for *{suggested_email}* is created.')

            except Exception as error:  # error while creating a user
                fl.error(msg=error)
                send_jira_comment('An error occurred while creating *Amazon account*:\n\n'
                                  f'*{error}*',
                                  jira_key=jira_key)
                return

            else:  # no errors normal flow

                # adding the credentials to txt file
                file = open(r'''User Accounts.txt''', 'a', encoding='utf-8')
                file.write(f"Amazon username: {suggested_email}\nPassword: {password}\n\n")
                file.close()

                fl.info('*Amazon account* is created successfully!\n'
                        f'An email with Amazon account credentials will be sent to {suggested_email}')
                send_jira_comment('*Amazon account* is created successfully!\n'
                                  f'An email with Amazon account credentials will be sent to *{suggested_email}* '
                                  f'in *{round(unix_countdown_time / 3600)}* hours\n',
                                  jira_key=jira_key)

                # normal flow - returns another celery task to send the email
                return send_gmail_message.apply_async(
                    ('ilya.konovalov@junehomes.com',
                     [suggested_email],
                     email_cc_list,
                     'Access to Amazon Connect call center',
                     final_draft,
                     round(unix_countdown_time / 3600)),
                    queue='new_emps',
                    countdown=round(unix_countdown_time + 120))

        else:
            print("Iteration: ", i)
            pass

    if not analogy_user_exists:
        fl.info('Amazon account* is NOT created.\n'
                f'"{user_email_analogy}" from user example doesn\'t exist!')

        send_jira_comment('*Amazon account* is NOT created.\n'
                          f'*{user_email_analogy}* from user example doesn\'t exist!\n',
                          jira_key=jira_key)
        return
    return


@celery_app.task  # old process
def check_role_permissions(role_title, jira_key):
    send_jira_comment(f'*Celery task* to check permissions of *"{role_title}"* is added.\n'
                      'Please, wait...', jira_key)

    permissions_for_persona_list = notion_search_for_role(role_title, jira_key=jira_key)  # the list of page_ids
    if not permissions_for_persona_list:
        print(f'Permissions are not added for {role_title}!')
        send_jira_comment(f'Permissions are not added for *{role_title}* role ❌', jira_key=jira_key)
        return  # ⚠️ ⚠️ ⚠️stops the main flow!
    else:
        # trying to create a directory for this role:
        path = os.path.join(f".\\roles_configs\\{jira_key}", role_title)
        mode = 0o666
        os.makedirs(path, mode)
        pages_list = ''
        for i in range(len(permissions_for_persona_list)):
            print(f"Reviewing {i + 1} / {len(permissions_for_persona_list)} permissions...for ({get_notion_page_title(permissions_for_persona_list[i]['id']).json()['properties']['Name']['title'][0]['plain_text']})")
            try:
                result = notion_search_for_permission_block_children(permissions_for_persona_list[i]['id'])

                if type(result) == tuple:  # because the correct variant should contain "True" i.e. - (result,True)
                    pages_list += f"[{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['properties']['Name']['title'][0]['plain_text']}|" \
                                  f"{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['url']}]: Validated, Good Job! ✅ \n"
                    with open(f".\\roles_configs\\{jira_key}\\{role_title}\\{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['properties']['Name']['title'][0]['plain_text']}.json", 'w+') as file:
                        file.write(str(json.dumps(result[0])))
                else:
                    pages_list += f"[{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['properties']['Name']['title'][0]['plain_text']}|" \
                                  f"{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['url']}]: *{result}*\n"
            except Exception as e:
                print(e)
        # print(pages_list)
        send_jira_comment(message=f"The summary after reviewing permissions for {role_title} persona:\n{pages_list}", jira_key=jira_key)


@celery_app.task
def new_check_role_and_permissions(role_title, jira_key):
    position_title = role_title
    t0 = time.time()
    send_jira_comment('A request to build a role config is sent to *Celery*. PLease, wait...\n '
                      'P.s. if there are lots of permissions and dependent roles it might take up to a few min for the config to be built.', jira_key=jira_key)
    permissions_history_check = []

    permissions_for_persona_list = notion_search_for_role(position_title, jira_key=jira_key)  # the list of page_ids
    pprint(permissions_for_persona_list)

    if len(permissions_for_persona_list) == 0:  # если пермиссии для персоны не добавлены!
        print(f'Permissions are not added for {position_title}!')
        # send_jira_comment(f'Permissions are not added for *{position_title}* position ❌', jira_key=jira_key)
        # return  # ⚠️ ⚠️ ⚠️stops the main flow!
    else:
        next_level_checker = False

        # # trying to create a directory for this role:
        try:
            path = os.path.join(f".\\roles_configs\\{jira_key}", position_title)
            mode = 0o666
            os.makedirs(path, mode)
        except Exception as e:
            print('An error while trying to create a folder:', e)
        else:
            pages_list = ''
            for i in range(len(permissions_for_persona_list))[::-1]:  # как было раньше

                # print(type(permissions_for_persona_list[i]))
                # print(permissions_for_persona_list[i-1])
                # print(type(permissions_for_persona_list[i-1]))
                # print()
                # print()

                current_permissions_set = permissions_for_persona_list[i]
                antecedent_permissions_set = permissions_for_persona_list[i - 1]

                # здесь текущий (n) и за ним уровень (n-1) - НЕ корневые
                # пока только для Google Workspace и JuneOS
                if type(current_permissions_set) == list and type(antecedent_permissions_set) == list:  # здесь имеем сет из пермиссий, каждый из которых нужно сравнить с предыдущим, с конца*
                    # # print(f"{permissions_for_persona_list[i]} --- {type(*permissions_for_persona_list[i])}, this is a nested permissions")
                    # # print(current_permissions_set[0])
                    # # print(antecedent_permissions_set[0])
                    print("current and previous permissions sets are both type 'List'")

                    for p in range(len(current_permissions_set[0])):  # берем n уровень, проверяем каждую пермиссию
                        # получаем результат проверки для коммента, название текущей роли и json конфиг
                        pages_list, current_role_name, current_json_object = compare_permissions_by_name(permissions_set=current_permissions_set,
                                                                                                         pages_list=pages_list,
                                                                                                         iterator=p,
                                                                                                         level=1,
                                                                                                         jira_key=jira_key,
                                                                                                         position_title=position_title)

                        if not current_json_object:  # failed or missing json_config, should not be added to config
                            print('there is an error in the document', current_json_object)
                            pages_list += "–––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"

                        else:
                            print(f'current_json_object for "{current_role_name}":')
                            pprint(current_json_object, indent=1)

                            if re.findall('googleworkspace', current_role_name):
                                file_role_name_for_comparison = 'googleworkspace'
                            elif re.findall('amazonconnect', current_role_name):
                                file_role_name_for_comparison = 'amazonconnect'
                            elif re.findall('juneos', current_role_name):
                                file_role_name_for_comparison = 'juneos'
                            elif re.findall('frontapp', current_role_name):
                                file_role_name_for_comparison = 'frontapp'
                            elif re.findall('slack', current_role_name):
                                file_role_name_for_comparison = 'slack'
                            else:
                                print('else:', current_role_name)
                                relevant_config = False
                                continue
                            print(f'role_name_for_comparison - {file_role_name_for_comparison}')
                            relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                                config_name=file_role_name_for_comparison,
                                antecedent_permissions_set=antecedent_permissions_set,
                                jira_key=jira_key,
                                position_title=position_title,
                                current_json_object=current_json_object,
                                pages_list=pages_list,
                                current_role_name=current_role_name)

                        print('-----end iteration of comparing the json config in notion with config on the disc-----')
                    # ================================================
                    pass

                # здесь текущий уровень - зависимая пермиссия (list), а за ним уже корневые пермиссии (dict)
                # т.е. уровень когда пермиссии parent role-и должны быть сравнены с корневой ролью
                elif type(current_permissions_set) == list and type(antecedent_permissions_set) == dict:
                    print("current  permissions set is 'list' while the previous permissions set is 'dict'")
                    pass

                    # ================================================
                    # ВСЕ РАБОТАЕТ УРА!!! ПРОСТО РАСКОММЕНТИТЬ ТО ЧТО МЕЖДУ ===
                    #
                    pages_list += '\n'
                    print(f"{current_permissions_set} --- {type(current_permissions_set)}, current_permissions_set")
                    print(f"{antecedent_permissions_set} --- {type(antecedent_permissions_set)}, antecedent_permissions_set")

                    items_list = []

                    try:
                        items_list = checking_config_for_service_existence(
                            position_title=position_title,
                            jira_key=jira_key,
                        )

                    except Exception as e:
                        print(f"Error occurred on: {e}")
                    print(items_list)

                    for p in range(len(current_permissions_set[0])):  # берем n уровень, проверяем каждую пермиссию

                        current_permission_id = current_permissions_set[0][p]['id']
                        current_role_name = get_notion_page_title(current_permission_id).json()['properties']['Name']['title'][0]['plain_text']
                        current_role_url = get_notion_page_title(current_permission_id).json()['url']

                        print('current_role_name:', current_role_name)
                        # print('current_role_url:', current_role_url)
                        # print('current_permission_id:', current_permission_id)

                        current_result = notion_search_for_permission_block_children(current_permission_id)  # запрашиваем есть ли json
                        print('current_result type:', type(current_result))
                        print('current_result:', current_result)
                        # print('got OUT of notion_search_for_permission_block_children')

                        if type(current_result) == tuple:  # tuple если конфиг валидный и нужно записать на диск
                            # print(data)
                            # if data != 'False':
                            print('data in the config != false')
                            if len(items_list) != 0:  # т.е. если в списке на диске уже есть какие-то конфиги
                                print("ITEMS LIST HAS CONFIGS!")
                                for i in range(len(items_list)):
                                    config_name = re.split('_', items_list[i])[0]
                                    filename = f".\\roles_configs\\{jira_key}\\{position_title}\\{config_name}_config.json"
                                    print("config_name -", config_name, ", current_role_name -", current_role_name)
                                    if re.findall(config_name, current_role_name):
                                        print('permissions can be compared')
                                        print("name -", config_name, ", current_role_name -", current_role_name)
                                        print('trying to read: ')
                                        try:  # in case there errors were written to the file somehow on the previous iterations
                                            with open(filename, 'r') as file:
                                                data = json.loads(file.read())
                                                print("data:", data)
                                        except Exception as e:
                                            print(e)

                                        else:
                                            if config_name == 'googleworkspace':
                                                relevant_config = compare_role_configs_google(current_result[0], data)
                                                print()
                                                print('!***************This is relevant googleworkspace config:')
                                                print(relevant_config)
                                                print('***************')
                                                print()
                                                with open(filename, 'w+') as file:
                                                    json.dump(relevant_config, file, indent=4)
                                            elif config_name == 'juneos':
                                                relevant_config = compare_role_configs_juneos(current_result[0], data)
                                                print()
                                                print('!***************This is relevant juneos config:')
                                                print(relevant_config)
                                                print('***************')
                                                print()
                                                with open(filename, 'w+') as file:
                                                    json.dump(relevant_config, file, indent=4)

                                            elif config_name == 'slack':  # doesn't work needs to be fixed
                                                relevant_config = compare_role_configs_google(current_result[0], data)
                                                print(relevant_config)
                                                with open(filename, 'w+') as file:
                                                    json.dump(relevant_config, file, indent=4)

                                            elif config_name == 'amazonconnect':
                                                relevant_config = compare_role_configs_google(current_result[0], data)
                                                print(relevant_config)
                                                with open(filename, 'w+') as file:
                                                    json.dump(relevant_config, file, indent=4)

                                        # items_list.append(f'{config_name}_config')
                                        print('this is items list:')
                                        print(items_list)
                                        print('@@@@@@@@@@@@@@@@@@@@@@@')
                                    else:
                                        print('^incomparable permissions, skipping')
                                        print('------------')

                            else:  # если на диске нет конфигов
                                service_name = re.split('-', current_role_name)[-1]
                                filename = f".\\roles_configs\\{jira_key}\\{position_title}\\{service_name}_config.json"

                                with open(filename, 'w+') as file:
                                    json.dump(current_result[0], file, indent=4)

                                print("ITEMS LIST IS EMPTY! config_name -", service_name, ", current_role_name -", current_role_name)
                                items_list.append(f'{service_name}_config.json')
                            pages_list += f"*[{current_role_name}|{current_role_url}]* : Validated. ✅\n"
                        else:
                            # print('not tupple, data: ', data)
                            pages_list += f"*[{current_role_name}|{current_role_url}]*: {current_result}\n"
                            pages_list += "–––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"
                    # =================================

                    # здесь обычные пермиссии
                    items_list = checking_config_for_service_existence(position_title=position_title, jira_key=jira_key)
                    pages_list += '\n\n'

                else:
                    if not next_level_checker:
                        pages_list += 'Current role permissions:\n'
                        next_level_checker = True
                    # составляем лист всех конфигов которые у нас уже есть в виде списка []
                    # print(f"{permissions_for_persona_list[i]['id']} --- {type(permissions_for_persona_list[i])}, this is a regular normal permission")
                    try:
                        print()
                        print('items_list for normal permissions:')
                        print(items_list)
                        print()
                    except:
                        items_list = []
                    else:
                        # запрашиваем из ноушена след. по списку пермиссию
                        permission_id = permissions_for_persona_list[i]['id']  # id сравниваемой пермиссии
                        permission_name = get_notion_page_title(permission_id).json()['properties']['Name']['title'][0]['plain_text']
                        permission_url = get_notion_page_title(permission_id).json()['url']
                        service_name = re.split('-', permission_name)[-1]
                        filename = f".\\roles_configs\\{jira_key}\\{position_title}\\{service_name}_config.json"

                        print('permission_name:', permission_name, "; service_name:", service_name)
                        permission_config = notion_search_for_permission_block_children(permission_id)
                        print('permission_config:', permission_config)

                        # т.е. конфиг валидный
                        if type(permission_config) == tuple:
                            if len(items_list) != 0:
                                for i in range(len(items_list)):
                                    print("valid config has found ✅")
                                    print('items_list -', items_list)
                                    print('service_name from notion -', service_name)
                                    print('permission_name -', permission_name)
                                    print('permissions_history_check -', permissions_history_check)

                                    if service_name in permissions_history_check:
                                        print(f'"{service_name}" found in {permissions_history_check}, skipping - was already updated...')
                                        continue
                                    else:
                                        print(service_name, "<->", items_list[i], "comparing...")
                                        if re.findall(service_name, items_list[i]):  # если они одинаковые
                                            print('нашли такую пермиссию в списке файлов на диске')
                                            pages_list += comparing_permission_from_notion_vs_config_on_disk(
                                                filename=filename,
                                                permission_config=permission_config,
                                                permission_name=permission_name,
                                                permission_url=permission_url,
                                                service_name=service_name
                                            )
                                        else:
                                            # когда разные сервисы
                                            print('НЕ нашли такую пермиссию в списке файлов на диске - проверяем обновлялась ли она уже?')
                                            print(permissions_history_check)
                                            if service_name in permissions_history_check:
                                                print(f'"{service_name}" found in {permissions_history_check}, passing..., т.е. уже обновлялась')
                                                continue
                                            else:
                                                pages_list += comparing_permission_from_notion_vs_config_on_disk(
                                                    filename=filename,
                                                    permission_config=permission_config,
                                                    permission_name=permission_name,
                                                    permission_url=permission_url,
                                                    service_name=service_name
                                                )

                                    permissions_history_check.append(service_name)

                            # это если список пустой, т.е.никаких пермиссий не добавлено
                            else:
                                with open(filename, 'w+') as file:
                                    # json.dump('{"test": 1}', file, indent=4)
                                    json.dump(permission_config[0], file, indent=4)
                                    pages_list += f"*[{permission_name}|{permission_url}]*: successfully written.✅\n"
                                    print(f"Permission '{filename}' is successfully written on the disc")

                        # т.е. если конфиг невалидный
                        else:  #
                            # print('current_result:', permission_config, "- invalid config")
                            print("invalid config")
                            pages_list += f"*[{permission_name}|{permission_url}]*: {permission_config}\n"
                            pages_list += "⬆️Permission is skipped during building *Permissions Tree*!\n"
                            pass

            print()

            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            print(pages_list)
            print()
            print(f"Length of the message for test purposes: {len(pages_list)}")
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

            send_jira_comment(message=f"Summary after reviewing permissions for *{position_title}* persona:\n{pages_list}"
                                      f"Time taken: {round(time.time() - t0, 1)}"
                                      f"*P.S. Remember to move ticket to \"Done\" / \"Rejected\" to rebuild config.*", jira_key=jira_key)

    del permissions_history_check

# revoke tasks  https://docs.celeryq.dev/en/stable/userguide/workers.html#revoke-revoking-tasks
#               https://stackoverflow.com/questions/8920643/cancel-an-already-executing-task-with-celery
#
# in celery it's impossible to  delete the received task wo using a flower GUI. you can only flag it as revoked which means it will immediately marked as revoked when ETA
# passes.
# to  revoke the task:
# - in python console:
# >>> from tasks import celery_app
# >>> a = celery_app.control.inspect()
# >>> a.scheduled()
# identify the id of the task
# celery_app.control.revoke('c944ee91-d4e7-4733-a82b-2dbdaef7c809')

#
# @celery_app.task
# def add(x, y):
#     time.sleep(600)
#     return x + y
#
#
# @celery_app.task
# def multiply():
#     try:
#         print(f'inside a celery task')
#         time.sleep(5)
#     except Exception as e:
#         return e
#     else:
#         return send_gmail_message.apply_async(
#                             ('ilya.konovalov@junehomes.com',
#                              ['ilia19945@mail.ru'],
#                              [],
#                              'test',
#                              'finaldraft',
#                              round(1 / 3600)),
#                             queue='new_emps',
#                             countdown=round(1))

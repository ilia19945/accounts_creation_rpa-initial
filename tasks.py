import json
import os

import boto3

from funcs import gmail_app_password, send_jira_comment, notion_search_for_role, notion_search_for_permission_block_children, get_notion_page_title
from celery import Celery

from email.mime.text import MIMEText
import smtplib
import fast_api_logging as fl

celery_app = Celery('tasks', backend='redis://localhost', broker='redis://localhost', queue='new_emps,terminations,other')
celery_app.conf.broker_transport_options = {'visibility_timeout': 2592000} #30 days
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
                # return send_gmail_message.apply_async(
                #     ('ilya.konovalov@junehomes.com',
                #      [suggested_email],
                #      ['idelia@junehomes.com', 'ivan@junehomes.com', 'artyom@junehomes.com', 'maria.zhuravleva@junehomes.com'],
                #      'Access to Amazon Connect call center',
                #      final_draft,
                #      round(unix_countdown_time / 3600)),
                #     queue='new_emps',
                #     countdown=round(unix_countdown_time + 120))

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


@celery_app.task
def check_role_permissions(position_title, jira_key):

    send_jira_comment(f'*Celery task* to check permissions of *"{position_title}"* is added.\n'
                      'Please, wait...', jira_key)

    permissions_for_persona_list = notion_search_for_role(position_title, jira_key=jira_key)  # the list of page_ids
    if not permissions_for_persona_list:
        print(f'Permissions are not added for {position_title}!')
        send_jira_comment(f'Permissions are not added for *{position_title}* position ❌', jira_key=jira_key)
        return  # ⚠️ ⚠️ ⚠️stops the main flow!
    else:
        # trying to create a directory for this role:
        path = os.path.join(f".\\roles_configs\\{jira_key}", position_title)
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
                    with open(f".\\roles_configs\\{jira_key}\\{position_title}\\{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['properties']['Name']['title'][0]['plain_text']}.json", 'w+') as file:
                        file.write(str(json.dumps(result[0])))
                else:
                    pages_list += f"[{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['properties']['Name']['title'][0]['plain_text']}|" \
                                  f"{get_notion_page_title(permissions_for_persona_list[i]['id']).json()['url']}]: *{result}*\n"
            except Exception as e:
                print(e)
        # print(pages_list)
        send_jira_comment(message=f"The summary after reviewing permissions for {position_title} persona:\n{pages_list}", jira_key=jira_key)



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

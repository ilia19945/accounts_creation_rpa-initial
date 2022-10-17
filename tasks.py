import json
import os
import time
from pprint import pprint
import re
import boto3

from config import email_cc_list
from funcs import gmail_app_password, send_jira_comment, notion_search_for_role, notion_search_for_permission_block_children, get_notion_page_title, compare_permissions_by_name, full_compare_by_name_and_permissions_with_file, checking_config_for_service_existence, compare_role_configs_google, \
    comparing_permission_from_notion_vs_config_on_disk
from celery import Celery

from email.mime.text import MIMEText
import smtplib
import fast_api_logging as fl

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


@celery_app.task
def new_check_role_and_permissions(position_title, jira_key):
    t0 = time.time()
    send_jira_comment('A request to build a role config is sent to *Celery*. PLease, wait...', jira_key=jira_key)
    permissions_history_check = []
    permissions_for_persona_list = notion_search_for_role(position_title, jira_key=jira_key)  # the list of page_ids

    if len(permissions_for_persona_list) == 0:  # если пермиссии для персоны не добавлены!
        print(f'Permissions are not added for {position_title}!')
        # send_jira_comment(f'Permissions are not added for *{position_title}* position ❌', jira_key=jira_key)
        # return  # ⚠️ ⚠️ ⚠️stops the main flow!
    else:

        # trying to create a directory for this role:
        path = os.path.join(f".\\roles_configs\\{jira_key}", position_title)
        mode = 0o666
        os.makedirs(path, mode)

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
            # пока только для гугла, потом написать конфиги для остальных сервисов
            if type(current_permissions_set) == list and type(antecedent_permissions_set) == list:  # здесь имеем сет из пермиссий, каждый из которых нужно сравнить с предыдущим, с конца*
                # # print(f"{permissions_for_persona_list[i]} --- {type(*permissions_for_persona_list[i])}, this is a nested permissions")
                # # print(current_permissions_set[0])
                # # print(antecedent_permissions_set[0])
                print("current and previous permissions sets are both type 'List'")

                # ================================================
                # ВСЕ РАБОТАЕТ УРА!!! ПРОСТО РАСКОММЕНТИТЬ ТО ЧТО МЕЖДУ ===
                #
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

                            relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                                config_name='googleworkspace',
                                antecedent_permissions_set=antecedent_permissions_set,
                                jira_key=jira_key,
                                position_title=position_title,
                                current_json_object=current_json_object,
                                pages_list=pages_list,
                                current_role_name=current_role_name)

                        elif re.findall('amazonconnect', current_role_name):

                            relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                                config_name='amazonconnect',
                                antecedent_permissions_set=antecedent_permissions_set,
                                jira_key=jira_key,
                                position_title=position_title,
                                current_json_object=current_json_object,
                                pages_list=pages_list,
                                current_role_name=current_role_name)

                        elif re.findall('juneos', current_role_name):

                            relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                                config_name='juneos',
                                antecedent_permissions_set=antecedent_permissions_set,
                                jira_key=jira_key,
                                position_title=position_title,
                                current_json_object=current_json_object,
                                pages_list=pages_list,
                                current_role_name=current_role_name)
                        elif re.findall('frontapp', current_role_name):

                            relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                                config_name='frontapp',
                                antecedent_permissions_set=antecedent_permissions_set,
                                jira_key=jira_key,
                                position_title=position_title,
                                current_json_object=current_json_object,
                                pages_list=pages_list,
                                current_role_name=current_role_name)

                        elif re.findall('slack', current_role_name):

                            relevant_config, pages_list = full_compare_by_name_and_permissions_with_file(
                                config_name='slack',
                                antecedent_permissions_set=antecedent_permissions_set,
                                jira_key=jira_key,
                                position_title=position_title,
                                current_json_object=current_json_object,
                                pages_list=pages_list,
                                current_role_name=current_role_name)

                        else:
                            print('else:', current_role_name)
                            relevant_config = False
                            pass
                    # print('-----end-iter-----')
                # ================================================
                pass

            # здесь текущий лист, а за ним уже корневые пермиссии
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
                        role_title=position_title,
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

                    if type(current_result) == tuple:
                        # print(data)
                        # if data != 'False':
                        print('data in the config != false')
                        for i in range(len(items_list)):
                            config_name = re.split('_', items_list[i])[0]
                            print("config_name -", config_name, ", current_role_name -", current_role_name)
                            if re.findall(config_name, current_role_name):
                                print('permissions can be compared')
                                print("name -", config_name, ", current_role_name -", current_role_name)
                                filename = f".\\roles_configs\\{jira_key}\\{position_title}\\{config_name}_config.json"
                                print('trying to read: ')
                                try:
                                    with open(filename, 'r') as file:
                                        data = json.loads(file.read())
                                        print("data:", data)
                                except Exception as e:
                                    print(e)

                                else:
                                    if config_name == 'googleworkspace':
                                        relevant_config = compare_role_configs_google(current_result[0], data)
                                        print()
                                        print('======== this is relevant config')
                                        print(relevant_config)
                                        print('========')
                                        print()
                                        with open(filename, 'w+') as file:
                                            json.dump(relevant_config, file, indent=4)

                                    elif config_name == 'slack':
                                        relevant_config = compare_role_configs_google(current_result[0], data)
                                        print(relevant_config)
                                        with open(filename, 'w+') as file:
                                            json.dump(relevant_config, file, indent=4)

                                    elif config_name == 'amazonconnect':
                                        relevant_config = compare_role_configs_google(current_result[0], data)
                                        print(relevant_config)
                                        with open(filename, 'w+') as file:
                                            json.dump(relevant_config, file, indent=4)
                            else:
                                print('^incomparable permissions, skipping')
                                print('------------')

                        pages_list += f"*[{current_role_name}|{current_role_url}]* : Validated. ✅\n"
                    else:
                        # print('not tupple, data: ', data)
                        print('current_result:', current_result)
                        pages_list += f"*[{current_role_name}|{current_role_url}]*: {current_result}\n"
                        pages_list += "–––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"
                # =================================

                # здесь обычные пермиссии
                items_list = checking_config_for_service_existence(role_title=position_title, jira_key=jira_key)
                pages_list += '\n\n'
            else:
                # составляем лист всех конфигов которые у нас уже есть в виде списка []
                # print(f"{permissions_for_persona_list[i]['id']} --- {type(permissions_for_persona_list[i])}, this is a regular normal permission")

                print()
                print('items_list for normal permissions:')
                print(items_list)
                print()

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
                                        pages_list=pages_list,
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
                                            pages_list=pages_list,
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
                            print("успешно записали", filename)


                # т.е. если конфиг невалидный
                else:  #
                    # print('current_result:', permission_config, "- invalid config")
                    print("invalid config")
                    pages_list += f"*[{permission_name}|{permission_url}]*: {permission_config}\n"
                    pages_list += "⬆️Permission is skipped during building *Permissions Tree*!\n"
                    pass

        print()

        print('+++++++++++++++++++++++++++++++++++++')
        print(pages_list)
        print()
        print()
        print(len(pages_list))
        print('+++++++++++++++++++++++++++++++++++++')

        send_jira_comment(message=f"Summary after reviewing permissions for *{position_title}* persona:\n"
                                  f"{pages_list}.\n"
                                  f"Time taken: *{round(time.time() - t0, 2)} secs.*\n"
                                  f"*P.S. Remember to move ticket to \"Done\" / \"Rejected\" if the config needs to be rebuilt.*", jira_key=jira_key)

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

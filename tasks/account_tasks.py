"""
Account provisioning Celery tasks.

Covers:
  - Amazon Connect user creation
  - Notion-based role/permission checks
  - Zendesk login activation
  - Utility task (add)
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from pprint import pprint

import boto3

import app.utils.logging as fl
from app.services.jira import send_jira_comment
from app.services.zendesk import enable_zendesk_login
from config import email_cc_list, instance_id  # legacy constants — not yet in app.config
from funcs import (  # TODO: extract remaining helpers to dedicated service modules
    checking_config_for_service_existence,
    compare_permissions_by_name,
    compare_role_configs_google,
    compare_role_configs_juneos,
    comparing_permission_from_notion_vs_config_on_disk,
    full_compare_by_name_and_permissions_with_file,
    get_notion_page_title,
    notion_search_for_permission_block_children,
    notion_search_for_role,
)

from tasks.celery_app import celery_app
from tasks.email_tasks import send_gmail_message

data_folder = Path(".")


# ---------------------------------------------------------------------------
# Amazon Connect
# ---------------------------------------------------------------------------

@celery_app.task
def create_amazon_user(
    suggested_email,
    first_name,
    last_name,
    user_email_analogy,
    password,
    final_draft,
    hire_start_date,
    jira_key,
) -> bool:
    client = boto3.client('connect')
    hire_start_date = datetime.strptime(hire_start_date, '%Y-%m-%dT%H:%M:%S.%f')

    def check_amazon_user(email: str) -> dict:
        return client.search_users(
            InstanceId=instance_id,
            MaxResults=100,
            SearchCriteria={
                'StringCondition': {
                    'FieldName': 'Username',
                    'Value': email.split('@')[0] + '@',
                    'ComparisonType': 'CONTAINS',
                },
            },
        )

    send_jira_comment(
        f'*Celery task* to create *Amazon account* for *"{suggested_email}"* is added.\n'
        'Please, wait...',
        jira_key,
    )

    check_for_user_analogy_existence = check_amazon_user(user_email_analogy)
    if check_for_user_analogy_existence['ApproximateTotalCount'] != 1:
        print('total people with this email found:', check_for_user_analogy_existence['ApproximateTotalCount'])
        send_jira_comment(
            f'Cannot copy permissions from != 1 user for {suggested_email}.\n'
            f'Found *{check_for_user_analogy_existence["ApproximateTotalCount"]}* users with *{user_email_analogy}*.\n '
            f'Please, double-check the email in the config.',
            jira_key,
        )
        return False

    user_analogy = check_for_user_analogy_existence['Users'][0]
    print('user_analogy successfully found')
    described_user_analogy = client.describe_user(
        UserId=user_analogy['Id'], InstanceId=instance_id
    )
    pprint(described_user_analogy)

    check_if_requested_user_exist = check_amazon_user(suggested_email)
    if check_if_requested_user_exist['ApproximateTotalCount'] != 0:
        print(f'total people with this email found, probably its already created: '
              f'{check_for_user_analogy_existence["ApproximateTotalCount"]}')
        send_jira_comment(
            f'Total people with *{suggested_email}* email found: *{check_for_user_analogy_existence["ApproximateTotalCount"]}*.\n'
            'Probably the user is already created?',
            jira_key,
        )
        return False

    print('requested user doesnt exist')
    try:
        create_user = client.create_user(
            Username=suggested_email.split("@")[0] + "@usrentapts.com",
            Password=password,
            IdentityInfo={
                'FirstName': first_name,
                'LastName': last_name,
                'Email': suggested_email.split("@")[0] + "@usrentapts.com",
            },
            PhoneConfig={
                'PhoneType': described_user_analogy['User']['PhoneConfig']['PhoneType'],
                'AutoAccept': described_user_analogy['User']['PhoneConfig']['AutoAccept'],
                'AfterContactWorkTimeLimit': 60,
            },
            SecurityProfileIds=described_user_analogy['User']['SecurityProfileIds'],
            RoutingProfileId=described_user_analogy['User']['RoutingProfileId'],
            InstanceId=instance_id,
            Tags={},
        )
        fl.info(create_user)
        fl.info(
            f'Amazon account for *{suggested_email}* — '
            f'{suggested_email.split("@")[0] + "@usrentapts.com"} is created.'
        )
    except Exception as error:
        fl.error(msg=error)
        send_jira_comment(
            f'An error occurred while creating *Amazon account*:\n\n*{error}*',
            jira_key=jira_key,
        )
        return False
    else:
        with open('User Accounts.txt', 'a', encoding='utf-8') as f:
            f.write(
                f"Amazon username: {suggested_email.split('@')[0] + '@usrentapts.com'}\n"
                f"Password: {password}\n\n"
            )
        fl.info(
            '*Amazon account* is created successfully!\n'
            f'An email with Amazon account credentials will be sent to {suggested_email}'
        )
        send_jira_comment(
            '*Amazon account* is created successfully!\n'
            f'An email with Amazon account credentials will be sent to *{suggested_email}* '
            f'At *{hire_start_date}* UTC.\n',
            jira_key=jira_key,
        )
        return send_gmail_message.apply_async(
            ('ilya.konovalov@junehomes.com', [suggested_email], email_cc_list,
             'Access to Amazon Connect call center', final_draft, hire_start_date),
            queue='new_emps',
            eta=hire_start_date + timedelta(minutes=2),
        )


# ---------------------------------------------------------------------------
# Role / permission checks (Notion-backed)
# ---------------------------------------------------------------------------

@celery_app.task
def check_role_permissions(role_title, jira_key):
    """Legacy role permissions checker (kept for compatibility)."""
    send_jira_comment(
        f'*Celery task* to check permissions of *"{role_title}"* is added.\nPlease, wait...',
        jira_key,
    )

    permissions_for_persona_list = notion_search_for_role(role_title, jira_key=jira_key)
    if not permissions_for_persona_list:
        print(f'Permissions are not added for {role_title}!')
        send_jira_comment(
            f'Permissions are not added for *{role_title}* role ❌', jira_key=jira_key
        )
        return

    path = data_folder / 'roles_configs' / jira_key / role_title
    Path(path).mkdir(mode=511, parents=True, exist_ok=True)
    pages_list = ''
    for i in range(len(permissions_for_persona_list)):
        page_id = permissions_for_persona_list[i]['id']
        page_title = (
            get_notion_page_title(page_id)
            .json()['properties']['Name']['title'][0]['plain_text']
        )
        print(f"Reviewing {i + 1} / {len(permissions_for_persona_list)} permissions... ({page_title})")
        try:
            result = notion_search_for_permission_block_children(page_id)
            page_url = get_notion_page_title(page_id).json()['url']
            if isinstance(result, tuple):
                pages_list += f"[{page_title}|{page_url}]: Validated, Good Job! ✅ \n"
                file_to_open = (
                    data_folder / 'roles_configs' / jira_key / role_title / f'{page_title}.json'
                )
                with open(file_to_open, 'w+') as file:
                    file.write(str(json.dumps(result[0])))
            else:
                pages_list += f"[{page_title}|{page_url}]: *{result}*\n"
        except Exception as e:
            print(e)

    send_jira_comment(
        message=f"The summary after reviewing permissions for {role_title} persona:\n{pages_list}",
        jira_key=jira_key,
    )


@celery_app.task
def new_check_role_and_permissions(role_title, jira_key):
    """Full multi-level role permission builder using Notion data."""
    position_title = role_title
    t0 = time.time()
    send_jira_comment(
        'A request to build a role config is sent to *Celery*. PLease, wait...\n '
        'P.s. if there are lots of permissions and dependent roles it might take up to a few min.',
        jira_key=jira_key,
    )
    permissions_history_check = []
    permissions_for_persona_list = notion_search_for_role(position_title, jira_key=jira_key)

    print('+++++++++++++++++++')
    print('Permissions list to check (reversed):')
    try:
        pprint(list(reversed(permissions_for_persona_list)))
        print('+++++++++++++++++++')

        if len(permissions_for_persona_list) == 0:
            print(f'Permissions are not added for {position_title}!')
            send_jira_comment(
                f'Permissions are not added for *{position_title}* position ❌', jira_key=jira_key
            )
            return

        next_level_checker = False
        path = data_folder / 'roles_configs' / jira_key / position_title
        Path(path).mkdir(mode=511, parents=True, exist_ok=True)
        pages_list = ''
        items_list = []

        for i in range(len(permissions_for_persona_list)):
            print('******')
            print('current iteration is:', i, 'permissions list len:', len(permissions_for_persona_list))
            print('******')

            try:
                current_permissions_set = permissions_for_persona_list[i]
                antecedent_permissions_set = permissions_for_persona_list[i + 1]
                print('current_permissions_set', current_permissions_set)
                print('antecedent_permissions_set', antecedent_permissions_set)
            except IndexError as e:
                print('This is the last iteration! End of list reached. Error:', e)

            # Both levels are lists → nested permission sets
            if isinstance(current_permissions_set, list) and isinstance(antecedent_permissions_set, list):
                print('******')
                print("current and previous permissions sets are both type 'List'")
                print('******')

                for p in range(len(current_permissions_set[0])):
                    pages_list, current_role_name, current_json_object = compare_permissions_by_name(
                        permissions_set=current_permissions_set,
                        pages_list=pages_list,
                        iterator=p,
                        level=1,
                        jira_key=jira_key,
                        position_title=position_title,
                    )
                    if not current_json_object:
                        print('there is an error in the document', current_json_object)
                        pages_list += (
                            "–––– ⬆️Permission is skipped during building *Permissions Tree*! "
                            "Fix the error, otherwise the permissions tree may not be complete.\n"
                        )
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
                            continue

                        print(f'role_name_for_comparison — {file_role_name_for_comparison}')
                        _, pages_list = full_compare_by_name_and_permissions_with_file(
                            config_name=file_role_name_for_comparison,
                            antecedent_permissions_set=antecedent_permissions_set,
                            jira_key=jira_key,
                            position_title=position_title,
                            current_json_object=current_json_object,
                            pages_list=pages_list,
                            current_role_name=current_role_name,
                        )

            # Current is list, antecedent is dict → transition level
            elif isinstance(current_permissions_set, list) and isinstance(antecedent_permissions_set, dict):
                print('******')
                print("current permissions set is 'list' while the previous is 'dict'")
                print('******')
                pages_list += '\n'

                try:
                    items_list = checking_config_for_service_existence(
                        position_title=position_title, jira_key=jira_key,
                    )
                except Exception as e:
                    print(f"Error occurred on: {e}")
                print(items_list)

                for p in range(len(current_permissions_set[0])):
                    current_permission_id = current_permissions_set[0][p]['id']
                    current_role_name = (
                        get_notion_page_title(current_permission_id)
                        .json()['properties']['Name']['title'][0]['plain_text']
                    )
                    current_role_url = get_notion_page_title(current_permission_id).json()['url']
                    print('current_role_name:', current_role_name)

                    current_result = notion_search_for_permission_block_children(current_permission_id)
                    print('current_result type:', type(current_result))

                    if isinstance(current_result, tuple):
                        print('data in the config != false')
                        if len(items_list) != 0:
                            print("ITEMS LIST HAS CONFIGS!")
                            for idx in range(len(items_list)):
                                config_name = re.split('_', items_list[idx])[0]
                                filename = (
                                    data_folder / 'roles_configs' / jira_key
                                    / position_title / f"{config_name}_config.json"
                                )
                                print(f"config_name — {config_name}, current_role_name — {current_role_name}")
                                if re.findall(config_name, current_role_name):
                                    print('permissions can be compared')
                                    try:
                                        with open(filename, 'r') as file:
                                            data = json.loads(file.read())
                                    except Exception as e:
                                        print(e)
                                    else:
                                        if config_name == 'googleworkspace':
                                            relevant_config = compare_role_configs_google(current_result[0], data)
                                        elif config_name == 'juneos':
                                            relevant_config = compare_role_configs_juneos(current_result[0], data)
                                        elif config_name in ('slack', 'amazonconnect'):
                                            relevant_config = compare_role_configs_google(current_result[0], data)
                                        else:
                                            continue
                                        print(relevant_config)
                                        with open(filename, 'w+') as file:
                                            json.dump(relevant_config, file, indent=4)
                                else:
                                    print('^incomparable permissions, skipping')
                        else:
                            service_name = re.split('-', current_role_name)[-1]
                            filename = (
                                data_folder / 'roles_configs' / jira_key
                                / position_title / f"{service_name}_config.json"
                            )
                            with open(filename, 'w+') as file:
                                json.dump(current_result[0], file, indent=4)
                            print("ITEMS LIST IS EMPTY! config_name —", service_name)
                            items_list.append(f'{service_name}_config.json')

                        pages_list += f"*[{current_role_name}|{current_role_url}]* : Validated. ✅\n"
                    else:
                        pages_list += f"*[{current_role_name}|{current_role_url}]*: {current_result}\n"
                        pages_list += (
                            "–––– ⬆️Permission is skipped during building *Permissions Tree*! "
                            "Fix the error, otherwise the permissions tree may not be complete.\n"
                        )

                items_list = checking_config_for_service_existence(
                    position_title=position_title, jira_key=jira_key
                )
                pages_list += '\n\n'

            # Root level — both are dicts
            else:
                if not next_level_checker:
                    pages_list += 'Current role permissions:\n'
                    next_level_checker = True
                try:
                    print(
                        f"{permissions_for_persona_list[i]['id']} — "
                        f"{type(permissions_for_persona_list[i])}, regular current permission"
                    )
                except (IndexError, Exception) as e:
                    print(f'Error printing antecedent_permissions_set: {e}')

                try:
                    print('\nitems_list for normal permissions:', items_list, '\n')
                except Exception:
                    items_list = []

                permission_id = permissions_for_persona_list[i]['id']
                permission_name = (
                    get_notion_page_title(permission_id)
                    .json()['properties']['Name']['title'][0]['plain_text']
                )
                permission_url = get_notion_page_title(permission_id).json()['url']
                service_name = re.split('-', permission_name)[-1]
                filename = (
                    data_folder / 'roles_configs' / jira_key
                    / position_title / f"{service_name}_config.json"
                )
                print('permission_name:', permission_name, '; service_name:', service_name)
                permission_config = notion_search_for_permission_block_children(permission_id)
                print('permission_config:', permission_config)

                if isinstance(permission_config, tuple):
                    if len(items_list) != 0:
                        for idx in range(len(items_list)):
                            print("valid config found ✅")
                            if service_name in permissions_history_check:
                                print(f'"{service_name}" already updated, skipping...')
                                continue
                            if re.findall(service_name, items_list[idx]):
                                pages_list += comparing_permission_from_notion_vs_config_on_disk(
                                    filename=filename,
                                    permission_config=permission_config,
                                    permission_name=permission_name,
                                    permission_url=permission_url,
                                    service_name=service_name,
                                )
                            else:
                                if service_name not in permissions_history_check:
                                    pages_list += comparing_permission_from_notion_vs_config_on_disk(
                                        filename=filename,
                                        permission_config=permission_config,
                                        permission_name=permission_name,
                                        permission_url=permission_url,
                                        service_name=service_name,
                                    )
                            permissions_history_check.append(service_name)
                    else:
                        with open(filename, 'w+') as file:
                            json.dump(permission_config[0], file, indent=4)
                        pages_list += f"*[{permission_name}|{permission_url}]*: successfully written.✅\n"
                        print(f"Permission '{filename}' successfully written")
                else:
                    print("invalid config")
                    pages_list += f"*[{permission_name}|{permission_url}]*: {permission_config}\n"
                    pages_list += "⬆️Permission is skipped during building *Permissions Tree*!\n"

            print()
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            print(pages_list)
            print(f"Message length: {len(pages_list)}")
            print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')

        send_jira_comment(
            message=(
                f"Summary after reviewing permissions for *{position_title}* persona:\n{pages_list}"
                f"Time taken: *{round(time.time() - t0, 1)} secs.*\n"
                "*P.S. Remember to move ticket to \"Done\" / \"Rejected\" to rebuild config.*"
            ),
            jira_key=jira_key,
        )
        del permissions_history_check

    except Exception as e:
        print('Couldn\'t process permissions list:', e)
        send_jira_comment(message=e, jira_key=jira_key)


# ---------------------------------------------------------------------------
# Zendesk
# ---------------------------------------------------------------------------

@celery_app.task(serializer='json')
def check_zendesk_login(user_email: str, access_token: str, jira_key: str) -> dict:
    """Celery wrapper around :func:`app.services.zendesk.enable_zendesk_login`."""
    return enable_zendesk_login(user_email, access_token, jira_key)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

@celery_app.task
def add(x, y):
    return x + y

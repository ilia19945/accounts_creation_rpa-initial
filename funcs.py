import json
import re
import time

import boto3
import requests
import string
import random
import os
from email.mime.text import MIMEText
import base64
from pprint import pprint
import fast_api_logging as fl
from pathlib import Path

import funcs

data_folder = Path(".")

# hidden variables in OS
google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
jira_api = os.environ.get('JIRA_API')
frontapp_api = os.environ.get('FRONTAPP_API')
gmail_app_password = os.environ.get('GMAIL_APP_PASSWORD')
juneos_dev_password = os.environ.get('JUNEOS_DEV_PASSWORD')
juneos_prod_login = os.environ.get('JUNEOS_PROD_LOGIN')
juneos_prod_password = os.environ.get('JUNEOS_PROD_PASSWORD')
elk_prod = os.environ.get('ELK_DEV')
elk_dev = os.environ.get('ELK_PROD')
notion_secret = os.environ.get('NOTION_SECRET')


def get_app_info(arg):
    with open('client_secret.json') as data:
        json_value = json.load(data)['web'][arg]
        return json_value


# returns the actual token
def get_actual_token(arg):
    with open(r'''access_refresh_tokens.json''') as data:
        # open the file and parse it to the latest json
        newest_data = data.read().split('\n')[-2]
        token = json.loads(newest_data)[arg]
        return token


"""make the http request to refresh the token Step 2:
https://developers.google.com/identity/protocols/oauth2/web-server#redirecting
scopes explanation https://developers.google.com/identity/protocols/oauth2/scopes#admin-directory"""


def get_new_access_token():
    refresh_access_token_request = 'https://accounts.google.com/o/oauth2/v2/auth?' \
                                   'scope=https://www.googleapis.com/auth/admin.directory.user' \
                                   '+https://www.googleapis.com/auth/apps.licensing' \
                                   '+https://www.googleapis.com/auth/admin.directory.group.member' \
                                   '+https://www.googleapis.com/auth/admin.directory.orgunit' \
                                   '+https://mail.google.com/' \
                                   '+https://www.googleapis.com/auth/gmail.modify' \
                                   '+https://www.googleapis.com/auth/gmail.compose' \
                                   '+https://www.googleapis.com/auth/gmail.send' \
                                   '+https://www.googleapis.com/auth/admin.directory.userschema' \
                                   '+https://www.googleapis.com/auth/calendar&' \
                                   'access_type=offline&' \
                                   'include_granted_scopes=true&' \
                                   'response_type=code&' \
                                   f'redirect_uri={get_app_info("redirect_uris")[0]}&' \
                                   f'client_id={get_app_info("client_id")}'
    return refresh_access_token_request


""" Step 5: Exchange authorization code for refresh and access tokens
https://developers.google.com/identity/protocols/oauth2/web-server#exchange-authorization-code"""


def exchange_auth_code_to_access_refresh_token(code):
    request_row = 'https://oauth2.googleapis.com/token?' \
                  f'code={code}&' \
                  f'client_id={get_app_info("client_id")}&' \
                  f'client_secret={get_app_info("client_secret")}&' \
                  f'redirect_uri={get_app_info("redirect_uris")[0]}&' \
                  'grant_type=authorization_code'
    response = requests.post(request_row)  # send and receives response

    fl.info(response.json())  # receives body in dict
    refreshed_token = response.json()
    if refreshed_token.get("error") is None:
        refreshed_token['datetime'] = str(int(time.time()))  # append datetime to dict
        refreshed_token = json.dumps(refreshed_token)  # convert dict to json
        # write json to the end of the file
        with open('access_refresh_tokens.json', 'a') as file:
            file.write(str(refreshed_token) + '\n')
        return

    else:
        print('Error received')
        fl.info(response)
        return response


# initiates the refreshing token process WHEN WE HAVE REFRESH TOKEN in the latest google response
# https://developers.google.com/identity/protocols/oauth2/web-server#offline
def refresh_token_func():
    refresh_request = f'{get_app_info("token_uri")}?' \
                      f'client_id={get_app_info("client_id")}' \
                      f'&client_secret={get_app_info("client_secret")}' \
                      f'&refresh_token={get_actual_token("refresh_token")}' \
                      '&grant_type=refresh_token'
    refreshed_token = requests.post(refresh_request)  # send and receives response

    refreshed_token = refreshed_token.json()
    refreshed_token['datetime'] = str(int(time.time()))  # append datetime to dict
    refreshed_token = json.dumps(refreshed_token)  # convert dict to json
    # write json to the end of the file
    file = open('access_refresh_tokens.json', 'a')
    file.write(str(refreshed_token) + '\n')

    file.close()
    fl.info('access_refresh_tokens.json - appended!\nRefresh token was exchanged successfully.')


# https://developers.google.com/admin-sdk/directory/v1/guides/manage-users
def create_google_user_req(first_name, last_name, suggested_email, organizational_unit):
    global google_password
    characters = string.ascii_letters + string.digits + string.punctuation
    google_password = ''.join(random.choice(characters) for i in range(8))
    """google response with another status which means that the account is not can be created."""

    # fl.info(f"{first_name} {last_name}\nUsername: {suggested_email}\nPassword: {password}\n\n")
    fl.info(f"{first_name} {last_name}\nUsername: {suggested_email}")
    url = 'https://admin.googleapis.com/admin/directory/v1/users/'
    headers = {
        'Authorization': f'Bearer {get_actual_token("access_token")}'
    }
    payload = json.dumps({
        "primaryEmail": f"{suggested_email}",
        "name": {
            "givenName": f"{first_name}",
            "familyName": f"{last_name}",
            "fullName": f"{first_name} {last_name}"
        },
        "password": f"{google_password}",
        "isAdmin": False,
        "isDelegatedAdmin": False,
        "agreedToTerms": True,
        "suspended": False,
        "changePasswordAtNextLogin": False,
        "ipWhitelisted": False,
        "includeInGlobalAddressList": True,
        "orgUnitPath": f"/Root OU/{organizational_unit}"
    })
    # print(payload)
    response = requests.post(url,
                             headers=headers,
                             data=payload)
    if response.status_code < 300:
        file = open(r'''User Accounts.txt''', 'a', encoding='utf-8')
        file.write(f"{first_name} {last_name}\nUsername: {suggested_email}\nPassword: {google_password}\n\n")
        file.close()
    elif response.status_code >= 500:
        fl.error(f"an error on the google side occurred while creating a google user:\n {str(response.json())}")
        return response.status_code, response.__dict__
    else:
        fl.error(f"an error occurred while creating a google user\n {str(response.json())}")
    return response.status_code, response.__dict__, google_password


# https://developers.google.com/admin-sdk/licensing/v1/how-tos/using
def assign_google_license(google_license_id, suggested_email):
    url = f"https://www.googleapis.com/apps/licensing/v1/product/Google-Apps/sku/{google_license_id}/user"
    payload = json.dumps({"userId": f"{suggested_email}"})
    headers = {'Authorization': f'Bearer {get_actual_token("access_token")}',
               'Content-Type': 'application/json'}
    assign_license = requests.post(url=url, headers=headers, data=payload)
    return assign_license.status_code, assign_license.__dict__


# https://developers.google.com/admin-sdk/directory/v1/guides/manage-group-members#create_member
def adding_user_to_google_group(gmail_groups_refined, suggested_email):
    payload = json.dumps({
        "email": suggested_email,
        "role": "MEMBER"})
    headers = {'Authorization': f'Bearer {get_actual_token("access_token")}',
               'Content-Type': 'application/json'}
    final_str = ''
    for i in gmail_groups_refined:
        url = f"https://admin.googleapis.com/admin/directory/v1/groups/{i}/members"
        # print(url)
        assign_google_group = requests.post(url=url, headers=headers, data=payload)
        if assign_google_group.status_code < 300:
            final_str += f"Gmail group *{str(i)}* assigning finished with status code: *{assign_google_group.status_code}* \n"
        else:
            final_str += f"Gmail group *{str(i)}* assigning finished with error code: *{assign_google_group.status_code}*. " \
                         f"Error: *{assign_google_group.json()['error']['message']}*\n"
    fl.info(f"(3/3) Assigned google groups:\n"
            f"{final_str}")
    return final_str


def adding_to_junehomes_dev_calendar(suggested_email, calendar_id):
    url = f'https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/acl'
    payload = json.dumps({
        "role": "writer",
        "scope": {
            "type": "user",
            "value": suggested_email
        }
    })
    headers = {'Authorization': f'Bearer {get_actual_token("access_token")}',
               'Accept': 'application/json',
               'Content-Type': 'application/json'
               }
    response = requests.post(url=url, headers=headers, data=payload)
    return response.status_code, response.json()


def adding_jira_cloud_user(suggested_email):
    # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-users/#api-rest-api-3-user-post
    url = "https://junehomes.atlassian.net/rest/api/3/user"

    payload = json.dumps({
        "emailAddress": suggested_email
    })
    headers = {
        'Authorization': jira_api,
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    return response.status_code, response.json()


def adding_jira_user_to_group(account_id, group_id):
    # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-groups/#api-rest-api-3-group-user-post
    url = f"https://junehomes.atlassian.net/rest/api/3/group/user?groupId={group_id}"

    payload = json.dumps({
        "accountId": account_id
    })
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': jira_api,
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    return response.status_code, response.json()


def send_jira_comment(message, jira_key):
    headers = {
        'Authorization': jira_api,
        'Content-Type': 'application/json'
    }
    if type(message) == dict:
        url = f'https://junehomes.atlassian.net/rest/api/3/issue/{jira_key}/comment'
        data = json.dumps(
            {"body": message})
    else:
        url = f'https://junehomes.atlassian.net/rest/api/2/issue/{jira_key}/comment'
        data = json.dumps(
            {"body": f"{message}"})
    jira_notification = requests.post(url=url, headers=headers, data=data)

    return jira_notification


def juneos_devprod_authorization(dev_or_prod):
    if dev_or_prod == 'dev':
        url = "https://dev.junehomes.net/api/v2/auth/login-web-token/"

        payload = json.dumps({
            "email": "ilya.konovalov@junehomes.com",  # на деве авторизация под моей учеткой
            "password": juneos_dev_password
        })
    elif dev_or_prod == 'prod':
        url = "https://junehomes.com/api/v2/auth/login-web-token/"

        payload = json.dumps({
            "email": juneos_prod_login,
            "password": juneos_prod_password
        })

    else:
        fl.error('check func params')
        return None

    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        return response
    except Exception as e:
        print("Error on sending a request to JuneOS:", e)
        fl.error(f'Status code:{response.status_code}\n'
                 f'{response.json()}')
        return response


def create_juneos_user(first_name, last_name, suggested_email, personal_phone, dev_or_prod):
    if dev_or_prod == 'dev':
        url = "https://dev.junehomes.net/api/v2/auth/registration/"
    elif dev_or_prod == 'prod':
        url = "https://junehomes.com/api/v2/auth/registration/"
    else:
        fl.error('check dev or prod param')
        return None
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'

    }

    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for i in range(35))
    fl.info(f'suggested_email: {suggested_email}')
    fl.debug(f'password: {password}')

    payload = json.dumps({
        "email": suggested_email,
        "first_name": first_name,
        "last_name": last_name,
        "phone": personal_phone,
        "password": password,
        "password2": password,
        "subscribe": True,
        "is_staff": True
    })

    juneos_user = requests.post(url=url, headers=headers, data=payload)
    return juneos_user


def get_juneos_groups_from_position_title(file_name):
    file_to_open = data_folder / 'permissions_by_orgunits' / file_name
    with open(file_to_open, "r") as data:
        groups_sales = json.loads(data.read())
        return groups_sales


def assign_groups_to_user(user_id, groups, dev_or_prod, csrftoken, sessionid, token):
    if dev_or_prod == 'prod':
        fl.info('assign_groups_to_user on prod was requested')
        url = f"https://junehomes.com/api/v2/auth/users/{user_id}/"
    elif dev_or_prod == 'dev':
        fl.info('assign_groups_to_user on dev was requested')
        url = f"https://dev.junehomes.net/api/v2/auth/users/{user_id}/"
    else:
        return 500, 'Error, wrong param dev_or_prod!'

    headers = {
        'Authorization': f'{token}',
        'Content-Type': 'application/json',
        'Cookie': f'csrftoken={csrftoken}; sessionid={sessionid}'
    }
    payload = json.dumps({
        "is_staff": True,
        "groups": groups
    })

    response = requests.request("PATCH", url, headers=headers, data=payload)

    fl.info(response.json())
    return response.status_code, response.json()


# sends an email to the end user.
# replaced with a celery task in tasks.py
def send_gmail_message(sender, to, cc, subject, message_text):
    message = MIMEText(message_text, 'html')
    message['to'] = to
    message['from'] = sender
    message['cc'] = cc
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_string().encode()).decode()

    url = f"https://gmail.googleapis.com/gmail/v1/users/{sender}/messages/send"

    payload = json.dumps({
        "raw": f"{raw_message}"
    })
    headers = {
        'Authorization': f'Bearer {get_actual_token("access_token")}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    if response.status_code < 300:
        return response.json()['id'], response.json()['labelIds']
    else:
        return response.json()['error']


# test: print(send_gmail_message(to="ilya.konovalov@junehomes.com", sender='ilya.konovalov@junehomes.com',cc='', subject='subject',
# message_text='test message'))


# creates a draft on gmail so the message can be easily sent to enduser.
# replaced with a celery task in tasks.py
def create_draft_message(sender, to, cc, subject, message_text):
    message = MIMEText(message_text, 'html')
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    message['cc'] = cc
    raw_message = base64.urlsafe_b64encode(message.as_string().encode()).decode()
    url = f"https://gmail.googleapis.com/gmail/v1/users/{sender}/drafts"

    payload = json.dumps({
        "message": {
            "raw": f"{raw_message}"
        }
    })
    headers = {
        'Authorization': f'Bearer {get_actual_token("access_token")}',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    response = requests.post(url=url, headers=headers, data=payload)
    if response.status_code < 300:
        return response.json()['id'], response.json()['message']['labelIds']
    else:
        return response.json()['error']


# test: print(create_draft_message(to="ilya.konovalov@junehomes.com", sender='ilya.konovalov@junehomes.com',cc='', subject='subject',
# message_text='test message'))

"""amazon account creation function is moved to tasks.py"""


def delete_amazon_user(user_email):
    # user_email - will need to search for the user email
    # search a user and retrieve its ID:
    # like: user_id = '3d3bf4fd-66d6-440f-89ca-95bd7235ce4d'
    user_id = ''
    client = boto3.client('connect')
    instance_id = 'a016cbe1-24bf-483a-b2cf-a73f2f389cb4'
    response = client.delete_user(
        InstanceId=instance_id,
        UserId=user_id
    )
    return response


def create_frontapp_user(suggested_email, first_name, last_name, frontapp_role):
    url = "https://scim.frontapp.com/v2/Users"

    payload = json.dumps({
        "schemas": [
            "urn:ietf:params:scim:schemas:core:2.0:User"
        ],
        "userName": suggested_email,
        "name": {
            "givenName": first_name,
            "familyName": last_name
        },
        "active": True,
        "emails": [
            {
                "value": suggested_email
            }
        ],
        "roles": [
            {
                "value": frontapp_role,
                "type": "template"
            }
        ],
    })
    headers = {
        'Accept': 'application/scim+json',
        'Content-Type': 'application/scim+json',
        'Authorization': f'Bearer {frontapp_api}'
    }

    response = requests.post(url=url, headers=headers, data=payload)

    return response.status_code, response.text


# test:
# frontapp_user = create_frontapp_user('ilya.test@example.com','ilya','test',)


def create_elk_user(firstname, lastname, suggested_email, role, dev_or_prod):
    if dev_or_prod == 'prod':
        url = f'https://kibana-v7.junehomes.net/_security/user/{suggested_email}'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': elk_prod
        }

    elif dev_or_prod == 'test':
        # test url on Ilya Ko. local kibana
        url = f"https://127.0.0.1:9200/_security/user/{suggested_email}"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ZWxhc3RpYzpCRDVmV3Irb05vK3YzZGZIQkxlUw=='
        }

    elif dev_or_prod == 'dev':
        url = f'https://kibana-v7.dev.junehomes.net/_security/user/{suggested_email}'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': elk_dev
        }

    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for i in range(32))

    payload = json.dumps({
        "password": password,
        "enabled": True,
        "roles": [role],
        "full_name": f"{firstname} {lastname}",
        "email": suggested_email
    })

    response = requests.request("POST", url, headers=headers, data=payload)
    return response, password


def request_child_roles(role_id):
    url = f"https://api.notion.com/v1/pages/{role_id}"

    payload = ""
    headers = {
        'Notion-Version': '2022-02-22',
        'Authorization': notion_secret
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    return response


# position_title = "Chief People Officer"


def notion_search_for_role(position_title, jira_key):
    url = "https://api.notion.com/v1/databases/09dc1fc3ec314343b7222808b5e5a72d/query"

    payload = json.dumps({
        "filter": {
            "property": "Role/Persona name",
            "rich_text": {
                "equals": position_title.replace("\\", "")
            }
        }
    })
    headers = {
        'Notion-Version': '2022-02-22',
        'Authorization': notion_secret,
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    pprint(response.json(), indent=1)
    try:
        print(len(response.json()['results']))
    except Exception as e:
        print('No results returned.', e)
        return False

    if len(response.json()['results']) == 0:  # if there is no role with this name
        send_jira_comment(f'the value "*{position_title}*" does not exist in column "Role/Persona name" ❌', jira_key=jira_key)
        return False

    elif len(response.json()['results']) == 1:  # there is only one role
        print('The role found')
        role_name = response.json()['results'][0]['properties']['Role/Persona name']['title'][0]['plain_text']
        role_url = response.json()['results'][0]['url']
        permissions_for_persona = response.json()['results'][0]['properties']['Permissions for persona']['relation']
        print(len(permissions_for_persona))


        child_roles_ids = response.json()['results'][0]['properties']['Is parent to:']['relation']
        print("child_roles_ids: ", len(child_roles_ids))  # Check how many child roles

        roles_tree = f'Roles Tree for *[{role_name}|{role_url}]*:'  # to check the roles tree
        dashes = '----'
        i = 0
        while True:
            i += 1

            print("child_roles_ids list:", child_roles_ids)
            if len(child_roles_ids) == 0:  # if there are no child roles
                print('No child roles detected')
                break
            elif len(child_roles_ids) > 1:
                print('TECH RESTRICTION! can\'t be more than 1 child role!')
                break

            else:
                child_role_name = get_notion_page_title(child_roles_ids[0]['id']).json()['properties']['Role/Persona name']['title'][0]['plain_text']
                child_role_url = get_notion_page_title(child_roles_ids[0]['id']).json()['url']

                roles_tree += f"\n{i}." + dashes * i + f"*[{child_role_name}|{child_role_url}]*"
                print('There are linked child roles!')
                set_of_permissions_by_each_child = []  # creating permissions list for each child role

                for role in range(len(child_roles_ids)):
                    role_id = child_roles_ids[role]['id']
                    # taking the pemissions list for the role
                    permissions_for_each_child = request_child_roles(role_id=role_id).json()['properties']['Permissions for persona']['relation']
                    set_of_permissions_by_each_child.append(permissions_for_each_child)  # appending permissions of each child role to the common list

                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ created for the current level")
                print(f'Permission set for role is built: ', set_of_permissions_by_each_child)  # having a set of sets of permissions for each role
                permissions_for_persona.append(set_of_permissions_by_each_child)  # appending to main list
                print("After append to general list: ", len(permissions_for_persona))
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ created a list for the current level")

                # for each childrole checking if it has any child rol
                for j in range(len(child_roles_ids)):
                    child_roles_id = request_child_roles(role_id=child_roles_ids[j]['id'])
                    role_name = child_roles_id.json()['properties']['Role/Persona name']['title'][0]['plain_text']
                    print("Number of child roles:", len(child_roles_id.json()['properties']['Is parent to:']['relation']), "of role -", role_name)
                # deleting the list
                child_roles_ids = []

                # appending the role if it exists
                if len(child_roles_id.json()['properties']['Is parent to:']['relation']) > 0:
                    child_roles_ids.append(*child_roles_id.json()['properties']['Is parent to:']['relation'])

                else:
                    break
                print("child_roles_ids of roles was recreated and appended: ", child_roles_ids)


        print("roles_tree:")
        print(roles_tree)
        send_jira_comment(roles_tree, jira_key)
        print('Complete set of permissions:')
        pprint(permissions_for_persona, indent=2)
        print('=============================================')

        if len(response.json()['results']) == 0:  # no permissions are linked to this role!
            return permissions_for_persona

        else:  # correct flow there are linked  permissions to this role!
            return permissions_for_persona

    elif len(response.json()['results']) > 1:  # if there is more than 1 role for this name
        pprint(response.json(), indent=1)
        print(f"There there is more than one result for your search ({len(response.json()['results'])}).\n"
              f"Roles should be unique! Check Rore table for \"{position_title}\"")
        send_jira_comment(f"There there is more than one result for your search ({len(response.json()['results'])}).\n"
                          f"Roles should be unique! Check Rore table for \"{position_title}\" ❌", jira_key=jira_key)
        return False
    return response


def notion_search_for_permission_block_children(block_id):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"

    payload = {}
    headers = {
        'Notion-Version': '2022-02-22',
        'Authorization': notion_secret
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    for i in range(len(response.json()['results'])):  # for every block on the page

        if 'code' in response.json()['results'][i]:
            print('code block found on the page!')
            permissions = response.json()['results'][i]['code']['rich_text'][0]['text']['content']

            try:

                permissions_dict = json.loads(permissions)
                return dict(permissions_dict), True  # tuple, т.е. валидный, можно записать на диск

            except Exception as e:
                print('Permissions are NOT parsed')
                return f"*Validation failed. JSON Error: {e}* ⚠️"

        else:
            pass

    return '*Please add JSON block to the body page* ⚠️'


def get_notion_page_title(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {}
    headers = {
        'Notion-Version': '2022-02-22',
        'Authorization': notion_secret
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    return response


def fetching_params_from_file(filename_contains: str, jsonvalue: str, jira_key: str, position_title: str):
    directory = data_folder / 'roles_configs' / jira_key / position_title
    for item in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, item)):  # creating a list of files in the directory
            if re.search(filename_contains, item):  # searching for a jsonvalue file in the directory
                file_to_open = data_folder / "roles_configs" / jira_key / position_title / item
                with open(file_to_open) as file:
                    try:
                        organizational_unit = json.loads(file.read())
                        if jsonvalue in organizational_unit:
                            organizational_unit = organizational_unit[jsonvalue]
                            return organizational_unit
                        else:
                            print('Organizational unit is not found')

                    except Exception as e:
                        print(f"Error: {e}")
            else:
                print(f'"{item}" - doesn\'t contain "{filename_contains}"')
        else:
            print(f'"{item}" - is not a file')


def checking_config_for_service_existence(position_title, jira_key):
    directory = data_folder / 'roles_configs' / jira_key / position_title
    items_list = []
    for item in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, item)):  # creating a list of files in the directory
            items_list.append(item)
        else:
            print(f'"{item}" - is not a file')
    return items_list


def compare_permissions_by_name(permissions_set,  # might be current_permissions_set[0] / antecedent_permissions_set[0]
                                pages_list,
                                iterator,
                                level,
                                jira_key,
                                position_title,
                                **compare_by_name_permission_for_l2
                                ):
    permission_id = permissions_set[0][iterator]['id']
    permission_name = get_notion_page_title(permission_id).json()['properties']['Name']['title'][0]['plain_text']
    permission_url = get_notion_page_title(permission_id).json()['url']

    if level == 2:
        service = compare_by_name_permission_for_l2['compare_by_name_permission_for_l2']
        if re.findall(service, permission_name):
            print(permission_name, '-', compare_by_name_permission_for_l2['compare_by_name_permission_for_l2'], 'they match!')
        else:
            json_object = 'incomparable_service'
            print(permission_name, '-', compare_by_name_permission_for_l2['compare_by_name_permission_for_l2'], 'they don\'t match')
            return pages_list, permission_name, json_object

    result = notion_search_for_permission_block_children(permission_id)  # запрашиваем есть ли валидный json

    print('notion_search_for_permission_block_children(permission_id): ')
    print(result)

    try:
        file_to_open = data_folder / "roles_configs" / jira_key / position_title / f"{compare_by_name_permission_for_l2['compare_by_name_permission_for_l2']}_config.json"
        with open(file_to_open, 'r') as file:
            result = json.loads(file.read())

    except Exception as e:
        print("Exception during opening the file:")
        print(e)

    print('level - ', level)

    if level == 1:  # это сравнение пермиссий current level
        if type(result) == tuple:
            json_object = result[0]  # это уже пермиcсии сами если все ок
            pages_list += f"[level: 1] *[{permission_name}|{permission_url}]* : Validated. ✅\n"

        elif type(result) == dict:
            json_object = result
            pages_list += f"[level: 1] +––> *[{permission_name}|{permission_url}]*: Inherited from the config on the disk. ✅\n"

        else:
            json_object = False  # если валидация не прошла
            pages_list += f"*[{permission_name}|{permission_url}]*: {result}\n"

    elif level == 2:

        if type(result) == tuple:
            json_object = result[0]  # это уже пермиcсии, если все ок

            pages_list += f"[level: 2] +––> *[{permission_name}|{permission_url}]*: Validated. ✅\n"

        elif type(result) == dict:
            json_object = result
            pages_list += f"[level: 2] +––> *[{permission_name}|{permission_url}]*: Inherited from the config on the disk. ✅\n"

        else:
            json_object = False  # если валидация не прошла
            pages_list += f"+––> *[{permission_name}|{permission_url}]*: {result}\n"

    return pages_list, permission_name, json_object


def compare_role_configs_google(current_json_object, antecedent_json_object):
    for c_index, (c_key, c_value) in enumerate(current_json_object.items()):
        for a_index, (a_key, a_value) in enumerate(antecedent_json_object.items()):
            if c_key == a_key:
                if a_value == c_value:  # equal values
                    pass
                else:  # values are different / c_value needs to be updated
                    if type(c_value) == list:
                        for i in range(len(a_value)):
                            if a_value[i].strip() not in c_value:
                                c_value.append(a_value[i].strip())

                    elif type(c_value) == str:
                        c_value = a_value
                    else:
                        print(f'A different value type is received: '
                              f'{c_value} - {type(c_value)}')
    return current_json_object


def compare_role_configs_juneos(current_json_object, antecedent_json_object):
    # !!! "data_file_config" will be replaced by "permission_config[0]"
    for c_index, (c_key, c_value) in enumerate(current_json_object.items()):
        for a_index, (a_key, a_value) in enumerate(antecedent_json_object.items()):
            if c_key == a_key:
                if a_value == c_value:  # equal values
                    pass
                else:  # values are different / c_value needs to be updated
                    if type(c_value) == list:
                        for i in range(len(a_value)):
                            if a_value[i] not in c_value:
                                c_value.append(a_value[i])

                        print('c_value:')
                        print(c_value)
                    elif type(c_value) == int:
                        c_value = a_value
                    else:
                        print(f'A different value type is received: '
                              f'{c_value} - {type(c_value)}')
    return current_json_object


def compare_role_configs_amazonconnect():
    print('сравнили конфиги в амазоне :)')


def compare_role_configs_slack():
    print('сравнили конфиги в slack :)')


def compare_role_configs_frontapp():
    print('сравнили конфиги в frontapp :)')


def full_compare_by_name_and_permissions_with_file(config_name: str,  # googleworkspace, amazonconnect,juneos,etc
                                                   antecedent_permissions_set,
                                                   jira_key,
                                                   position_title,
                                                   current_json_object,
                                                   pages_list,
                                                   current_role_name):
    print()
    print('current_role_name:')
    print(current_role_name)
    print('config_name:')
    print(config_name)
    print('current_json_object:')
    print(current_json_object)
    print()

    for r in range(len(antecedent_permissions_set[0])):  # берем каждую пермиссию из n-1 уровня
        # получаем результат проверки для коммента, n-1 название роли и json конфиг
        pages_list, antecedent_role_name, antecedent_json_object = compare_permissions_by_name(permissions_set=antecedent_permissions_set,
                                                                                               pages_list=pages_list,
                                                                                               iterator=r,
                                                                                               level=2,
                                                                                               compare_by_name_permission_for_l2=config_name,
                                                                                               jira_key=jira_key,
                                                                                               position_title=position_title)

        print('this is antecedent_json_object:', antecedent_json_object)
        print('this is current_json_object:', current_json_object)
        if not antecedent_json_object:  # writing down only the current result. Skipping antecedent_json_object because it's invalid.
            print('there is an error in the antecedent config...')

            pages_list += "–––––––– ⬆️Permission is skipped during building *Permissions Tree*! Fix the error, otherwise the permissions tree may not be complete.\n"
            relevant_config = current_json_object

            # запись в файл
            file_to_open = data_folder / "roles_configs" / jira_key / position_title / f'{config_name}_config.json'
            with open(file_to_open, 'w+') as file:
                json.dump(relevant_config, file, indent=4)
            print(f'"{config_name}_config.json" is successfully written')

        elif antecedent_json_object == "incomparable_service":  # когда сервис для сравниваемой пермиссии отличается - скипаем.
            print(f'The permission - "{antecedent_role_name}" cannot be compared with  service - "{config_name}", skipping ...')
            continue

        else:
            print('antecedent_role_name is correct')
            if re.findall(config_name, antecedent_role_name):  # internal config of antecedent_role
                if config_name == 'googleworkspace':
                    print(f"Comparing '{config_name}' и '{antecedent_role_name}'")
                    # comparing current role json object vs. antecedent role json object for googleworkspace
                    relevant_config = compare_role_configs_google(current_json_object, antecedent_json_object)
                    print()
                    print('***************This is relevant googleworkspace config:')
                    print(relevant_config)
                    print('***************')
                    print()

                    if relevant_config:
                        file_to_open = data_folder / "roles_configs" / jira_key / position_title / f'{config_name}_config.json'
                        with open(file_to_open, 'w+') as file:
                            json.dump(relevant_config, file, indent=4)
                    else:
                        print('relevant config: ', relevant_config)
                        pass

                elif config_name == 'juneos':
                    # !!! "data_file_config" will be replaced by "permission_config[0]"
                    relevant_config = compare_role_configs_juneos(current_json_object, antecedent_json_object)
                    print()
                    print('***************This is relevant juneos config:')
                    print(relevant_config)
                    print('***************')
                    print()

                    if relevant_config:
                        file_to_open = data_folder / "roles_configs" / jira_key / position_title / f'{config_name}_config.json'
                        with open(file_to_open, 'w+') as file:
                            json.dump(relevant_config, file, indent=4)
                    else:
                        print('relevant config: ', relevant_config)
                        pass

                elif config_name == 'amazonconnect':
                    relevant_config = compare_role_configs_amazonconnect()

                elif config_name == 'frontapp':
                    relevant_config = compare_role_configs_frontapp()

                elif config_name == 'slack':
                    relevant_config = compare_role_configs_slack()
                    pass
                else:
                    relevant_config = f'received permissions for: {config_name}'
                    print(f'received permissions for: {config_name}.. Don\'t know how to compare... skipping')
            else:
                relevant_config = f'else: {antecedent_role_name}'
                print('else:', antecedent_role_name)
                pass

    return relevant_config, pages_list


def comparing_permission_from_notion_vs_config_on_disk(filename,
                                                       permission_config,
                                                       permission_name,
                                                       permission_url,
                                                       service_name
                                                       ):
    validation_result = ''
    try:
        with open(filename, 'r') as file:
            data_file_config = json.loads(file.read())
            print("data_file_config:", data_file_config)

    except Exception as e:
        # если не смог прочитать конфиг, то просто перезаписываем и в jira комменте отписываемся что скипнули

        print("couldn't read the permission on disc, error:", e)
        with open(filename, 'w+') as file:
            json.dump(permission_config[0], file, indent=4)
        validation_result += f"*[{permission_name}|{permission_url}]*: Config successfully written.✅\n"
        print(f"Permission '{filename}' is successfully written on the disc!")
    else:
        # если смог прочитать, то пытаемся сравнить по сервисам
        if service_name == 'googleworkspace':
            print("**********************************************")
            print(">>>>>>>>>>>>>>>>>>>>>>>>> data_file_config:")
            print(data_file_config)
            print(">>>>>>>>>>>>>>>>>>>>>>>>> permission_config[0]")
            print("")
            print(permission_config[0])
            print(">>>>>>>>>>>>>>>>>>>>>>>>>")
            # !!! "data_file_config" will be replaced by "permission_config[0]"
            relevant_config = compare_role_configs_google(permission_config[0], data_file_config)
            print('relevant_config:')
            print("сonfigs compared ✅")
            print("====================")
            print('relevant_config for google:')
            print(relevant_config)
            print("**********************************************")
            with open(filename, 'w+') as file:
                json.dump(relevant_config, file, indent=4)

        elif service_name == 'juneos':
            relevant_config = compare_role_configs_juneos(permission_config[0], data_file_config)
            print('relevant_config:')
            print("сonfigs compared ✅")
            print("====================")
            with open(filename, 'w+') as file:
                json.dump(relevant_config, file, indent=4)
        else:  # пока просто перезаписываем
            with open(filename, 'w+') as file:
                json.dump(permission_config[0], file, indent=4)
            print("успешно перезаписали", filename)
        validation_result += f"*[{permission_name}|{permission_url}]* : Validated. ✅\n"

    return validation_result


def allow_zendesk_login(user_email, access_token):
    url = f"https://admin.googleapis.com/admin/directory/v1/users/{user_email}?projection=full"

    payload = json.dumps({
        "customSchemas": {
            "Additional_details": {
                "Zendesk_role": "agent"
            }
        }
    })
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    response = requests.request("PATCH", url, headers=headers, data=payload)
    return response


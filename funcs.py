import json
import time
import requests
import string
import random
import os
from email.mime.text import MIMEText
import base64
import boto3
from pprint import pprint
import fast_api_logging as fl

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
    with open('client_secret_675261997418-4pfe4aep6v3l3pl13lii6p8arsd4md3m.apps.googleusercontent.com.json') as data:
        json_value = json.load(data)['web'][arg]
        return json_value


# returns the actual token
def get_actual_token(arg):
    with open(r'''access_refresh_tokens.json''') as data:
        # open the file and parse it to the latest json
        newest_data = data.read().split('\n')[-2]
        token = json.loads(newest_data)[arg]
        return token
    # f = open(r'''C:\PythonProjects\Fastapi\access_refresh_tokens.json''')
    # data = json.load(f)
    # # print(data)
    # return data["tokens"][-1][arg]


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

    # print(response.headers)  # receives headers in dict
    fl.info(response.json())  # receives body in dict
    refreshed_token = response.json()
    if refreshed_token.get("error") is None:
        refreshed_token['datetime'] = str(int(time.time()))  # append datetime to dict
        # print(refreshed_token)  # receives body in dict
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

    # print(refreshed_token.headers)  # receives headers in dict
    # print(refreshed_token.json())  # receives body in dict
    refreshed_token = refreshed_token.json()
    refreshed_token['datetime'] = str(int(time.time()))  # append datetime to dict

    # print(refreshed_token)  # receives body in dict
    refreshed_token = json.dumps(refreshed_token)  # convert dict to json

    # print(refreshed_token)
    # write json to the end of the file
    file = open('access_refresh_tokens.json', 'a')
    file.write(str(refreshed_token) + '\n')

    file.close()
    fl.info('access_refresh_tokens.json - appended!\nRefresh token was exchanged successfully.')


# https://developers.google.com/admin-sdk/directory/v1/guides/manage-users
def create_google_user_req(first_name, last_name, suggested_email, organizational_unit):
    global password
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for i in range(8))
    """google response with another status which means that the account is not can be created."""

    file = open(r'''User Accounts.txt''', 'a', encoding='utf-8')

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
        "password": f"{password}",
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
        file.write(f"{first_name} {last_name}\nUsername: {suggested_email}\nPassword: {password}\n\n")
        file.close()
    elif response.status_code >= 500:
        fl.error(f"an error on the google side occurred while creating a google user:\n {str(response.json())}")
        return response.status_code, response.__dict__
    else:
        fl.error(f"an error occurred while creating a google user\n {str(response.json())}")
    return response.status_code, response.__dict__, password


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
            # print(assign_google_group.status_code)
        # print(assign_google_group.json())
    # print(final_row)
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
        # print('dev was requested')
        url = "https://dev.junehomes.net/api/v2/auth/login-web-token/"

        payload = json.dumps({
            "email": "ilya.konovalov@junehomes.com",  # на деве авторизация под моей учеткой
            "password": juneos_dev_password
        })
    elif dev_or_prod == 'prod':
        # print('prod was requested')
        url = "https://junehomes.com/api/v2/auth/login-web-token/"

        payload = json.dumps({
            "email": juneos_prod_login,  # на проде под отдельной
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
        # return response.status_code, \
        #        response.cookies['csrftoken'], \
        #        response.cookies['sessionid'], \
        #        response.json()['token']
        return response
    except:
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
    with open('permissions_by_orgunits/' + file_name, "r") as data:
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
    # print(message)
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
    # print(message)
    raw_message = base64.urlsafe_b64encode(message.as_string().encode()).decode()
    # print(raw_message)
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
        "userName": f"{suggested_email}",
        "name": {
            "givenName": f"{first_name}",
            "familyName": f"{last_name}"
        },
        "active": True,
        "emails": [
            {
                "value": f"{suggested_email}"
            }
        ],
        "roles": [
            {
                "value": f"{frontapp_role}",
                "type": "template"
            }
        ],
        "urn:ietf:params:scim:schemas:extension:frontapp:teammate": None
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

    # pprint(response.json(), indent=1)

    if len(response.json()['results']) == 0:  # if there is no role with this name
        pprint(response.json()['results'], indent=1)
        # print(f'the value "{position_title}" does not exist in column "Role/Persona name"')
        send_jira_comment(f'the value "*{position_title}*" does not exist in column "Role/Persona name" ❌', jira_key=jira_key)
        return False

    elif len(response.json()['results']) == 1:
        print('The role found')
        permissions_for_persona = response.json()['results'][0]['properties']['Permissions for persona']['relation']
        # print(len(permissions_for_persona))
        if len(response.json()['results']) == 0:
            return permissions_for_persona

        else:
            # pprint(permissions_for_persona, indent=1)  # list
            return permissions_for_persona

    elif len(response.json()['results']) > 1:  # if there is more than 1 role for this name
        pprint(response.json(), indent=1)
        print(f"There there is more than one result for your search ({len(response.json()['results'])}).\n"
              f"Roles should be unique! Check Rore table for \"{position_title}\"")
        send_jira_comment(f"There there is more than one result for your search ({len(response.json()['results'])}).\n"
                          f"Roles should be unique! Check Rore table for \"{position_title}\" ❌", jira_key=jira_key)
        return False
    # permissions_for_persona = response.json()['results'][0]['properties']['Permissions for persona']['relation']
    # if permissions_for_persona
    # pprint(permissions_for_persona,indent=1)

    return response


def notion_search_for_permission_block_children(block_id):
    url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"

    payload = {}
    headers = {
        'Notion-Version': '2022-02-22',
        'Authorization': notion_secret
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    check_permissions = False

    for i in range(len(response.json()['results'])):
        if 'toggle' in response.json()['results'][i]:
            if 'code' in response.json()['results'][i]:
                print('code block found on the page!')
                permissions = response.json()['results'][i]['code']['rich_text'][0]['text']['content']
                try:
                    print('validating JSON ... ')
                    permissions_json: object = json.loads(permissions)
                    pprint(permissions_json, indent=1)
                    check_permissions = True
                    print('validated')

                except Exception as e:
                    # print(f"failed. JSON Error: {e}")
                    return f"validation failed. JSON Error: {e} ⚠️"
            else:
                return "Add code block to the permissions page ⚠️ "

        else:
            return "Toggle is not added to permissions page ⚠️"

    if check_permissions:
        return permissions_json, True
    else:
        # print('Please add JSON block to the document to the root level on the body page')
        return 'Please add "/toggle" block containing the valid JSON block to the body page ⚠️'


def get_notion_page_title(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {}
    headers = {
        'Notion-Version': '2022-02-22',
        'Authorization': notion_secret
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    # pprint(response.json(),indent=1)
    return response

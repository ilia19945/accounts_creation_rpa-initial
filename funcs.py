import json
import time
from email.mime.text import MIMEText
import requests
import string
import random
import os
import base64

# functions
# just receives google application info

# hidden variables in OS
google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
jira_api = os.environ.get('JIRA_API')
frontapp_api = os.environ.get('FRONTAPP_API')


def get_app_info(arg):
    with open('client_secret_675261997418-4pfe4aep6v3l3pl13lii6p8arsd4md3m.apps.googleusercontent.com.json') as data:
        json_value = json.load(data)['web'][arg]
        return json_value


# returns the actual token
def get_actual_token(arg):  # ОБРАТИ ВНИМАНИЕ ЧТО ИСПОЛЬЗУЕТСЯ ФАЙЛ tokens2!!! НА БОЮ ПЕРЕКЛЮЧИТЬ НА TOKENS.JSON
    with open(r'''C:\PythonProjects\Fastapi\access_refresh_tokens.json''') as data:
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
                                   '+https://www.googleapis.com/auth/gmail.send&' \
                                   'access_type=offline&' \
                                   'include_granted_scopes=true&' \
                                   'response_type=code&' \
                                   f'redirect_uri={get_app_info("redirect_uris")[0]}&' \
                                   f'client_id={get_app_info("client_id")}'
    return refresh_access_token_request


""" Step 5: Exchange authorization code for refresh and access tokens
https://developers.google.com/identity/protocols/oauth2/web-server#exchange-authorization-code"""


def exchange_auth_code_to_access_refresh_token(code, jira_key):
    request_row = 'https://oauth2.googleapis.com/token?' \
                  f'code={code}&' \
                  f'client_id={get_app_info("client_id")}&' \
                  f'client_secret={get_app_info("client_secret")}&' \
                  f'redirect_uri={get_app_info("redirect_uris")[0]}&' \
                  'grant_type=authorization_code'
    # print(request_row)
    response = requests.post(request_row)  # send and receives response

    # print(response.headers)  # receives headers in dict
    print(response.json())  # receives body in dict
    refreshed_token = response.json()
    if refreshed_token.get("error") is None:
        refreshed_token['datetime'] = str(time.time_ns())[0:10]  # append datetime to dict
        # print(refreshed_token)  # receives body in dict
        refreshed_token = json.dumps(refreshed_token)  # convert dict to json

        # print(refreshed_token)
        # write json to the end of the file
        file = open('access_refresh_tokens.json', 'a')
        file.write(str(refreshed_token) + '\n')
        file.close()
        print('Step 5 executed successfully! Auth code has been exchanged to an access token.\n'
              'Please repeat creating a user account attempt.')
        send_jira_comment('Current Auth token was irrelevant and has been exchanged to a new token.\n'
                          'Please repeat creating a user account attempt.\n'
                          '(Switch the ticket status -> *"In Progress"* -> *"Create user accounts!"*)',
                          jira_key)
    else:
        print(response)


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
    refreshed_token['datetime'] = str(time.time_ns())[0:10]  # append datetime to dict

    # print(refreshed_token)  # receives body in dict
    refreshed_token = json.dumps(refreshed_token)  # convert dict to json

    # print(refreshed_token)
    # write json to the end of the file
    file = open('access_refresh_tokens.json', 'a')
    file.write(str(refreshed_token) + '\n')

    file.close()
    print('access_refresh_tokens.json - appended!\nRefresh token was exchanged successfully.')


password = ''


# https://developers.google.com/admin-sdk/directory/v1/guides/manage-users
def create_google_user_req(first_name, last_name, suggested_email, organizational_unit):
    """google response with another status which means that the account is not can be created."""

    characters = string.ascii_letters + string.digits + string.punctuation
    global password
    password = ''.join(random.choice(characters) for i in range(8))
    file = open(r'''C:\Users\ilia1\Desktop\June Homes\User Accounts.txt''', 'a', encoding='utf-8')

    print(f"{first_name} {last_name}\nUsername: {suggested_email}\nPassword: {password}\n\n")
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
    elif response.status_code > 500:
        print("an error on the google side occurred while creating a google user")
        print(response.text)
        return response.status_code, response.__dict__
    else:
        print("an error occurred while creating a google user")
        print(response.text)
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
def adding_user_to_google_group(gmail_groups, suggested_email):
    payload = json.dumps({
        "email": f"{suggested_email}",
        "role": "MEMBER"})
    headers = {'Authorization': f'Bearer {get_actual_token("access_token")}',
               'Content-Type': 'application/json'}
    final_str = ''
    for i in gmail_groups:
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
    return final_str


def send_jira_comment(message, jira_key):
    url = f'https://junehomes.atlassian.net/rest/api/2/issue/{jira_key}/comment'
    # это кринж надо бы откуда-то токен из внешнего файла доставать, но пока пох
    headers = {
        'Authorization': jira_api,  # \X.X/
        'Content-Type': 'application/json'
    }
    data = json.dumps(
        {"body": f"{message}"})
    jira_notification = requests.post(url=url, headers=headers, data=data)

    return jira_notification.status_code, jira_notification.json()


def create_juneos_dev_user(first_name, last_name, suggested_email, personal_phone, password):
    url = "https://dev.junehomes.net/api/v2/auth/registration/"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
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

    juneos_dev_user = requests.post(url=url, headers=headers, data=payload)
    if juneos_dev_user.status_code < 300:
        print('user created')
        print(juneos_dev_user.json()['user'])
        return juneos_dev_user.status_code, juneos_dev_user.json()['token'], juneos_dev_user.json()['user'], juneos_dev_user.json()['user']['id']


    else:  # if error
        print(juneos_dev_user.json()['errors'])
        return juneos_dev_user.json()['errors']


# sends an email to the enduser.
# sender should be updated manually!!!!
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


# test:
# print(send_gmail_message(to="ilya.konovalov@junehomes.com", sender='ilya.konovalov@junehomes.com',cc='', subject='subject', message_text='test message'))


# creates a draft on gmail so the message can be easily sent to enduser.
# sender should be updated manually!!!!
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

    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code < 300:
        return response.json()['id'], response.json()['message']['labelIds']
    else:
        return response.json()['error']


# test:
# print(create_draft_message(to="ilya.konovalov@junehomes.com", sender='ilya.konovalov@junehomes.com',cc='', subject='subject', message_text='test message'))


def create_amazon_user():
    pass


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

    response = requests.request("POST", url, headers=headers, data=payload)

    return response.status_code, response.text
# test:
# frontapp_user = create_frontapp_user('ilya.test@example.com','ilya','test',)

"""
Google Workspace service.

Wraps Google Admin SDK, Licensing, Calendar, and Gmail API calls.
All authentication helpers (OAuth token management) live here too.
"""

from __future__ import annotations

import json
import random
import string
import time
from pathlib import Path

import requests

from app.config import settings
import app.utils.logging as fl


data_folder = Path(".")


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def get_app_info(arg: str):
    """Read a field from client_secret.json → web section."""
    with open("client_secret.json") as data:
        return json.load(data)["web"][arg]


def get_actual_token(arg: str):
    """Return the latest token value (access_token / refresh_token) from the log file."""
    with open("access_refresh_tokens.json") as data:
        newest_data = data.read().split("\n")[-2]
        return json.loads(newest_data)[arg]


def get_new_access_token() -> str:
    """Build the OAuth 2.0 authorisation URL (Step 2).

    https://developers.google.com/identity/protocols/oauth2/web-server#redirecting
    """
    refresh_access_token_request = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        "scope=https://www.googleapis.com/auth/admin.directory.user"
        "+https://www.googleapis.com/auth/apps.licensing"
        "+https://www.googleapis.com/auth/admin.directory.group.member"
        "+https://www.googleapis.com/auth/admin.directory.orgunit"
        "+https://mail.google.com/"
        "+https://www.googleapis.com/auth/gmail.modify"
        "+https://www.googleapis.com/auth/gmail.compose"
        "+https://www.googleapis.com/auth/gmail.send"
        "+https://www.googleapis.com/auth/admin.directory.userschema"
        "+https://www.googleapis.com/auth/calendar&"
        "access_type=offline&"
        "include_granted_scopes=true&"
        "response_type=code&"
        f"redirect_uri={get_app_info('redirect_uris')[0]}&"
        f"client_id={get_app_info('client_id')}"
    )
    return refresh_access_token_request


def exchange_auth_code_to_access_refresh_token(code: str):
    """Exchange an authorisation code for access + refresh tokens (Step 5).

    https://developers.google.com/identity/protocols/oauth2/web-server#exchange-authorization-code
    """
    request_row = (
        "https://oauth2.googleapis.com/token?"
        f"code={code}&"
        f"client_id={get_app_info('client_id')}&"
        f"client_secret={get_app_info('client_secret')}&"
        f"redirect_uri={get_app_info('redirect_uris')[0]}&"
        "grant_type=authorization_code"
    )
    response = requests.post(request_row)
    fl.info(response.json())
    refreshed_token = response.json()
    if refreshed_token.get("error") is None:
        refreshed_token["datetime"] = str(int(time.time()))
        refreshed_token = json.dumps(refreshed_token)
        with open("access_refresh_tokens.json", "a") as file:
            file.write(str(refreshed_token) + "\n")
        return
    else:
        fl.info(response)
        return response


def refresh_token_func() -> None:
    """Refresh the Google access token using the stored refresh token.

    https://developers.google.com/identity/protocols/oauth2/web-server#offline
    """
    refresh_request = (
        f"{get_app_info('token_uri')}?"
        f"client_id={get_app_info('client_id')}"
        f"&client_secret={get_app_info('client_secret')}"
        f"&refresh_token={get_actual_token('refresh_token')}"
        "&grant_type=refresh_token"
    )
    refreshed_token = requests.post(refresh_request).json()
    refreshed_token["datetime"] = str(int(time.time()))
    refreshed_token = json.dumps(refreshed_token)
    with open("access_refresh_tokens.json", "a") as file:
        file.write(str(refreshed_token) + "\n")
    fl.info("access_refresh_tokens.json - appended!\nRefresh token was exchanged successfully.")


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

def create_google_user_req(
    first_name: str,
    last_name: str,
    suggested_email: str,
    organizational_unit: str,
):
    """Create a Google Workspace user via the Admin SDK.

    https://developers.google.com/admin-sdk/directory/v1/guides/manage-users
    Returns (status_code, response_dict, google_password).
    """
    global google_password
    characters = string.ascii_letters + string.digits + string.punctuation
    google_password = "".join(random.choice(characters) for _ in range(8))

    fl.info(f"{first_name} {last_name}\nUsername: {suggested_email}")

    url = "https://admin.googleapis.com/admin/directory/v1/users/"
    headers = {"Authorization": f"Bearer {get_actual_token('access_token')}"}
    payload = json.dumps(
        {
            "primaryEmail": suggested_email,
            "name": {
                "givenName": first_name,
                "familyName": last_name,
                "fullName": f"{first_name} {last_name}",
            },
            "password": google_password,
            "isAdmin": False,
            "isDelegatedAdmin": False,
            "agreedToTerms": True,
            "suspended": False,
            "changePasswordAtNextLogin": False,
            "ipWhitelisted": False,
            "includeInGlobalAddressList": True,
            "orgUnitPath": f"/Root OU/{organizational_unit}",
        }
    )
    response = requests.post(url, headers=headers, data=payload)

    if response.status_code < 300:
        with open("User Accounts.txt", "a", encoding="utf-8") as file:
            file.write(
                f"{first_name} {last_name}\nUsername: {suggested_email}\nPassword: {google_password}\n\n"
            )
    elif response.status_code >= 500:
        fl.error(
            f"an error on the google side occurred while creating a google user:\n {response.json()}"
        )
        return response.status_code, response.__dict__
    else:
        fl.error(f"an error occurred while creating a google user\n {response.json()}")

    return response.status_code, response.__dict__, google_password


# ---------------------------------------------------------------------------
# Licensing
# ---------------------------------------------------------------------------

def assign_google_license(google_license_id: str, suggested_email: str):
    """Assign a Google Workspace licence to a user.

    https://developers.google.com/admin-sdk/licensing/v1/how-tos/using
    Returns (status_code, response_dict).
    """
    url = f"https://www.googleapis.com/apps/licensing/v1/product/Google-Apps/sku/{google_license_id}/user"
    payload = json.dumps({"userId": suggested_email})
    headers = {
        "Authorization": f"Bearer {get_actual_token('access_token')}",
        "Content-Type": "application/json",
    }
    response = requests.post(url=url, headers=headers, data=payload)
    return response.status_code, response.__dict__


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

def adding_user_to_google_group(gmail_groups_refined: list, suggested_email: str) -> str:
    """Add a user to one or more Google Groups.

    https://developers.google.com/admin-sdk/directory/v1/guides/manage-group-members#create_member
    Returns a formatted status string.
    """
    payload = json.dumps({"email": suggested_email, "role": "MEMBER"})
    headers = {
        "Authorization": f"Bearer {get_actual_token('access_token')}",
        "Content-Type": "application/json",
    }
    final_str = ""
    for group in gmail_groups_refined:
        url = f"https://admin.googleapis.com/admin/directory/v1/groups/{group}/members"
        response = requests.post(url=url, headers=headers, data=payload)
        if response.status_code < 300:
            final_str += (
                f"Gmail group *{group}* assigning finished with status code: *{response.status_code}* \n"
            )
        else:
            final_str += (
                f"Gmail group *{group}* assigning finished with error code: *{response.status_code}*. "
                f"Error: *{response.json()['error']['message']}*\n"
            )
    fl.info(f"(3/3) Assigned google groups:\n{final_str}")
    return final_str


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def adding_to_junehomes_dev_calendar(suggested_email: str, calendar_id: str):
    """Grant writer access to a Google Calendar for a user.

    Returns (status_code, response_json).
    """
    url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/acl"
    payload = json.dumps(
        {"role": "writer", "scope": {"type": "user", "value": suggested_email}}
    )
    headers = {
        "Authorization": f"Bearer {get_actual_token('access_token')}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    response = requests.post(url=url, headers=headers, data=payload)
    return response.status_code, response.json()


# ---------------------------------------------------------------------------
# Custom schema / Zendesk
# ---------------------------------------------------------------------------

def allow_zendesk_login(user_email: str, access_token: str):
    """Set the Zendesk custom schema field on a Google user to enable SSO login.

    Returns the raw requests.Response object.
    """
    url = f"https://admin.googleapis.com/admin/directory/v1/users/{user_email}?projection=full"
    payload = json.dumps(
        {"customSchemas": {"Additional_details": {"Zendesk_role": "agent"}}}
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    return requests.request("PATCH", url, headers=headers, data=payload)

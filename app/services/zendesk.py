"""
Zendesk access service.

Zendesk login for JuneOS employees is enabled via a custom schema field
(``Additional_details.Zendesk_role``) on their Google Workspace profile.
This module encapsulates both the check and the activation logic.
"""

import requests

import app.utils.logging as fl
from app.services.google_workspace import allow_zendesk_login
from app.services.jira import send_jira_comment

# Zendesk login page used in Jira comments
_ZENDESK_LOGIN_URL = "https://junehomes.zendesk.com/auth/v2/login"
_ZENDESK_LOGIN_HINT = (
    f"The user may now go to [Zendesk Login page|{_ZENDESK_LOGIN_URL}] and login "
    "through \"I'm an agent\" → via the login and password of their work account.\n\n"
    "P.S. Make sure the user has the correct Org.unit on Google Workspace "
    "that allows Zendesk SAML."
)


def check_zendesk_login_param(user_email: str, access_token: str) -> dict:
    """
    GET the user's Google Workspace profile and check whether the
    ``Additional_details.Zendesk_role`` custom schema is already set.

    Returns::

        {
            "has_param": bool,
            "response": requests.Response,
        }
    """
    url = (
        f"https://admin.googleapis.com/admin/directory/v1/"
        f"users/{user_email}?projection=full"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)

    try:
        role = response.json()["customSchemas"]["Additional_details"]["Zendesk_role"]
        print(f"check_zendesk_login_param: Zendesk_role already set → {role!r}")
        return {"has_param": True, "response": response}
    except KeyError:
        return {"has_param": False, "response": response}


def enable_zendesk_login(
    user_email: str,
    access_token: str,
    jira_key: str,
) -> dict:
    """
    Check whether the Zendesk login custom schema is set for *user_email* and
    enable it if missing.  Posts a Jira comment with the outcome.

    Returns a result dict with keys ``"result"`` and ``"details"``.
    """
    check = check_zendesk_login_param(user_email, access_token)

    if check["has_param"]:
        send_jira_comment(
            message=(
                "A necessary parameter is already set.\n "
                + _ZENDESK_LOGIN_HINT
            ),
            jira_key=jira_key,
        )
        return {"result": "AlreadySet", "details": "Parameter already exists"}

    try:
        response = allow_zendesk_login(user_email, access_token)
        print(f"enable_zendesk_login: response → {response.json()}")
        print(
            f"enable_zendesk_login: parameter set for {user_email}. "
            f"Go to {_ZENDESK_LOGIN_URL} and click 'I'm an agent'."
        )
        send_jira_comment(
            message=(
                "A necessary parameter was set.\n "
                + _ZENDESK_LOGIN_HINT
            ),
            jira_key=jira_key,
        )
        return {"result": "Success", "details": "Parameter set successfully"}

    except Exception as exc:
        fl.error(f"enable_zendesk_login: exception → {exc}")
        send_jira_comment(
            message=f"An error occurred when trying to provide access to Zendesk:\n{exc}",
            jira_key=jira_key,
        )
        return {"result": "Exception", "details": str(exc)}

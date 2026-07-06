"""
Jira service.

Wraps Jira Cloud REST API v2/v3 calls:
  - user creation
  - group membership
  - issue comments
"""

from __future__ import annotations

import json

import requests

from app.config import settings


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def adding_jira_cloud_user(suggested_email: str):
    """Create a new Jira Cloud user by email.

    https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-users/#api-rest-api-3-user-post
    Returns (status_code, response_json).
    """
    url = "https://junehomes.atlassian.net/rest/api/3/user"
    payload = json.dumps({"emailAddress": suggested_email})
    headers = {
        "Authorization": settings.jira_api,
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, data=payload)
    return response.status_code, response.json()


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

def adding_jira_user_to_group(account_id: str, group_id: str):
    """Add a Jira user (by accountId) to a group (by groupId).

    https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-groups/#api-rest-api-3-group-user-post
    Returns (status_code, response_json).
    """
    url = f"https://junehomes.atlassian.net/rest/api/3/group/user?groupId={group_id}"
    payload = json.dumps({"accountId": account_id})
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": settings.jira_api,
    }
    response = requests.post(url, headers=headers, data=payload)
    return response.status_code, response.json()


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def send_jira_comment(message, jira_key: str):
    """Post a comment to a Jira issue.

    Accepts either a plain string (API v2) or an Atlassian Document Format
    dict (API v3).  Returns the raw requests.Response object.
    """
    headers = {
        "Authorization": settings.jira_api,
        "Content-Type": "application/json",
    }
    if isinstance(message, dict):
        url = f"https://junehomes.atlassian.net/rest/api/3/issue/{jira_key}/comment"
        data = json.dumps({"body": message})
    else:
        url = f"https://junehomes.atlassian.net/rest/api/2/issue/{jira_key}/comment"
        data = json.dumps({"body": str(message)})

    return requests.post(url=url, headers=headers, data=data)

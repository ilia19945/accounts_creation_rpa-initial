"""
Services package.

Public re-exports for convenient importing:

    from app.services import (
        create_google_user_req,
        adding_jira_cloud_user,
        send_jira_comment,
        ...
    )
"""

from app.services.google_workspace import (
    get_app_info,
    get_actual_token,
    get_new_access_token,
    exchange_auth_code_to_access_refresh_token,
    refresh_token_func,
    create_google_user_req,
    assign_google_license,
    adding_user_to_google_group,
    adding_to_junehomes_dev_calendar,
    allow_zendesk_login,
)

from app.services.jira import (
    adding_jira_cloud_user,
    adding_jira_user_to_group,
    send_jira_comment,
)

__all__ = [
    # Google Workspace
    "get_app_info",
    "get_actual_token",
    "get_new_access_token",
    "exchange_auth_code_to_access_refresh_token",
    "refresh_token_func",
    "create_google_user_req",
    "assign_google_license",
    "adding_user_to_google_group",
    "adding_to_junehomes_dev_calendar",
    "allow_zendesk_login",
    # Jira
    "adding_jira_cloud_user",
    "adding_jira_user_to_group",
    "send_jira_comment",
]

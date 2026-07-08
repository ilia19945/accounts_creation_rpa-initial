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

from app.services.email import (
    send_gmail_message,
    create_draft_message,
)

from app.services.slack import (
    compare_role_configs_slack,
)

from app.services.amazon_connect import (
    delete_amazon_user,
    compare_role_configs_amazonconnect,
)

from app.services.juneos import (
    juneos_devprod_authorization,
    create_juneos_user,
    get_juneos_groups_from_position_title,
    assign_groups_to_user,
    compare_role_configs_juneos,
)

from app.services.zendesk import (
    check_zendesk_login_param,
    enable_zendesk_login,
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
    # Email / Gmail
    "send_gmail_message",
    "create_draft_message",
    # Slack
    "compare_role_configs_slack",
    # Amazon Connect
    "delete_amazon_user",
    "compare_role_configs_amazonconnect",
    # JuneOS
    "juneos_devprod_authorization",
    "create_juneos_user",
    "get_juneos_groups_from_position_title",
    "assign_groups_to_user",
    "compare_role_configs_juneos",
    # Zendesk
    "check_zendesk_login_param",
    "enable_zendesk_login",
]

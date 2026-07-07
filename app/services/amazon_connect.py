"""
Amazon Connect service.

Wraps boto3 calls for Amazon Connect user management.

The Celery task that *creates* Amazon users (``create_amazon_user``) lives in
``tasks.py`` and will be migrated to ``tasks/account_tasks.py`` on Day 7.
"""

from __future__ import annotations

import boto3

import app.utils.logging as fl

# Legacy JuneHomes Amazon Connect instance ID.
# The active USRENTAPTS instance used by the Celery create_amazon_user task
# is defined in root-level config.py as ``instance_id``.
_JH_INSTANCE_ID = "a016cbe1-24bf-483a-b2cf-a73f2f389cb4"


def delete_amazon_user(user_email: str) -> dict:
    """Delete an Amazon Connect user.

    Args:
        user_email: The email address of the user to delete.

    Returns:
        The raw boto3 response dict.

    Note:
        A user-lookup step (``search_users`` → resolve email to ``UserId``)
        is required before this function can be called with a real user.
        The ``user_id`` variable below is left as a TODO stub.
    """
    # TODO: implement lookup — call client.search_users() to resolve
    # user_email → UserId before deleting.
    user_id = ""

    client = boto3.client("connect")
    response = client.delete_user(
        InstanceId=_JH_INSTANCE_ID,
        UserId=user_id,
    )
    return response


def compare_role_configs_amazonconnect() -> None:
    """Stub: placeholder for Amazon Connect role-config comparison logic."""
    print("сравнили конфиги в амазоне :)")

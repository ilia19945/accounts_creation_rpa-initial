"""
Email / Gmail service.

Provides helper functions to send Gmail messages and create drafts
via the Gmail REST API (OAuth Bearer-token flow).

Note: the Celery task variant of ``send_gmail_message`` (which uses SMTP)
lives in ``tasks.py`` and will be migrated to ``tasks/email_tasks.py``
on Day 7 of the refactor.
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText

import requests

from app.services.google_workspace import get_actual_token
import app.utils.logging as fl


def send_gmail_message(
    sender: str,
    to: str,
    cc: str,
    subject: str,
    message_text: str,
):
    """Send a message through the Gmail REST API (OAuth Bearer-token variant).

    Returns ``(message_id, label_ids)`` on success or the error dict on failure.

    Note: the SMTP-based Celery task with the same name lives in ``tasks.py``
    and is scheduled for extraction to ``tasks/email_tasks.py`` on Day 7.
    """
    message = MIMEText(message_text, "html")
    message["to"] = to
    message["from"] = sender
    message["cc"] = cc
    message["subject"] = subject
    raw_message = base64.urlsafe_b64encode(message.as_string().encode()).decode()

    url = f"https://gmail.googleapis.com/gmail/v1/users/{sender}/messages/send"
    headers = {
        "Authorization": f"Bearer {get_actual_token('access_token')}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {"raw": raw_message}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code < 300:
        return response.json()["id"], response.json()["labelIds"]
    return response.json()["error"]


def create_draft_message(
    sender: str,
    to: str,
    cc: str,
    subject: str,
    message_text: str,
):
    """Create a Gmail draft via the REST API.

    Returns ``(draft_id, label_ids)`` on success or the error dict on failure.
    """
    message = MIMEText(message_text, "html")
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject
    message["cc"] = cc
    raw_message = base64.urlsafe_b64encode(message.as_string().encode()).decode()

    url = f"https://gmail.googleapis.com/gmail/v1/users/{sender}/drafts"
    headers = {
        "Authorization": f"Bearer {get_actual_token('access_token')}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {"message": {"raw": raw_message}}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code < 300:
        return response.json()["id"], response.json()["message"]["labelIds"]
    return response.json()["error"]

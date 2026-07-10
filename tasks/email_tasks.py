"""
Email Celery tasks.

Contains send_gmail_message — used by most other tasks to dispatch
credential / notification emails via Gmail SMTP.
"""

import smtplib
from email.mime.text import MIMEText

import app.utils.logging as fl
from app.config import settings

from tasks.celery_app import celery_app


@celery_app.task
def send_gmail_message(sender, to, cc, subject, message_text, hire_start_date):
    fl.info(f'A new task is received. Email subject: {subject}. To: {to}. Countdown at:{hire_start_date} UTC.')

    message = MIMEText(message_text, 'html')
    message['from'] = sender
    message['to'] = ",".join(to)
    message['cc'] = ",".join(cc)
    message['subject'] = subject

    recipients = to + cc

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender, settings.gmail_app_password)
    server.sendmail(from_addr=sender, to_addrs=recipients, msg=message.as_string())
    server.quit()
    fl.info(f'Message will be sent to:{to}, at: {hire_start_date}')
    return f'Message was successfully sent to:{to}, at: {hire_start_date}'

"""
Google Workspace Celery tasks.

Creates Google accounts, assigns licences and groups, adds calendar
access, and schedules credential e-mails via send_gmail_message.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from jinja2 import Environment, FileSystemLoader

import app.utils.logging as fl
from app.services.google_workspace import (
    adding_to_junehomes_dev_calendar,
    adding_user_to_google_group,
    assign_google_license,
    create_google_user_req,
)
from app.services.jira import adding_jira_cloud_user, send_jira_comment
from config import email_cc_list, google_license_skus  # legacy constants — not yet in app.config
from funcs import create_elk_user  # TODO: extract to app/services/elk.py

from tasks.celery_app import celery_app
from tasks.email_tasks import send_gmail_message

_env = Environment(loader=FileSystemLoader("email_templates"))


@celery_app.task
def async_google_account_license_groups_calendar_creation(
        first_name,
        last_name,
        suggested_email,
        organizational_unit,
        gmail_groups,
        hire_start_date,
        personal_email,
        supervisor_email,
        role_title,
        jira_key,
):
    hire_start_date = datetime.strptime(hire_start_date, '%Y-%m-%dT%H:%M:%S.%f')

    google_user = create_google_user_req(first_name, last_name, suggested_email, organizational_unit)

    if google_user[0] < 300:
        google_password = google_user[2]
        print('This is your google password:', google_password)
        fl.info(f"User {first_name} {last_name} is created. Username: {suggested_email}\n")
        send_jira_comment(
            f"(1/3) User *{first_name} {last_name}* is successfully created!\n"
            f"User Email: *{suggested_email}*\n",
            jira_key,
        )

        # Licence assignment based on department/role
        if organizational_unit == 'Sales' and role_title != 'Vendor Tour Manager':
            assigned_license = assign_google_license(
                google_license_skus["Google Workspace Business Plus"], suggested_email
            )
            license_name = list(google_license_skus)[1]
        else:
            assigned_license = assign_google_license(
                google_license_skus["G Suite Business"], suggested_email
            )
            license_name = list(google_license_skus)[0]

        if assigned_license[0] < 300:
            send_jira_comment(f"(2/3) *{license_name}* license, successfully assigned!", jira_key)
            fl.info(f"{license_name} license, assigned")
        elif assigned_license[0] == 412:
            send_jira_comment(f"Not enough licenses. Google error:\n{assigned_license[1]}", jira_key)
            fl.error(f"Not enough licenses. Google error:\n{assigned_license[1]}")
        else:
            send_jira_comment(
                "An error appeared while assigning google license.\n"
                f"Error code: {assigned_license[0]}\n"
                f"Error message: {assigned_license[1]['error']['message']}",
                jira_key,
            )
            fl.error(
                f"Error code: {assigned_license[0]}\n"
                f"Error message: {assigned_license[1]['error']['message']}"
            )

        fl.info(f"gmail_groups to assign: {str(gmail_groups)}")
        final_row = adding_user_to_google_group(gmail_groups, suggested_email)
        fl.info(f"Groups assigned: {final_row}")
        send_jira_comment(f"(3/3) Assigned google groups:\n{final_row}", jira_key)

        if organizational_unit == 'Technology':
            # Ping IT support head via Jira comment
            message = open("mention_itsupport_head.txt", "r", encoding="UTF-8").read()
            send_jira_comment(
                message=json.loads(message.replace('suggested_email', suggested_email)),
                jira_key=jira_key,
            )

            # Add employee to the junehomes-dev calendar
            calendar_id = 'junehomes.com_6f1l2kssibhmsg10e7fvnmdv1o@group.calendar.google.com'
            calendar_result = adding_to_junehomes_dev_calendar(
                suggested_email=suggested_email, calendar_id=calendar_id
            )
            if calendar_result[0] < 300:
                fl.info(f"User *{suggested_email}* is added to *[junehomes-dev calendar|]*.")
                send_jira_comment(
                    f"User *{suggested_email}* is added to *[junehomes-dev "
                    "calendar|https://calendar.google.com/calendar/u/0/r/settings/calendar/"
                    "anVuZWhvbWVzLmNvbV82ZjFsMmtzc2liaG1zZzEwZTdmdm5tZHYxb0Bncm91cC5jYWxlbmRhci5nb29nbGUuY29t?pli=1]*.",
                    jira_key,
                )
            else:
                msg = (
                    f"An error occured while trying to add a User: *{suggested_email}* "
                    "to *[junehomes-dev calendar|]*.\n"
                    f"Error code: *{calendar_result[0]}*\n"
                    f"Error body: {calendar_result[1]}"
                )
                fl.info(msg)
                send_jira_comment(msg, jira_key=jira_key)

            # Create Jira account
            adding_user_to_jira = adding_jira_cloud_user(suggested_email=suggested_email)
            if adding_user_to_jira[0] < 300:
                fl.info(f"Jira user *{suggested_email}* is created.")
                send_jira_comment(f"Jira user *{suggested_email}* is created.", jira_key)
            else:
                err = (
                    f"An error occurred while creating Jira user *{suggested_email}*.\n"
                    f"Error code: {adding_user_to_jira[0]} \n"
                    f"Error body: {adding_user_to_jira[1]}"
                )
                fl.info(err)
                send_jira_comment(err, jira_key)

            # ELK Development
            try:
                elk_dev = create_elk_user(
                    firstname=first_name, lastname=last_name,
                    suggested_email=suggested_email, role='viewer', dev_or_prod='dev',
                )
            except Exception as e:
                send_jira_comment(
                    f'An error occurred when trying to add a user on ELK DEV:\n{e}', jira_key
                )
            else:
                if elk_dev[0].status_code < 300:
                    fl.info(f'ELK Dev user is created. Credentials will be sent at: {hire_start_date} UTC.')
                    send_jira_comment(
                        f'ELK Dev user is created. ELK dev credentials will be sent in: {hire_start_date} UTC.',
                        jira_key,
                    )
                    draft = _env.get_template("kibana_jinja.txt").render(
                        first_name=first_name, suggested_email=suggested_email,
                        stage="Development", password=elk_dev[1],
                    )
                    send_gmail_message.apply_async(
                        ('ilya.konovalov@junehomes.com', [personal_email],
                         email_cc_list + [supervisor_email],
                         'Your Kibana.Development credentials.', draft, hire_start_date),
                        queue='new_emps',
                        eta=hire_start_date + timedelta(minutes=2),
                    )
                else:
                    fl.info(
                        f'ELK Dev user is NOT created!\n'
                        f'Response:{elk_dev[0].status_code}\n{elk_dev[0].json()}'
                    )
                    send_jira_comment(
                        f'ELK Dev user is *NOT created*!\n'
                        f'Response:{elk_dev[0].status_code}\n{elk_dev[0].json()}',
                        jira_key,
                    )

            # ELK Production
            try:
                elk_prod = create_elk_user(
                    firstname=first_name, lastname=last_name,
                    suggested_email=suggested_email, role='viewer', dev_or_prod='prod',
                )
            except Exception as e:
                send_jira_comment(
                    f'An error occurred when trying to add a user on ELK PROD:\n{e}', jira_key
                )
            else:
                if elk_prod[0].status_code < 300:
                    draft = _env.get_template("kibana_jinja.txt").render(
                        first_name=first_name, suggested_email=suggested_email,
                        stage="Production", password=elk_dev[1],  # noqa: F821 — set in ELK Dev block
                    )
                    send_gmail_message.apply_async(
                        ('ilya.konovalov@junehomes.com', [personal_email],
                         email_cc_list + [supervisor_email],
                         'Your Kibana.Production credentials.', draft, hire_start_date),
                        queue='new_emps',
                        eta=hire_start_date + timedelta(minutes=2),
                    )
                    fl.info(f'ELK Prod user is created. Credentials will be sent at: {hire_start_date} UTC.')
                    send_jira_comment(
                        f'ELK Prod user is created. ELK Prod credentials will be sent in: {hire_start_date} UTC.',
                        jira_key,
                    )
                else:
                    fl.info(
                        f'ELK Prod user is *NOT created!* '
                        f'Response: {elk_prod[0].status_code} {elk_prod[0].json()}'
                    )
                    send_jira_comment(
                        f'ELK Prod user is NOT created!\n'
                        f'Response:{elk_prod[0].status_code}\n{elk_prod[0].json()}',
                        jira_key,
                    )

        # Send corporate email credentials
        draft = _env.get_template("google_mail_jinja.txt").render(
            first_name=first_name, suggested_email=suggested_email, password=google_password,
        )
        print(draft)
        send_gmail_message.apply_async(
            ('ilya.konovalov@junehomes.com', [personal_email],
             email_cc_list + [supervisor_email],
             'June Homes: corporate email account', draft, hire_start_date),
            queue='new_emps',
            eta=hire_start_date + timedelta(minutes=2),
        )
        fl.info(f'June Homes: corporate email account will be sent at {hire_start_date} UTC')
        send_jira_comment(
            f"*June Homes: corporate email account* email will be sent to\n "
            f"User: *{suggested_email}*\n"
            f"At: *{hire_start_date}* UTC.\n",
            jira_key,
        )

        # IT services & policies email
        if organizational_unit == 'Resident Experience':
            template_name = 'it_services_and_policies_support.txt'
        else:
            template_name = 'it_services_and_policies_wo_trello_zendesk.txt'
        draft = _env.get_template(template_name).render()
        send_gmail_message.apply_async(
            ('ilya.konovalov@junehomes.com', [suggested_email], [],
             'IT services and policies', draft, hire_start_date),
            queue='new_emps',
            eta=hire_start_date + timedelta(minutes=10),
        )
        fl.info(f"IT services and policies email will be sent at {hire_start_date} UTC.")
        send_jira_comment(
            f"Final is reached!\n*IT services and policies* email will be sent at {hire_start_date} UTC",
            jira_key=jira_key,
        )

    else:
        send_jira_comment(
            "An error occurred while creating a google user!\n"
            f"Error code: {google_user[0]}\n"
            f"Error response: {google_user[1]}",
            jira_key,
        )

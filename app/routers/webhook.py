"""
Jira webhook routers.

Handles incoming Jira webhook events for two hiring workflows:

  POST /webhook             — employee/contractor hiring (general)
  POST /maintenance_hiring  — maintenance staff hiring

Original location: ``mainfastapi.py`` → ``employee_contract_main_flow`` and
``maintenance_main_flow``.
"""

import os
import os.path
import random
import re
import shutil
import string
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Body, Response
from jinja2 import Environment, FileSystemLoader

import fast_api_logging as fl
import funcs as f
from config import (
    countdown_for_it_content,
    countdown_for_others_depts,
    roles_dict,
    email_cc_list,
)
from tasks import (
    async_google_account_license_groups_calendar_creation,
    check_zendesk_login,
    create_amazon_user,
    new_check_role_and_permissions,
    send_gmail_message,
)

from app.routers import shared_state

router = APIRouter()

data_folder = Path(".")

loader = FileSystemLoader("email_templates")
env = Environment(loader=loader)


# ── /webhook — employee / contractor hiring ────────────────────────────────────

@router.post("/webhook", status_code=200)
async def employee_contract_main_flow(body: dict = Body(...)):
    """Main flow for employee/contractor Jira webhook events."""

    shared_state.jira_key = body["issue"]["key"]

    detect_change_type = body["changelog"]["items"][0]["field"]
    detect_action = body["changelog"]["items"][0]["toString"]
    fl.info(f"Change type: {detect_change_type}")

    if detect_change_type != "status":
        fl.info(
            f'The field "{detect_change_type}" was changed to: "{detect_action}". '
            "Nothing will be done. Awaiting for the other request"
        )
        return

    jira_old_status = body["changelog"]["items"][0]["fromString"]
    jira_new_status = body["changelog"]["items"][0]["toString"]
    jira_description = re.split(r": |\n", body["issue"]["fields"]["description"])
    fl.info(f"Key: {shared_state.jira_key}")
    fl.info(f"Old Status: {jira_old_status}; New Status: {jira_new_status}")

    role_title = jira_description[jira_description.index("*Role title*") + 1]

    # ── Organizational unit ──────────────────────────────────────────────────
    try:
        organizational_unit = f.fetching_params_from_file(
            filename_contains="googleworkspace",
            jsonvalue="Organizational Unit",
            position_title=role_title,
            jira_key=shared_state.jira_key,
        )
        print("the value is taken from config on Notion")
    except Exception as e:
        print(
            "Couldn't take the *Organizational unit* from *googleworkspace* file config.\n"
            f"Error: [{e}]\nTrying to take the value from ticket description..."
        )
        try:
            organizational_unit = jira_description[
                jira_description.index("*Organizational unit*") + 1
            ]
            print("the value is taken from jira description")
        except Exception as e:
            f.send_jira_comment(
                "Couldn't take the *Organizational unit* from ticket description...\n"
                f"Error: [{e}]\n"
                "Make sure the Org Unit exists on Google Workspace.",
                shared_state.jira_key,
            )
            return

    print(f"Organizational unit: {organizational_unit}")
    first_name = jira_description[jira_description.index("*First name*") + 1]
    last_name = jira_description[jira_description.index("*Last name*") + 1]
    if organizational_unit == "Sales":
        last_name = last_name[0]

    personal_email = jira_description[
        jira_description.index("*Personal email*") + 1
    ].split("|")[0][
        0 : len(jira_description[jira_description.index("*Personal email*") + 1])
    ]
    if personal_email[0:1] == "[":
        personal_email = personal_email[1:]
    elif personal_email == "":
        personal_email = jira_description[
            jira_description.index("h4. Persona.l email") + 1
        ].split("|")[0]
        if personal_email[0:1] == "[":
            personal_email = personal_email[1:]

    suggested_email = jira_description[
        jira_description.index("*Suggested name@junehomes.com*") + 1
    ].split("|")[0]
    if suggested_email[0:1] == "[":
        suggested_email = suggested_email[1:]
    elif suggested_email == "":
        suggested_email = jira_description[
            jira_description.index("*Suggested name@junehomes.com*") + 1
        ].split("|")[0]
        if suggested_email[0:1] == "[":
            suggested_email = suggested_email[1:]

    personal_phone = jira_description[
        jira_description.index("*Personal phone number (with country code)*") + 1
    ]
    supervisor_email = jira_description[jira_description.index("*Supervisor*") + 1]

    hire_start_date = jira_description[
        jira_description.index(
            "*Start date (IT needs 3 WORKING days to create accounts)*"
        )
        + 1
    ]
    hire_start_date = datetime.strptime(hire_start_date, "%m/%d/%Y")

    user_email_analogy = jira_description[
        jira_description.index(
            "*If needs access to the telephony system, describe details (e.g. permissions and settings like which existing user?)*"
        )
        + 1
    ]

    if organizational_unit in ["Technology", "Brand Marketing"]:
        hire_start_date += countdown_for_it_content
    else:
        hire_start_date += countdown_for_others_depts

    fl.info(f"ETA for the task execution: {str(hire_start_date)}")
    if hire_start_date < datetime.now():
        hire_start_date = datetime.now() + timedelta(minutes=2)

    fl.info(f"Task ETA: {hire_start_date} UTC")

    # ── Status-specific handlers ─────────────────────────────────────────────

    if jira_new_status == "Create a google account":
        fl.info(f"Key: {shared_state.jira_key}")
        fl.info("Correct event to create user Google account detected. Perform user creation attempt ...")
        fl.info(f"timestamp: {str(body['timestamp'])}")
        fl.info(f"webhookEvent: {body['webhookEvent']}")
        fl.info(f"user: {body['user']['accountId']}")

        try:
            access_token = f.get_actual_token("access_token")
            fl.debug(access_token)
            expires_in_time = f.get_actual_token("expires_in")
            fl.info(expires_in_time)
            token_datetime = f.get_actual_token("datetime")
            fl.info(token_datetime)
        except Exception as error:
            return fl.error(error)

        token_datetime = f.get_actual_token("datetime")
        current_time = int(time.time())
        token_time = current_time - int(token_datetime)

        try:
            gmail_groups = f.fetching_params_from_file(
                filename_contains="googleworkspace",
                jsonvalue="Groups",
                position_title=role_title,
                jira_key=shared_state.jira_key,
            )
            if gmail_groups is None:
                pass
            if "team@junehomes.com" not in gmail_groups:
                gmail_groups.append("team@junehomes.com")
        except Exception as e:
            print(f"Error: {e}")
            gmail_groups = jira_description[
                jira_description.index("*Gmail - which groups needs access to*") + 1
            ].split(",")
            gmail_groups_refined = [g.strip() for g in gmail_groups]
            if "team@junehomes.com" not in gmail_groups_refined:
                gmail_groups_refined.append("team@junehomes.com")
            gmail_groups = [i for i in gmail_groups_refined if i]

        try:
            organizational_unit = f.fetching_params_from_file(
                filename_contains="googleworkspace",
                jsonvalue="Organizational Unit",
                position_title=role_title,
                jira_key=shared_state.jira_key,
            )
        except Exception as e:
            print(f"Error occurred on: {e}")
            organizational_unit = jira_description[
                jira_description.index("*Organizational unit*") + 1
            ]

        fl.info(
            msg=f"Access_token: {access_token}\n"
            f"datetime: {expires_in_time}\n"
            f"first_name: {first_name}\n"
            f"last_name: {last_name}\n"
            f"personal_email: {personal_email}\n"
            f"suggested_email: {suggested_email}\n"
            f"organizational_unit: {organizational_unit}\n"
            f"personal_phone:{personal_phone}\n"
            f"gmail_groups (list): {str(gmail_groups)}\n"
            f"hire_start_date: {hire_start_date}\n"
            f"Token lifetime: {token_time}\n"
            f"token_datetime:{token_datetime}\n"
        )

        if token_time >= expires_in_time:
            fl.info('Access token expired! Trying to get get_actual_token("refresh_token")...')
            try:
                refresh_token = f.get_actual_token("refresh_token")
                fl.info(f"Refresh_token: {refresh_token}")
            except KeyError:
                fl.info("Refresh token wasn't found in the last google response.")
                new_access_token = f.get_new_access_token()
                fl.info(new_access_token)
                jira_comment_response = f.send_jira_comment(
                    "*Access token expired!*\nNew access token should be requested before moving forward. "
                    "Press {color:red}*[Pass Google Authorization|"
                    + new_access_token
                    + "]*{color} button "
                    "and accept app permissions (if asked).\n"
                    "⚠ *REMEMBER: IT'S ONE TIME LINK! SHOULD BE DELETED AFTER REFRESHING* ⚠\n"
                    "(It's recommended to open in a new browser tab)\n",
                    shared_state.jira_key,
                )
                if jira_comment_response.status_code > 300:
                    fl.error(f"Jira comment wasn't added. {jira_comment_response.json()}")
                fl.info("Jira comment was added successfully")
            else:
                fl.info("Refresh token was provided by google. Refresh token_func() is executed \n")
                f.refresh_token_func()
                f.send_jira_comment(
                    "Current access_token expired. It was automatically refreshed. "
                    "Please try to create google account for the user again.\n"
                    '(Switch the ticket status -> "In Progress" -> "Create a Google account")',
                    shared_state.jira_key,
                )
        else:
            import requests as _requests

            fl.info("Access token is actual. Suggested user email will be checked to the uniqueness.")
            url = f"https://admin.googleapis.com/admin/directory/v1/users/{suggested_email}"
            headers = {"Authorization": f'Bearer {f.get_actual_token("access_token")}'}
            check_for_user_existence = _requests.get(url=url, headers=headers, data={})

            if check_for_user_existence.status_code < 300:
                print(f"The account ({suggested_email}) is already exist!")
                f.send_jira_comment(
                    f"The account ({suggested_email}) *is already exist*!\n"
                    "Check suggested email field and try again.",
                    shared_state.jira_key,
                )
            else:
                print(
                    f'Celery task to create Google account for *"{suggested_email}"* is added.\nPlease, wait...'
                )
                f.send_jira_comment(
                    f'*Celery task* to create *Google account* for *"{suggested_email}"* is added.\nPlease, wait...',
                    shared_state.jira_key,
                )
                async_google_account_license_groups_calendar_creation.apply_async(
                    (
                        first_name,
                        last_name,
                        suggested_email,
                        organizational_unit,
                        gmail_groups,
                        hire_start_date,
                        personal_email,
                        supervisor_email,
                        role_title,
                        shared_state.jira_key,
                    ),
                    queue="new_emps",
                )

    elif jira_new_status == "Create a FrontApp account":
        try:
            frontapp_role_name = f.fetching_params_from_file(
                filename_contains="frontapp",
                jsonvalue="teammate_template_id",
                position_title=role_title,
                jira_key=shared_state.jira_key,
            )
            print("role is taken from config on Notion:", frontapp_role_name)
            frontapp_role = roles_dict[frontapp_role_name]
        except Exception as e:
            print(f"Error: {e}")
            try:
                frontapp_role = jira_description[
                    jira_description.index("*If needs FrontApp, select a user role*") + 1
                ]
            except Exception as e:
                print(f"Error: {e}")
                return f.send_jira_comment(
                    "An error occurred while trying to get the information from ticket description config:\n"
                    f"{e}",
                    shared_state.jira_key,
                )
            else:
                try:
                    frontapp_role = roles_dict[frontapp_role]
                    print("role is taken from jira ticket description!")
                except Exception as e:
                    print(f"Error: {e}")
                    return f.send_jira_comment(
                        f"The Frontapp role *{frontapp_role}* was found on the description,"
                        f" but the teammate_template_id wasn't found on server config. Error:\n"
                        f"{e}\nAdd the role to configs.py or make sure the correct "
                        f'*"teammate_template_id": "value"* is filled up on Notion of this role.',
                        shared_state.jira_key,
                    )

        fl.info(f"Frontapp role: {frontapp_role}")
        print("Frontapp role:", frontapp_role)

        try:
            frontapp_user = f.create_frontapp_user(
                suggested_email=suggested_email,
                first_name=first_name,
                last_name=last_name,
                frontapp_role=frontapp_role,
            )
            fl.info(f"Status code: {str(frontapp_user[0])}")
            if frontapp_user[0] > 300:
                fl.error(
                    f"an error occurred on trying to create an account: {frontapp_user[0]}, "
                    f"error: {frontapp_user[1]}"
                )
            else:
                fl.info(frontapp_user[1])
                f.send_jira_comment(
                    jira_key=shared_state.jira_key,
                    message="Frontapp User *successfully* created!\n"
                    f"User email: *{suggested_email}*.\n",
                )
        except KeyError:
            fl.error("the role doesn't exist")
            f.send_jira_comment(
                jira_key=shared_state.jira_key,
                message=f'The role specified for a frontapp user: "{frontapp_role}" - *doesn\'t exist!*\n'
                f"The list of the roles:\n {roles_dict.keys()}",
            )

    elif jira_new_status == "Create an Amazon account":
        fl.info(f'Analogy to create the User on Amazon: "{user_email_analogy}"')
        try:
            user_email_analogy = f.fetching_params_from_file(
                filename_contains="amazonconnect",
                jsonvalue="user_email_analogy",
                position_title=role_title,
                jira_key=shared_state.jira_key,
            )
        except Exception as e:
            print(f"Error: {e}")
            return f.send_jira_comment(
                "An error occurred while trying to get the information from Amazon config:\n" f"{e}",
                shared_state.jira_key,
            )

        if user_email_analogy in ("", "N/A ", " ", "-"):
            f.send_jira_comment("not a user email!", jira_key=shared_state.jira_key)
            fl.error(f'not a user email: "{user_email_analogy}"')
        else:
            print(user_email_analogy)
            characters = string.ascii_letters + string.digits + string.punctuation
            password = "".join(random.choice(characters) for _ in range(16))

            template = env.get_template(name="amazon_connect_jinja.txt")
            final_draft = template.render(
                first_name=first_name,
                suggested_email=suggested_email.split("@")[0] + "@usrentapts.com",
                amazon_password=password,
            )
            create_amazon_user.apply_async(
                (
                    suggested_email,
                    first_name,
                    last_name,
                    user_email_analogy,
                    password,
                    final_draft,
                    hire_start_date,
                    shared_state.jira_key,
                ),
                queue="other",
            )
        return

    elif jira_new_status == "Create a JuneOS account":
        try:
            organizational_unit = f.fetching_params_from_file(
                filename_contains="googleworkspace",
                jsonvalue="Organizational Unit",
                position_title=role_title,
                jira_key=shared_state.jira_key,
            )
            print("The organizational_unit:", organizational_unit)
            print("the information is taken from config on Notion")
        except Exception as e:
            print(f"Error: {e}")
            organizational_unit = jira_description[
                jira_description.index("*Organizational unit*") + 1
            ]
            print("the information is taken from description!")
        fl.info(organizational_unit)

        if organizational_unit == "Technology":
            juneos_user = f.create_juneos_user(
                first_name=first_name,
                last_name=last_name,
                suggested_email=suggested_email,
                personal_phone=personal_phone,
                dev_or_prod="dev",
            )
            if juneos_user.status_code < 300:
                fl.info("JuneOS user created!")
                f.send_jira_comment(
                    "*JuneOS development* user created.\n"
                    f"Username: *{suggested_email}*, \n"
                    f"*[User link|https://dev.junehomes.net/december_access/users/user/{juneos_user.json()['user']['id']}/change/] "
                    f"(Don't forget to make him a superuser on JuneOS.Development.)*.\n"
                    f"Credentials will be sent at: {hire_start_date}.",
                    jira_key=shared_state.jira_key,
                )
                template = env.get_template(name="juneos_dev_jinja.txt")
                final_draft = template.render(
                    first_name=first_name, suggested_email=suggested_email
                )
                send_gmail_message.apply_async(
                    (
                        "ilya.konovalov@junehomes.com",
                        [suggested_email],
                        email_cc_list,
                        "Access to JuneOS.Development property management system",
                        final_draft,
                        hire_start_date,
                    ),
                    queue="new_emps",
                    eta=hire_start_date,
                )
                fl.info(f"Email will be sent: {hire_start_date} UTC")
            else:
                fl.error(
                    "An error occurred while creating a JuneOS.Development user.\n"
                    f"Error code: *{juneos_user.status_code}* \n\n"
                    f'*{juneos_user.json()["errors"]}*'
                )
                f.send_jira_comment(
                    "An error occurred while creating a JuneOS.Development user.\n"
                    f"Error code: *{juneos_user.status_code}* \n\n"
                    f'*{juneos_user.json()["errors"]}*',
                    jira_key=shared_state.jira_key,
                )

        print(f"organizational_unit [{organizational_unit}] received.")
        try:
            groups = f.fetching_params_from_file(
                filename_contains="juneos",
                jsonvalue="groups",
                position_title=role_title,
                jira_key=shared_state.jira_key,
            )
            if groups is None:
                pass
        except Exception as e:
            print(f"Couldn't get the value from JuneOS file config. Error: {e}")
            try:
                if organizational_unit == "Sales":
                    groups = f.get_juneos_groups_from_position_title(
                        file_name="groups_sales.json"
                    )[role_title]
                elif organizational_unit == "Resident Experience":
                    groups = f.get_juneos_groups_from_position_title(
                        file_name="groups_resident_experience.json"
                    )[role_title]
                elif organizational_unit == "Performance Marketing":
                    groups = f.get_juneos_groups_from_position_title(
                        file_name="groups_performance_marketing.json"
                    )[role_title]
                else:
                    groups = f.get_juneos_groups_from_position_title(
                        file_name=f"groups_{organizational_unit}.json"
                    )[role_title]
                fl.info(f"the group was found! \n{str(groups)}")
            except Exception as error:
                fl.error(error)
                f.send_jira_comment(
                    "An error occurred while trying to search a user role both on Notion and on disk:\n"
                    f"*{error}* for *{organizational_unit}*.\n"
                    "Check if role exists in /permissions_by_orgunits/*groups_YOUR_ORG_UNIT_NAME.json*"
                    " in and update .json or in *Notion*. Then try again.",
                    jira_key=shared_state.jira_key,
                )
                return KeyError(error)
        else:
            print("Trying to get the config from prefilled file on the disk...")

        print("Trying to create a JuneOS user")
        juneos_user = f.create_juneos_user(
            first_name=first_name,
            last_name=last_name,
            suggested_email=suggested_email,
            personal_phone=personal_phone,
            dev_or_prod="prod",
        )

        if juneos_user.status_code < 300:
            fl.info(f"*JuneOS* user created. Username: *{suggested_email}*, \n")
            template = env.get_template(name="juneos_jinja.txt")
            final_draft = template.render(
                first_name=first_name, suggested_email=suggested_email
            )
            send_gmail_message.apply_async(
                (
                    "ilya.konovalov@junehomes.com",
                    [suggested_email],
                    email_cc_list,
                    "Access to JuneOS property management system",
                    final_draft,
                    hire_start_date,
                ),
                queue="new_emps",
                eta=hire_start_date,
            )
            fl.info(
                f"email 'Access to JuneOS property management system' will be sent at:{hire_start_date}, \n"
            )

            if role_title == "Property manager":
                link = f"*Don't forget to add user to *{role_title}s* on juneOS.*\n*[LINK|https://junehomes.com/december_access/staff/propertymanager/add/]*"
            elif role_title == "City manager":
                link = f"*Don't forget to add user to *{role_title}s* on juneOS.*\n*[LINK|https://junehomes.com/december_access/staff/citymanager/add/]*"
            elif "support" in role_title.strip().lower() and organizational_unit in [
                "Resident Experience",
                "Resident Experience (incl. Design and Launches)",
            ]:
                link = "*Don't forget to add user to *Agents* on juneOS.*\n*[LINK|https://junehomes.com/december_access/staff/agent/add/]*"
            elif ("success" in role_title.strip().lower() or "sales" in role_title.strip().lower()) and organizational_unit == "Sales":
                link = (
                    "*Don't forget to add user to *Lead Owners* on juneOS.*\n"
                    "*[LINK|https://junehomes.com/december_access/staff/team/add/]*\n"
                    "Remember we use agent arn for amazon (not queue arn) since 1st Dec. 2022."
                )
            else:
                link = ""

            f.send_jira_comment(
                "*JuneOS* user created.\n"
                f"Username: *{suggested_email.strip()}*, \n"
                f"*[User link|https://junehomes.com/december_access/users/user/{juneos_user.json()['user']['id']}/change/]*.\n"
                f"Credentials will be sent at: {hire_start_date}.\n"
                f"{link}",
                jira_key=shared_state.jira_key,
            )

            try:
                juneos_auth = f.juneos_devprod_authorization(dev_or_prod="prod")
            except Exception as error:
                fl.error(error)

            if juneos_auth.status_code < 300:
                csrftoken = juneos_auth.cookies["csrftoken"]
                sessionid = juneos_auth.cookies["sessionid"]
                token = juneos_auth.json()["token"]
                juneos_user_id = juneos_user.json()["user"]["id"]

                fl.info(f"successfully authenticated in JuneOS production: {str(juneos_auth.status_code)}")
                fl.info("Trying to Assign groups")

                try:
                    assigned_groups = f.assign_groups_to_user(
                        user_id=juneos_user_id,
                        groups=groups,
                        dev_or_prod="prod",
                        token=token,
                        csrftoken=csrftoken,
                        sessionid=sessionid,
                    )
                except Exception as error:
                    fl.error(error)

                if assigned_groups[0] < 300:
                    fl.info("groups assigned")
                    f.send_jira_comment(
                        "Groups in JuneOS are assigned to *[user|https://junehomes.com/december_access/"
                        f"users/user/{juneos_user_id}/change/]*.\n",
                        jira_key=shared_state.jira_key,
                    )
                else:
                    f.send_jira_comment(
                        "An error occurred while assigning groups to JuneOS user.\n"
                        f"Error code: *{assigned_groups[0]}* \n\n"
                        f"*{assigned_groups[1]}*",
                        jira_key=shared_state.jira_key,
                    )
                    fl.error(
                        "An error occurred while assigning groups to JuneOS user.\n"
                        f"Error code: *{assigned_groups[0]}* \n\n"
                        f"*{assigned_groups[1]}"
                    )
            else:
                fl.error(
                    "An error occurred while trying to authenticate on JuneOS.\n"
                    f"Error code: *{juneos_auth.status_code}* \n\n"
                    f"*{juneos_auth.text}*"
                )
                f.send_jira_comment(
                    "An error occurred while trying to authenticate on JuneOS.\n"
                    f"Error code: *{juneos_auth.status_code}* \n\n"
                    f"*{juneos_auth.json()}*",
                    jira_key=shared_state.jira_key,
                )
        else:
            fl.error(
                "An error occurred while creating a JuneOS user.\n"
                f"Error code: *{juneos_user.status_code}* \n\n"
                f'*{juneos_user.json()["errors"]}*'
            )
            f.send_jira_comment(
                "An error occurred while creating a JuneOS user.\n"
                f"Error code: *{juneos_user.status_code}* \n\n"
                f'*{juneos_user.json()["errors"]}*',
                jira_key=shared_state.jira_key,
            )
        return

    elif jira_new_status == "Create a Zendesk account":
        access_token = f.get_actual_token("access_token")
        token_datetime = f.get_actual_token("datetime")
        expires_in_time = f.get_actual_token("expires_in")
        current_time = int(time.time())

        if int(token_datetime) + int(expires_in_time) < current_time:
            print("Token Expired, needs to be refreshed")
            f.send_jira_comment(
                "*Access to Google workspace has expired!*\n"
                "Can't set the parameter allowing to the agent to login to Zendesk on Google Workspace.\n "
                "Please, refresh google access by clicking on \"Create a google account\" on Jira ticket and request new Access Token",
                jira_key=shared_state.jira_key,
            )

        check_zendesk_login.apply_async(
            (suggested_email, access_token, shared_state.jira_key),
            queue="new_emps",
        )

    elif jira_new_status == "Check Role and Permissions":
        new_check_role_and_permissions.apply_async(
            (role_title, shared_state.jira_key), queue="other"
        )
        return

    elif jira_new_status in ["Done", "Rejected"]:
        try:
            path = data_folder / "roles_configs" / shared_state.jira_key
            if os.path.exists(path) and os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            print("Exception:", e)

    else:
        fl.info(
            "Got a status change different from what triggers the user account creation. "
            "Waiting for a valid status change..."
        )


# ── /maintenance_hiring — maintenance staff hiring ─────────────────────────────

@router.post("/maintenance_hiring", status_code=200)
async def maintenance_main_flow(body: dict = Body(...)):
    """Main flow for maintenance employee Jira webhook events."""

    shared_state.jira_key = body["issue"]["key"]

    detect_change_type = body["changelog"]["items"][0]["field"]
    detect_action = body["changelog"]["items"][0]["toString"]
    fl.info(f"Change type: {detect_change_type}")

    if detect_change_type != "status":
        fl.info(
            f'The field "{detect_change_type}" was changed to: "{detect_action}". '
            "Nothing will be done. Awaiting for the other request"
        )
        return

    jira_old_status = body["changelog"]["items"][0]["fromString"]
    jira_new_status = body["changelog"]["items"][0]["toString"]
    jira_description = re.split(r": |\n", body["issue"]["fields"]["description"])
    fl.info(f"Key: {shared_state.jira_key}")
    fl.info(f"Old Status: {jira_old_status}; New Status: {jira_new_status}")
    print(jira_description)

    position_title = jira_description[jira_description.index("*Position title*") + 1]
    first_name = jira_description[jira_description.index("*First name*") + 1]
    last_name = jira_description[jira_description.index("*Last name*") + 1]
    suggested_email = first_name.lower() + "." + last_name.lower() + "@junehomes.com"

    personal_email = jira_description[
        jira_description.index("*Personal email*") + 1
    ].split("|")[0][
        0 : len(jira_description[jira_description.index("*Personal email*") + 1])
    ]
    if personal_email[0:1] == "[":
        personal_email = personal_email[1:]
    elif personal_email == "":
        personal_email = jira_description[
            jira_description.index("h4. Personal email") + 1
        ].split("|")[0]
        if personal_email[0:1] == "[":
            personal_email = personal_email[1:]

    personal_phone = jira_description[
        jira_description.index("*Personal phone number*") + 1
    ]
    supervisor_email = jira_description[
        jira_description.index("*Supervisor (whom reports to)*") + 1
    ]

    start_date = jira_description[
        jira_description.index(
            "*Start date (IT needs 3 working days to create accounts)*"
        )
        + 1
    ]
    hire_start_date = datetime.strptime(start_date, "%m/%d/%Y")
    hire_start_date += countdown_for_others_depts

    if hire_start_date < datetime.now():
        hire_start_date = datetime.now() + timedelta(minutes=2)

    fl.info(f"Task ETA: {hire_start_date}")

    if jira_new_status == "Create a JuneOS account":
        fl.info("Maintenance employee")
        try:
            groups = f.fetching_params_from_file(
                filename_contains="juneos",
                jsonvalue="groups",
                position_title=position_title,
                jira_key=shared_state.jira_key,
            )
            if groups is None:
                return f.send_jira_comment(
                    "No groups are found on the file for JuneOS Config.",
                    shared_state.jira_key,
                )
        except Exception as error:
            print(f"Couldn't get the value from JuneOS file config. Error: {error}")
            fl.error(error)
            f.send_jira_comment(
                f"An error occurred while trying to search a user position:\n"
                f"*{error}* for *{position_title}*.\n"
                "Check if position exists in /permissions_by_orgunits/*groups_maintenance.json*"
                " in and update json. Then try again.",
                jira_key=shared_state.jira_key,
            )
            return Response(content={}, status_code=200)
        else:
            juneos_user = f.create_juneos_user(
                first_name=first_name,
                last_name=last_name,
                suggested_email=personal_email,
                personal_phone=personal_phone,
                dev_or_prod="prod",
            )

            if juneos_user.status_code < 300:
                fl.info(f"User: {personal_email} is created successfully!")

                template = env.get_template(name="juneos_jinja.txt")
                final_draft = template.render(
                    first_name=first_name, suggested_email=personal_email
                )
                send_gmail_message.apply_async(
                    (
                        "ilya.konovalov@junehomes.com",
                        [personal_email],
                        email_cc_list,
                        "Access to JuneOS property management system",
                        final_draft,
                        hire_start_date,
                    ),
                    queue="new_emps",
                    eta=hire_start_date,
                )
                fl.info(
                    f"email 'Access to JuneOS property management system' will be sent at: {hire_start_date} \n"
                )

                template = env.get_template(
                    name="it_services_and_policies_wo_trello_zendesk.txt"
                )
                final_draft = template.render()
                send_gmail_message.apply_async(
                    (
                        "ilya.konovalov@junehomes.com",
                        [personal_email],
                        [],
                        "IT services and policies",
                        final_draft,
                        hire_start_date,
                    ),
                    queue="new_emps",
                    eta=hire_start_date + timedelta(minutes=5),
                )
                fl.info(f"IT services and policies email will be sent at {hire_start_date}.")
                f.send_jira_comment(
                    f"*IT services and policies* email will be sent at *{hire_start_date}* UTC.",
                    jira_key=shared_state.jira_key,
                )

                if position_title == "Property manager":
                    link = "propertymanager/add/"
                elif position_title == "Housekeeper":
                    link = "housekeeper/add/"
                elif position_title == "City manager":
                    link = "citymanager/add/"
                else:
                    link = ""

                f.send_jira_comment(
                    "*JuneOS* user created.\n"
                    f"Username: *{personal_email}*, \n"
                    f"*[User link|https://junehomes.com/december_access/users/user/{juneos_user.json()['user']['id']}/change/]*.\n"
                    f"Credentials will be sent at: *{hire_start_date}* UTC.\n"
                    f"*Don't forget to add user to {position_title}s on juneOS.*\n"
                    f"*[LINK|https://junehomes.com/december_access/staff/{link}]*\n"
                    f"and on *[Vendors|https://junehomes.com/december_access/users/uservendor/] and then assign vendor "
                    f"to this [user|https://junehomes.com/december_access/users/user/{juneos_user.json()['user']['id']}/change/]",
                    jira_key=shared_state.jira_key,
                )

                try:
                    juneos_auth = f.juneos_devprod_authorization(dev_or_prod="prod")
                except Exception as error:
                    fl.error(error)

                if juneos_auth.status_code < 300:
                    csrftoken = juneos_auth.cookies["csrftoken"]
                    sessionid = juneos_auth.cookies["sessionid"]
                    token = juneos_auth.json()["token"]
                    juneos_user_id = juneos_user.json()["user"]["id"]

                    fl.info(
                        f"successfully authenticated in JuneOS production: {str(juneos_auth.status_code)}"
                    )
                    fl.info("Trying to Assign groups")

                    try:
                        assigned_groups = f.assign_groups_to_user(
                            user_id=juneos_user_id,
                            groups=groups,
                            dev_or_prod="prod",
                            token=token,
                            csrftoken=csrftoken,
                            sessionid=sessionid,
                        )
                    except Exception as error:
                        fl.error(error)

                    if assigned_groups[0] < 300:
                        fl.info("groups assigned")
                        f.send_jira_comment(
                            "Groups in JuneOS are assigned to *[user|https://junehomes.com/december_access/"
                            f"users/user/{juneos_user_id}/change/]*.\n",
                            jira_key=shared_state.jira_key,
                        )
                    else:
                        f.send_jira_comment(
                            "An error occurred while assigning groups to JuneOS user.\n"
                            f"Error code: *{assigned_groups[0]}* \n\n"
                            f"*{assigned_groups[1]}*",
                            jira_key=shared_state.jira_key,
                        )
                        fl.error(
                            "An error occurred while assigning groups to JuneOS user.\n"
                            f"Error code: *{assigned_groups[0]}* \n\n"
                            f"*{assigned_groups[1]}"
                        )
                else:
                    fl.info(
                        "An error occurred while trying to authenticate on JuneOS.\n"
                        f"Error code: *{juneos_auth.status_code}* \n\n"
                        f"*{juneos_auth.json()}*"
                    )
                    f.send_jira_comment(
                        "An error occurred while trying to authenticate on JuneOS.\n"
                        f"Error code: *{juneos_auth.status_code}* \n\n"
                        f"*{juneos_auth.json()}*",
                        jira_key=shared_state.jira_key,
                    )
            else:
                fl.error(
                    "An error occurred while creating a JuneOS user.\n"
                    f"Error code: *{juneos_user.status_code}* \n\n"
                    f'*{juneos_user.json()["errors"]}*'
                )
                f.send_jira_comment(
                    "An error occurred while creating a JuneOS user.\n"
                    f"Error code: *{juneos_user.status_code}* \n\n"
                    f'*{juneos_user.json()["errors"]}*',
                    jira_key=shared_state.jira_key,
                )

    elif jira_new_status == "Check Role and Permissions":
        new_check_role_and_permissions.apply_async(
            (position_title, shared_state.jira_key), queue="other"
        )

    elif jira_new_status == "Create a google account":
        fl.info(f"Key: {shared_state.jira_key}")
        fl.info("Correct event to create user Google account detected. Perform user creation attempt ...")
        fl.info(f"timestamp: {str(body['timestamp'])}")
        fl.info(f"webhookEvent: {body['webhookEvent']}")
        fl.info(f"user: {body['user']['accountId']}")

        try:
            access_token = f.get_actual_token("access_token")
            fl.debug(access_token)
            expires_in_time = f.get_actual_token("expires_in")
            fl.info(expires_in_time)
            token_datetime = f.get_actual_token("datetime")
            fl.info(token_datetime)
        except Exception as error:
            return fl.error(error)

        token_datetime = f.get_actual_token("datetime")
        current_time = int(time.time())
        token_time = current_time - int(token_datetime)

        try:
            gmail_groups = f.fetching_params_from_file(
                filename_contains="googleworkspace",
                jsonvalue="Groups",
                position_title=position_title,
                jira_key=shared_state.jira_key,
            )
            if gmail_groups is None:
                pass
            if "team@junehomes.com" not in gmail_groups:
                gmail_groups.append("team@junehomes.com")
        except Exception as e:
            print(f"Error: {e}")
            gmail_groups = ["team@junehomes.com"]

        try:
            organizational_unit = f.fetching_params_from_file(
                filename_contains="googleworkspace",
                jsonvalue="Organizational Unit",
                position_title=position_title,
                jira_key=shared_state.jira_key,
            )
        except Exception as e:
            print(f"Error occurred on: {e}")
            organizational_unit = "Resident Experience"

        fl.info(
            msg=f"Access_token: {access_token}\n"
            f"datetime: {expires_in_time}\n"
            f"first_name: {first_name}\n"
            f"last_name: {last_name}\n"
            f"personal_email: {personal_email}\n"
            f"suggested_email: {first_name} + '.' + {last_name}@junehomes.com\n"
            f"organizational_unit: {organizational_unit}\n"
            f"personal_phone:{personal_phone}\n"
            f"gmail_groups (list): {str(gmail_groups)}\n"
            f"hire_start_date: {hire_start_date}\n"
            f"Token lifetime: {token_time}\n"
            f"token_datetime:{token_datetime}\n"
        )

        if token_time >= expires_in_time:
            fl.info('Access token expired! Trying to get get_actual_token("refresh_token")...')
            try:
                refresh_token = f.get_actual_token("refresh_token")
                fl.info(f"Refresh_token: {refresh_token}")
            except KeyError:
                fl.info("Refresh token wasn't found in the last google response.")
                new_access_token = f.get_new_access_token()
                fl.info(new_access_token)
                jira_comment_response = f.send_jira_comment(
                    "*Access token expired!*\nNew access token should be requested before moving forward. "
                    "Press {color:red}*[Pass Google Authorization|"
                    + new_access_token
                    + "]*{color} button "
                    "and accept app permissions (if asked).\n"
                    "⚠ *REMEMBER: IT'S ONE TIME LINK! SHOULD BE DELETED AFTER REFRESHING* ⚠\n"
                    "(It's recommended to open in a new browser tab)\n",
                    shared_state.jira_key,
                )
                if jira_comment_response.status_code > 300:
                    fl.error(f"Jira comment wasn't added. {jira_comment_response.json()}")
                fl.info("Jira comment was added successfully")
            else:
                fl.info("Refresh token was provided by google. Refresh token_func() is executed \n")
                f.refresh_token_func()
                f.send_jira_comment(
                    "Current access_token expired. It was automatically refreshed. "
                    "Please try to create google account for the user again.\n"
                    '(Switch the ticket status -> "In Progress" -> "Create a Google account")',
                    shared_state.jira_key,
                )
        else:
            import requests as _requests

            fl.info("Access token is actual. Suggested user email will be checked to the uniqueness.")
            url = f"https://admin.googleapis.com/admin/directory/v1/users/{suggested_email}"
            headers = {"Authorization": f'Bearer {f.get_actual_token("access_token")}'}
            check_for_user_existence = _requests.get(url=url, headers=headers, data={})

            if check_for_user_existence.status_code < 300:
                print(f"The account ({suggested_email}) is already exist!")
                f.send_jira_comment(
                    f"The account ({suggested_email}) *is already exist*!\n"
                    "Check suggested email field and try again.\n"
                    "P.S. Remember for Maintenance emps the correct emails format is: "
                    '"*first_name.last_name@junehomes.com*", so update the jira ticket if necessary',
                    shared_state.jira_key,
                )
            else:
                print(
                    f'Celery task to create Google account for *"{suggested_email}"* is added.\nPlease, wait...'
                )
                f.send_jira_comment(
                    f'*Celery task* to create *Google account* for *"{suggested_email}"* is added.\nPlease, wait...',
                    shared_state.jira_key,
                )
                async_google_account_license_groups_calendar_creation.apply_async(
                    (
                        first_name,
                        last_name,
                        suggested_email,
                        organizational_unit,
                        gmail_groups,
                        hire_start_date,
                        personal_email,
                        supervisor_email,
                        position_title,
                        shared_state.jira_key,
                    ),
                    queue="new_emps",
                )

    elif jira_new_status in ["Done", "Rejected"]:
        try:
            path = data_folder / "roles_configs" / shared_state.jira_key
            if os.path.exists(path) and os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            print("Exception:", e)

    elif jira_new_status not in [
        "In Progress",
        "Rejected",
        "Waiting for dev",
        "Waiting for reply",
    ]:
        f.send_jira_comment(
            "*Creating a Google account* and *Creating a JuneOS account* are the only available status for the maintenance employees.",
            jira_key=shared_state.jira_key,
        )
    else:
        pass

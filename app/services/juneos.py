"""
JuneOS API service.

Handles authentication, user creation, group assignment,
and permission-config comparison for the JuneOS property-management system.
"""

import json
import string
import random
import os
from pathlib import Path

import requests

import app.utils.logging as fl

# ── env vars ──────────────────────────────────────────────────────────────────
juneos_dev_password: str = os.environ.get("JUNEOS_DEV_PASSWORD", "")
juneos_prod_login: str = os.environ.get("JUNEOS_PROD_LOGIN", "")
juneos_prod_password: str = os.environ.get("JUNEOS_PROD_PASSWORD", "")

data_folder = Path(".")


# ── auth ──────────────────────────────────────────────────────────────────────

def juneos_devprod_authorization(dev_or_prod: str):
    """
    Obtain a session token from JuneOS (dev or prod).

    Returns the raw ``requests.Response`` on success, or ``None`` on bad param.
    """
    if dev_or_prod == "dev":
        url = "https://dev.junehomes.net/api/v2/auth/login-web-token/"
        payload = json.dumps({
            "email": "ilya.konovalov@junehomes.com",
            "password": juneos_dev_password,
        })
    elif dev_or_prod == "prod":
        url = "https://junehomes.com/api/v2/auth/login-web-token/"
        payload = json.dumps({
            "email": juneos_prod_login,
            "password": juneos_prod_password,
        })
    else:
        fl.error("juneos_devprod_authorization: invalid dev_or_prod param")
        return None

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        return response
    except Exception as exc:
        fl.error(f"Error sending request to JuneOS: {exc}")
        return None


# ── user creation ─────────────────────────────────────────────────────────────

def create_juneos_user(
    first_name: str,
    last_name: str,
    suggested_email: str,
    personal_phone: str,
    dev_or_prod: str,
):
    """
    Register a new staff user in JuneOS (dev or prod).

    Returns the raw ``requests.Response``, or ``None`` on bad param.
    """
    if dev_or_prod == "dev":
        url = "https://dev.junehomes.net/api/v2/auth/registration/"
    elif dev_or_prod == "prod":
        url = "https://junehomes.com/api/v2/auth/registration/"
    else:
        fl.error("create_juneos_user: invalid dev_or_prod param")
        return None

    characters = string.ascii_letters + string.digits + string.punctuation
    password = "".join(random.choice(characters) for _ in range(35))

    fl.info(f"create_juneos_user: suggested_email={suggested_email}")
    fl.debug(f"create_juneos_user: generated password (redacted in prod logs)")

    payload = json.dumps({
        "email": suggested_email,
        "first_name": first_name,
        "last_name": last_name,
        "phone": personal_phone,
        "password": password,
        "password2": password,
        "subscribe": True,
        "is_staff": True,
    })

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
    }

    return requests.post(url, headers=headers, data=payload)


# ── group helpers ─────────────────────────────────────────────────────────────

def get_juneos_groups_from_position_title(file_name: str) -> dict:
    """
    Load a JuneOS groups mapping from ``permissions_by_orgunits/<file_name>``.

    Returns the parsed JSON dict.
    """
    file_to_open = data_folder / "permissions_by_orgunits" / file_name
    with open(file_to_open, "r") as fh:
        return json.loads(fh.read())


def assign_groups_to_user(
    user_id: int,
    groups: list,
    dev_or_prod: str,
    csrftoken: str,
    sessionid: str,
    token: str,
):
    """
    PATCH a JuneOS user to assign the given group list.

    Returns ``(status_code, response_json)``.
    """
    if dev_or_prod == "prod":
        fl.info("assign_groups_to_user: targeting prod")
        url = f"https://junehomes.com/api/v2/auth/users/{user_id}/"
    elif dev_or_prod == "dev":
        fl.info("assign_groups_to_user: targeting dev")
        url = f"https://dev.junehomes.net/api/v2/auth/users/{user_id}/"
    else:
        return 500, "Error: invalid dev_or_prod param"

    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "Cookie": f"csrftoken={csrftoken}; sessionid={sessionid}",
    }
    payload = json.dumps({"is_staff": True, "groups": groups})

    response = requests.patch(url, headers=headers, data=payload)
    fl.info(response.json())
    return response.status_code, response.json()


# ── permission-config comparison ──────────────────────────────────────────────

def compare_role_configs_juneos(
    current_json_object: dict,
    antecedent_json_object: dict,
) -> dict:
    """
    Merge *antecedent* JuneOS config values into *current*, extending lists
    and overriding integers when they diverge.

    Returns the updated ``current_json_object``.
    """
    for c_key, c_value in current_json_object.items():
        for a_key, a_value in antecedent_json_object.items():
            if c_key != a_key or a_value == c_value:
                continue

            if isinstance(c_value, list):
                for item in a_value:
                    if item not in c_value:
                        c_value.append(item)
                print(f"compare_role_configs_juneos: merged list for key '{c_key}':", c_value)
            elif isinstance(c_value, int):
                current_json_object[c_key] = a_value
            else:
                print(
                    f"compare_role_configs_juneos: unexpected type for key "
                    f"'{c_key}': {type(c_value)}"
                )

    return current_json_object

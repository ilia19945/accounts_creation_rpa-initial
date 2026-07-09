"""
Google OAuth2 redirect router.

Handles the OAuth2 callback from Google:

  GET /   — receives the authorisation code (or error) that Google redirects
             to after the user approves (or denies) the OAuth consent screen.

Original location: ``mainfastapi.py`` → ``redirect_from_google``.
"""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import fast_api_logging as fl
import funcs as f

from app.routers import shared_state

router = APIRouter()


@router.get("/")
async def redirect_from_google(
    code: Optional[str] = Query(
        None,
        description=(
            "authorisation code from Google — "
            "https://developers.google.com/identity/protocols/oauth2/web-server"
            "#exchange-authorization-code"
        ),
    ),
    error: str = Query(
        None,
        description="Error param that Google sends when the user denies authorization.",
    ),
):
    """Catch the OAuth2 redirect from Google and exchange the code for tokens."""

    if code and error:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Bad request. Parameters 'code'={code} and 'error'={error} "
                "can't be in the same query."
            ),
        )

    elif code:
        if 60 < len(code) < 85:  # Google auth codes are ~73-75 chars
            fl.info("Received a request with code from google")

            with open("authorization_codes.txt", "a+") as fh:
                fh.write(str(time.asctime()) + ";" + code + "\n")

            fl.info(f"Jira key: {shared_state.jira_key}")

            try:
                f.exchange_auth_code_to_access_refresh_token(code)
            except Exception as e:
                fl.info(e)
                f.send_jira_comment(
                    "An error occurred while trying to refresh the code:\n" f"{e}",
                    shared_state.jira_key,
                )
            else:
                fl.info(
                    "Step 5 executed successfully! Auth code has been exchanged to an "
                    "access token.\nPlease repeat creating a user account attempt."
                )
                f.send_jira_comment(
                    "Current Auth token was irrelevant and has been exchanged to a new token.\n"
                    "Please repeat creating a user account attempt.\n"
                    '(Switch the ticket status -> *"In Progress"* -> *"Create a Google account!"*)',
                    shared_state.jira_key,
                )

            return {
                "event": (
                    "The authorization code has been caught and saved. "
                    "Close this page and go back to jira ticket tab, please."
                )
            }

        else:
            fl.info(f"seems like a wrong value has been sent in the code parameter: {code}")
            return "Are you serious, bro? Is that really a code from google?"

    elif error:
        fl.error("User denied to confirm the permissions!\nMain flow is stopped!")
        return "User denied to confirm the permissions! Main flow is stopped!"

    else:
        fl.error("Received a random request")
        return {"response": "Why are you on this page?=.="}

"""
Pydantic schemas for the Jira webhook payload.

These models represent the structure sent by Jira to the ``/webhook`` and
``/maintenance_hiring`` endpoints, giving FastAPI proper request validation
and IDE-friendly attribute access in place of raw ``dict`` indexing.

Jira webhook docs:
https://developer.atlassian.com/server/jira/platform/webhooks/
"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ── changelog ─────────────────────────────────────────────────────────────────

class ChangelogItem(BaseModel):
    """A single field change inside a Jira changelog entry."""

    field: str = Field(..., description="Name of the changed field, e.g. 'status'.")
    fieldtype: Optional[str] = None
    from_: Optional[str] = Field(None, alias="from", description="Previous raw value.")
    fromString: Optional[str] = Field(None, description="Previous human-readable value.")
    to: Optional[str] = Field(None, description="New raw value.")
    toString: Optional[str] = Field(None, description="New human-readable value.")

    class Config:
        populate_by_name = True  # allow both alias and field name


class Changelog(BaseModel):
    """Container for the list of field changes in this webhook event."""

    id: Optional[str] = None
    items: List[ChangelogItem] = Field(default_factory=list)


# ── issue ─────────────────────────────────────────────────────────────────────

class JiraIssueFields(BaseModel):
    """Subset of Jira issue fields used by the webhook handler."""

    summary: Optional[str] = None
    description: Optional[str] = Field(
        None,
        description=(
            "Raw Jira wiki-markup description. "
            "The webhook handler splits this on ': ' and '\\n' to extract "
            "field values such as 'First name', 'Last name', etc."
        ),
    )
    status: Optional[Any] = None
    issuetype: Optional[Any] = None
    priority: Optional[Any] = None
    assignee: Optional[Any] = None
    reporter: Optional[Any] = None

    class Config:
        extra = "allow"  # Jira sends many more fields; ignore unknown ones


class JiraIssue(BaseModel):
    """Minimal representation of a Jira issue as received in the webhook."""

    id: Optional[str] = None
    key: str = Field(..., description="Issue key, e.g. 'IT-123'.")
    self_url: Optional[str] = Field(None, alias="self")
    fields: JiraIssueFields = Field(default_factory=JiraIssueFields)

    class Config:
        populate_by_name = True


# ── user ──────────────────────────────────────────────────────────────────────

class JiraWebhookUser(BaseModel):
    """Jira user that triggered the webhook event."""

    accountId: str
    displayName: Optional[str] = None
    emailAddress: Optional[str] = None

    class Config:
        extra = "allow"


# ── top-level payload ─────────────────────────────────────────────────────────

class JiraWebhookPayload(BaseModel):
    """
    Root model for the Jira webhook POST body.

    Usage in a FastAPI route::

        @app.post("/webhook", status_code=200)
        async def employee_contract_main_flow(body: JiraWebhookPayload):
            jira_key = body.issue.key
            change = body.changelog.items[0]
            if change.field == "status":
                ...
    """

    timestamp: Optional[int] = Field(
        None,
        description="Unix epoch milliseconds when the event was emitted.",
    )
    webhookEvent: Optional[str] = Field(
        None,
        description="Event type, e.g. 'jira:issue_updated'.",
    )
    issue_event_type_name: Optional[str] = None
    user: Optional[JiraWebhookUser] = None
    issue: JiraIssue
    changelog: Changelog = Field(default_factory=Changelog)

    class Config:
        extra = "allow"

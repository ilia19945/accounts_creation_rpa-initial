"""
Shared mutable state for the FastAPI application.

Replicates the ``global jira_key`` that existed in ``mainfastapi.py``.
Both the auth and webhook routers reference the same module object, so
mutations performed by one router are visible to the other.

NOTE: This is intentionally **not** thread-safe — the original implementation
      was not thread-safe either.  Proper fixup (e.g. contextvars or a DB)
      is left for a future refactoring pass.
"""

# Last Jira issue key received by a webhook event.
# The Google OAuth callback uses it to post a follow-up comment.
jira_key: str = ""

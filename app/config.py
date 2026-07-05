"""
Application settings loaded from environment variables (or .env file).

Uses pydantic BaseSettings (pydantic v1) so every field is validated
and the full configuration is available as a single typed object:

    from app.config import settings

    client_id = settings.google_client_id
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """All application settings, sourced from environment variables."""

    # --- Google OAuth ---
    google_client_id: str = Field(..., env="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(..., env="GOOGLE_CLIENT_SECRET")

    # --- Jira ---
    jira_api: str = Field(..., env="JIRA_API")

    # --- FrontApp ---
    frontapp_api: str = Field(..., env="FRONTAPP_API")

    # --- Gmail SMTP ---
    gmail_app_password: str = Field(..., env="GMAIL_APP_PASSWORD")

    # --- JuneOS ---
    juneos_dev_password: str = Field(..., env="JUNEOS_DEV_PASSWORD")
    juneos_prod_login: str = Field(..., env="JUNEOS_PROD_LOGIN")
    juneos_prod_password: str = Field(..., env="JUNEOS_PROD_PASSWORD")

    # --- ELK (note: original env-var names were intentionally swapped — kept as-is) ---
    elk_prod: Optional[str] = Field(None, env="ELK_DEV")
    elk_dev: Optional[str] = Field(None, env="ELK_PROD")

    # --- Notion ---
    notion_secret: Optional[str] = Field(None, env="NOTION_SECRET")

    class Config:
        env_file = Path(__file__).parent.parent / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton — import this throughout the codebase
settings = Settings()

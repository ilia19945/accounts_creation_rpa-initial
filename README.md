# 🚀 Accounts Creation RPA

> Full automation of IT-Support new-hire onboarding: account creation, permissions, and notifications.

## What it does

1. Receives Jira webhook events (ticket status / description changes)
2. Provisions accounts across Google Workspace, Amazon Connect, Zendesk, Notion, and more
3. Schedules welcome emails via Celery
4. Notifies IT agents with results and required manual steps

**Before:** ~1.5 hours per new hire → **After:** ~10–15 minutes ✅

---

## Project Structure

```
.
├── app/
│   ├── main.py                 # FastAPI entry point, router registration
│   ├── config.py               # Pydantic Settings (loaded from .env)
│   ├── models/
│   │   └── schemas.py          # Pydantic schemas for Jira webhook payload
│   ├── routers/
│   │   ├── auth.py             # Google OAuth2 callback
│   │   ├── webhook.py          # Jira webhook handler + business logic
│   │   └── health.py           # /health endpoint
│   ├── services/               # One module per external service
│   │   ├── google_workspace.py
│   │   ├── amazon_connect.py
│   │   ├── zendesk.py
│   │   ├── jira.py
│   │   ├── slack.py
│   │   ├── email.py
│   │   └── juneos.py
│   └── utils/
│       └── logging.py          # Logging config
├── tasks/
│   ├── celery_app.py           # Celery + Redis broker init
│   ├── email_tasks.py          # Scheduled email delivery
│   ├── google_tasks.py         # Google account creation task
│   └── account_tasks.py        # Amazon Connect, Zendesk, Notion checks
├── roles_configs/              # Role → permissions YAML/JSON
├── email_templates/            # Jinja2 email templates
├── docker-compose.yml
├── dockerfile
├── requirements.txt
├── Makefile
└── .env.example
```

---

## Stack

| Layer   | Tech                        |
|---------|-----------------------------|
| API     | FastAPI + Uvicorn           |
| Queue   | Celery 5 + Redis            |
| GUI     | Flower                      |
| Infra   | Docker Compose              |

---

## Quick Start

```bash
cp .env.example .env     # fill in secrets
make up                  # build + start all services
make logs                # follow logs
make stop                # stop everything
```

| Service | URL                          |
|---------|------------------------------|
| API     | http://localhost:8000        |
| Flower  | http://localhost:5555 (admin:admin) |

---

## How It Works

```
Jira webhook
    │
    ▼
POST /webhook/jira          (FastAPI, app/routers/webhook.py)
    │
    ├─► validate payload     (app/models/schemas.py)
    │
    ├─► route by ticket type
    │       ├── new_emps  ──► tasks/google_tasks.py + tasks/account_tasks.py
    │       ├── terminations ► tasks/account_tasks.py
    │       └── other     ──► tasks/email_tasks.py
    │
    └─► on success: schedule welcome email + Slack notification to IT agent
        on failure: post formatted error to Jira ticket
```

Celery workers consume from three queues: `new_emps`, `terminations`, `other`.

---

## Role Model

Roles are defined in Notion databases and support:

- **Inheritance** — Senior Dev inherits Middle + Junior permissions
- **Service matching** — config auto-updates when a role changes
- **Error notifications** — failures surface back to the Jira ticket

---

## Environment Variables

See `.env.example` for the full list. Key groups:

| Group             | Variables                              |
|-------------------|----------------------------------------|
| Google OAuth      | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, … |
| Celery / Redis    | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Jira              | `JIRA_URL`, `JIRA_TOKEN`, …            |
| Slack             | `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`  |
| Amazon Connect    | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, … |
| Zendesk           | `ZENDESK_URL`, `ZENDESK_TOKEN`, …      |
| Notion            | `NOTION_TOKEN`, `NOTION_DB_ID`         |

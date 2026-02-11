# Architecture Overview

## System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE                         │
│                                                         │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │ main.py  │──▶│ scheduler.py │──▶│ orchestrator.py│  │
│  └──────────┘   └──────┬───────┘   └───────┬────────┘  │
│                         │                   │           │
│                  ┌──────┴───────┐    ┌──────┴────────┐  │
│                  │   Watchers   │    │  Claude CLI   │  │
│                  │ • filesystem │    │  (subprocess)  │  │
│                  │ • gmail      │    └───────┬────────┘  │
│                  └──────────────┘            │           │
│                                     ┌───────┴────────┐  │
│  ┌─────────────────────────────────┤  MCP Servers    │  │
│  │  Skills                         │ • email-server  │  │
│  │  • linkedin_poster.py           │ • odoo-server   │  │
│  │  • meta_poster.py               │ • social-server │  │
│  │  • twitter_poster.py            └────────────────┘  │
│  │  • weekly_audit.py                                   │
│  │  • task_state.py (Ralph Wiggum)                      │
│  └──────────────────────────────────────────────────────│
│                                                         │
│  ┌──────────────────────────────┐                       │
│  │   AI_Employee_Vault/         │  (Obsidian vault)     │
│  │   ├── Inbox/                 │                       │
│  │   ├── Needs_Action/          │                       │
│  │   ├── In_Progress/           │                       │
│  │   ├── Pending_Approval/      │                       │
│  │   ├── Approved/              │                       │
│  │   ├── Rejected/              │                       │
│  │   ├── Done/                  │                       │
│  │   ├── Logs/                  │                       │
│  │   ├── Briefings/             │                       │
│  │   ├── Plans/                 │                       │
│  │   ├── Dashboard.md           │                       │
│  │   ├── Company_Handbook.md    │                       │
│  │   └── Business_Goals.md      │                       │
│  └──────────────────────────────┘                       │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS / API calls
        ┌────────────┼────────────────────┐
        │            │                    │
        ▼            ▼                    ▼
┌──────────────┐ ┌────────────┐  ┌──────────────────┐
│ Azure ACI    │ │  Neon DB   │  │  Cloud APIs       │
│ (Odoo 19)   │ │ (Postgres) │  │ • Gmail API       │
│ :8069       │──▶│            │  │ • LinkedIn API    │
└──────────────┘ └────────────┘  │ • Meta Graph API  │
                                  │ • Twitter API v2  │
                                  └──────────────────┘
```

## Component Descriptions

### Entry Points
- **`main.py`** — CLI entry point. Launches watcher, orchestrator, or full scheduler.
- **`scheduler.py`** — Combines all jobs on a schedule (Gmail polling, task processing, social media drafts, weekly audit).
- **`orchestrator.py`** — Core coordinator: reads pending tasks, invokes Claude CLI, handles approvals, updates dashboard.

### Watchers
- **`watchers/filesystem_watcher.py`** — Watchdog-based monitor on `Inbox/`. New files trigger triage to `Needs_Action/`.
- **`watchers/gmail_watcher.py`** — Polls Gmail API for unread emails, creates `EMAIL_*.md` in `Needs_Action/`.

### Skills (Business Logic)
- **`skills/linkedin_poster.py`** — Creates LinkedIn drafts, executes approved posts via REST API.
- **`skills/meta_poster.py`** — Facebook Page and Instagram posting via Meta Graph API.
- **`skills/twitter_poster.py`** — Tweet posting via Twitter API v2 (tweepy).
- **`skills/weekly_audit.py`** — Aggregates weekly data, generates Weekly Summary and CEO Briefing.
- **`skills/task_state.py`** — Multi-step task tracking for the Ralph Wiggum loop.

### MCP Servers (Tool Providers for Claude)
- **`mcp_servers/email_server.py`** — Gmail send/draft/list tools.
- **`mcp_servers/odoo_server.py`** — Odoo accounting tools (invoices, payments, balances, P&L).
- **`mcp_servers/social_server.py`** — Social media posting and draft tools.

### Utilities
- **`utils/retry.py`** — Exponential backoff, graceful degradation, health checker singleton.
- **`utils/frontmatter.py`** — Parse/create YAML frontmatter from markdown files.
- **`utils/audit.py`** — Consistent audit logging wrapper.

### Hooks
- **`.claude/hooks/stop.py`** — Ralph Wiggum stop hook. Blocks Claude exit when multi-step task has incomplete steps.

## Data Flow

1. **Input**: Files dropped in `Inbox/` or emails arriving in Gmail.
2. **Triage**: Watchers create `.md` metadata files in `Needs_Action/`.
3. **Processing**: Orchestrator reads `Needs_Action/`, invokes Claude CLI per task.
4. **Approval**: Sensitive actions → `Pending_Approval/` → human moves to `Approved/` or `Rejected/`.
5. **Execution**: Orchestrator picks up approved files, delegates to appropriate skill module.
6. **Archival**: Completed tasks → `Done/`, all actions → `Logs/`.
7. **Reporting**: Scheduler triggers daily briefings, weekly audits, CEO briefings.

## Cloud vs Local

| Component | Location | Access Method |
|-----------|----------|---------------|
| AI Employee app | Local | Python process |
| Claude CLI | Local | Subprocess |
| MCP servers | Local processes | stdin/stdout JSON-RPC |
| Obsidian vault | Local filesystem | Direct file I/O |
| Odoo 19 | Azure Container Instances | XML-RPC over HTTPS |
| PostgreSQL | Neon DB (serverless) | Used by Odoo internally |
| Gmail, LinkedIn, Meta, Twitter | Cloud APIs | REST over HTTPS |

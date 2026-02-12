# AI Employee — Platinum Demo Script

This document walks through the end-to-end Platinum tier demo for hackathon judges.

## Pre-Demo Checklist

- [ ] Azure VM running (`systemctl status ai-employee-cloud`)
- [ ] Local scheduler running (`uv run python main.py --scheduler --zone local`)
- [ ] Vault git sync working (both zones push/pull)
- [ ] WhatsApp webhook running (`uv run python -m utils.whatsapp_webhook`)
- [ ] ngrok tunnel active (`ngrok http 5001`)
- [ ] Health endpoint accessible (`curl http://<VM_IP>:8080/health`)

## Demo Flow

### 1. Show Architecture (2 min)

Open `docs/ARCHITECTURE.md` or draw the diagram:

```
┌─── Cloud Zone (Azure VM) ──────────────────────────┐
│  scheduler.py → orchestrator.py → Claude CLI        │
│  Gmail poll, social drafts, briefings, audit        │
│  Health endpoint: GET /health → :8080               │
└──────────────┬──────────────────────────────────────┘
               │ Git sync (every 60s)
               │ AI_Employee_Vault/ ↔ GitHub
┌──────────────┴──────────────────────────────────────┐
│  Local Zone (your laptop)                            │
│  Approved action execution, WhatsApp notify          │
│  WhatsApp webhook: POST /webhook → :5001             │
└─────────────────────────────────────────────────────┘
               │ WhatsApp Business API
               ▼
         📱 Human's Phone
```

### 2. Email → Cloud Triage (3 min)

1. Send a test email to the configured Gmail account
2. Show the cloud VM logs: `sudo journalctl -u ai-employee-cloud -f`
3. Within 2 minutes, Gmail watcher picks it up
4. `EMAIL_*.md` appears in `Needs_Action/`
5. Orchestrator processes it → creates reply draft in `Pending_Approval/`
6. Vault sync pushes to GitHub

### 3. Git Sync (1 min)

1. Show the GitHub repo for the vault
2. Point out commit messages: `[cloud] auto-sync 2026-02-12T...`
3. Local zone pulls the new `Pending_Approval/` file automatically

### 4. WhatsApp Approval (3 min)

1. Local zone detects the new pending file
2. WhatsApp notification fires to your phone:
   ```
   AI Employee needs approval:
   File: EMAIL_REPLY_abc123.md
   Action: email_send
   Reply: APPROVE EMAIL_REPLY_abc123.md
   ```
3. Reply `APPROVE EMAIL_REPLY_abc123.md` on WhatsApp
4. Webhook moves file to `Approved/`
5. Local orchestrator executes the email send via MCP

### 5. Completion → Sync Back (1 min)

1. File moves to `Done/` with timestamp
2. Vault sync pushes completion to GitHub
3. Cloud zone pulls → sees the `Done/` entry
4. Dashboard updated with new counts

### 6. Health Endpoint (1 min)

```bash
curl http://<VM_IP>:8080/health | python -m json.tool
```

Show JSON response with zone, vault status, service health.

### 7. Automated Demo Gate (1 min)

```bash
bash scripts/demo_gate.sh
```

Shows all checks passing: vault structure, file processing, logging, health, git.

### 8. Social Media Pipeline (2 min)

Show a LinkedIn/Facebook/Twitter/Instagram draft cycle:
1. Scheduled draft generation (cloud zone)
2. Draft in `Pending_Approval/` synced to local
3. WhatsApp notification
4. Approve via WhatsApp → auto-publishes

### 9. Odoo Accounting (1 min)

Show Odoo dashboard via HTTPS:
```bash
curl -I https://ai-employee-odoo.eastus.azurecontainer.io/web/login
```

Show invoice creation and the $100 payment approval threshold.

## Key Talking Points

1. **Zero-trust execution**: Cloud zone NEVER executes approved actions — only local zone does
2. **Git as message bus**: No custom APIs needed, standard Git push/pull syncs the vault
3. **WhatsApp HITL**: Mobile-first approval without opening a laptop
4. **24/7 operation**: systemd + auto-restart keeps the cloud zone always running
5. **Audit trail**: Every action logged to `Logs/YYYY-MM-DD.json` with zone attribution
6. **DRY_RUN safety**: Flip one env var to go from testing to production

# AI Employee — Complete Demo Guide

> **Hackathon Demo** | All Tiers: Bronze → Silver → Gold → Platinum

This document contains every command needed to demonstrate the AI Employee system. Each tier builds on the previous one.

---

## Quick Reference

| Resource | URL / Command |
|----------|--------------|
| **GitHub Repo** | https://github.com/aimanhanif321/hacthon-0 |
| **Azure VM IP** | `20.64.238.101` |
| **Health Endpoint** | http://20.64.238.101:8080/health |
| **WhatsApp Webhook** | https://fairy-flimsies-nonegregiously.ngrok-free.dev/webhook |
| **Odoo** | http://ai-employee-odoo.eastus.azurecontainer.io:8069 |
| **SSH to VM** | `ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101` |

---

## Pre-Demo Setup (Run Once Before Demo)

```bash
# 1. Start Azure VM (if deallocated)
az vm start --resource-group ai-employee-rg --name ai-employee-vm

# 2. Verify VM is running
az vm show -g ai-employee-rg -n ai-employee-vm -d --query powerState -o tsv
# Expected: VM running

# 3. Check cloud zone health
curl -s http://20.64.238.101:8080/health | python -m json.tool

# 4. Start local zone on your laptop
uv run python main.py --scheduler --zone local

# 5. Verify ngrok tunnel is active (on VM)
ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101 "curl -s http://localhost:4040/api/tunnels | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"tunnels\"][0][\"public_url\"])'"
```

---

## Bronze Tier Demo

> Obsidian vault, filesystem watcher, Claude Code integration, agent skills

### Commands

```bash
# Show vault structure (10 folders)
ls AI_Employee_Vault/

# Show Company Handbook (AI rules)
cat AI_Employee_Vault/Company_Handbook.md

# Show Dashboard (live status)
cat AI_Employee_Vault/Dashboard.md

# Start file watcher only
uv run python main.py
```

### Live Demo: File Drop Triage

```bash
# Drop a test file into Inbox
echo "Q4 2026 Financial Report - Revenue up 15%" > AI_Employee_Vault/Inbox/quarterly_report.txt

# Watch the watcher triage it (wait 2-3 seconds)
ls AI_Employee_Vault/Needs_Action/
# Expected: FILE_quarterly_report_<timestamp>.md appears

# Read the auto-generated action file
cat AI_Employee_Vault/Needs_Action/FILE_quarterly_report_*.md
# Shows: frontmatter with type, priority, status + suggested actions
```

### What to Show Judges

1. **Obsidian Vault** — Open vault in Obsidian, show folder structure
2. **Dashboard.md** — Auto-updated live status with counts per folder
3. **Company_Handbook.md** — Rules the AI follows (priority levels, $100 threshold)
4. **File Watcher** — Drop file → auto-triage → action file created

---

## Silver Tier Demo

> Gmail watcher, LinkedIn posting, Plans, MCP email server, human approval, scheduling

### Commands

```bash
# Run full scheduler (does everything)
uv run python main.py --scheduler

# Process pending tasks once and exit
uv run python main.py --once

# Run orchestrator only (no watchers)
uv run python main.py --orchestrator
```

### Live Demo: Email Processing

```bash
# Send a test email to your Gmail account, then wait ~2 minutes
# Gmail watcher polls every 2 minutes

# Check if email was picked up
ls AI_Employee_Vault/Needs_Action/EMAIL_*

# Read the email action file
cat AI_Employee_Vault/Needs_Action/EMAIL_*.md
# Shows: sender, subject, body, priority, suggested actions

# After orchestrator processes it, check Done/
ls AI_Employee_Vault/Done/
```

### Live Demo: LinkedIn Draft + Approval

```bash
# Manually trigger a LinkedIn draft (normally scheduled Monday 10 AM)
# The orchestrator + Claude generates a draft from Business_Goals.md

# Check pending approvals
ls AI_Employee_Vault/Pending_Approval/

# Read the LinkedIn draft
cat AI_Employee_Vault/Pending_Approval/LINKEDIN_POST_*.md
# Shows: frontmatter with action: linkedin_post + Post Content

# APPROVE: Move file to Approved/
mv AI_Employee_Vault/Pending_Approval/LINKEDIN_POST_*.md AI_Employee_Vault/Approved/

# Orchestrator auto-executes within 30 seconds
# Check Done/ for completed post
ls AI_Employee_Vault/Done/
```

### Live Demo: Daily Briefing

```bash
# Check generated briefings
ls AI_Employee_Vault/Briefings/

# Read today's briefing
cat AI_Employee_Vault/Briefings/*_Daily.md
# Shows: tasks completed, pending items, recommendations
```

### What to Show Judges

1. **Two Watchers** — Filesystem (real-time) + Gmail (polling 2 min)
2. **Email MCP Server** — Claude can send/draft emails via MCP tools
3. **Approval Workflow** — Draft → Pending_Approval → Human moves to Approved → Auto-executes
4. **Claude Reasoning** — Plans generated for complex tasks in Plans/
5. **Scheduling** — Gmail every 2min, tasks every 30s, briefing at 8 AM, LinkedIn Monday 10 AM

---

## Gold Tier Demo

> Odoo accounting, 4 social platforms, weekly audit, error recovery, Ralph Wiggum loop

### Commands

```bash
# Check Odoo connection
curl -s http://ai-employee-odoo.eastus.azurecontainer.io:8069/web/login | head -5

# Start/Stop Odoo (save Azure credits)
az container start --resource-group ai-employee-rg --name odoo-server
az container stop --resource-group ai-employee-rg --name odoo-server

# Check audit logs
cat AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json | python -m json.tool
```

### Live Demo: Invoice Creation (Odoo)

```bash
# Create an invoice task file
cat > AI_Employee_Vault/Needs_Action/ODOO_invoice_demo.md << 'EOF'
---
type: odoo_task
priority: high
status: pending
action: create_invoice
---
# Create Invoice

Customer: Ali Khan
Items:
- 5x Widget at $50 each
- 2x Premium Service at $150 each
EOF

# Orchestrator processes it → calls Odoo MCP → invoice created
# Check Odoo web UI at http://ai-employee-odoo.eastus.azurecontainer.io:8069
# Login: admin / admin
```

### Live Demo: Facebook Post

```bash
# Check if there's a Facebook draft in Pending_Approval
ls AI_Employee_Vault/Pending_Approval/FB_POST_*

# Approve it
mv AI_Employee_Vault/Pending_Approval/FB_POST_*.md AI_Employee_Vault/Approved/

# Orchestrator publishes to Facebook via Meta Graph API
# Check logs for post ID
cat AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json | python -m json.tool | grep facebook
```

### Live Demo: All 4 Social Platforms

```bash
# LinkedIn draft  — Monday 10:00 AM  (Silver)
# Facebook draft  — Tuesday 10:30 AM (Gold)
# Twitter draft   — Wednesday 10:30 AM (Gold)
# Instagram draft — Thursday 10:30 AM (Gold)

# All follow same flow:
# 1. Scheduler triggers draft generation
# 2. Claude reads Business_Goals.md, generates platform-specific content
# 3. Draft saved to Pending_Approval/ with action: <platform>_post
# 4. Human reviews + moves to Approved/
# 5. Orchestrator calls skill module → API publishes

# Check all pending social posts
ls AI_Employee_Vault/Pending_Approval/ | grep -E "LINKEDIN|FB|TWEET|IG"
```

### Live Demo: Weekly Audit + CEO Briefing

```bash
# Check weekly briefings (auto-generated Sunday 8 PM)
ls AI_Employee_Vault/Briefings/*Weekly*
ls AI_Employee_Vault/Briefings/*CEO*

# Read CEO briefing
cat AI_Employee_Vault/Briefings/*CEO_Briefing.md
# Shows: KPI dashboard, social media breakdown, achievements, action items
```

### Live Demo: Error Recovery

```bash
# Check service health
uv run python -c "from utils.retry import health; print(health.summary())"

# Ralph Wiggum loop — complex tasks keep Claude working
cat .task_state.json 2>/dev/null || echo "No active multi-step task"
```

### What to Show Judges

1. **Odoo on Azure** — Live accounting with invoices, balances, P&L
2. **4 Social Platforms** — LinkedIn + Facebook + Instagram + Twitter all integrated
3. **$100 Payment Threshold** — Payments >$100 require human approval
4. **CEO Briefing** — Auto-generated weekly KPI dashboard
5. **Error Recovery** — Exponential backoff, graceful degradation, health checker
6. **Ralph Wiggum** — Stop hook keeps Claude working on multi-step tasks

---

## Platinum Tier Demo

> Cloud/Local zones, Azure VM, vault Git sync, WhatsApp approvals, health endpoint

### Commands

```bash
# === CLOUD ZONE (Azure VM) ===

# SSH into VM
ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101

# Check cloud service status
sudo systemctl status ai-employee-cloud

# View cloud zone logs (live)
sudo journalctl -u ai-employee-cloud -f

# Restart cloud zone
sudo systemctl restart ai-employee-cloud

# Check health from anywhere
curl -s http://20.64.238.101:8080/health | python -m json.tool

# === LOCAL ZONE (Your Laptop) ===

# Start local zone
uv run python main.py --scheduler --zone local

# === VM ON/OFF (Save Credits) ===

# STOP VM (no charges when deallocated)
az vm deallocate --resource-group ai-employee-rg --name ai-employee-vm

# START VM (before demo)
az vm start --resource-group ai-employee-rg --name ai-employee-vm

# Check VM power state
az vm show -g ai-employee-rg -n ai-employee-vm -d --query powerState -o tsv
```

### Live Demo: Health Endpoint

```bash
# Open in browser or curl
curl -s http://20.64.238.101:8080/health | python -m json.tool

# Expected response:
# {
#   "status": "ok",
#   "zone": "cloud",
#   "timestamp": "2026-02-12T...",
#   "vault_ok": true,
#   "services": {}
# }
```

### Live Demo: WhatsApp Approval Flow

```bash
# 1. Create a test approval file on the VM
ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101 "cat > ~/ai_employee/AI_Employee_Vault/Pending_Approval/TEST_APPROVAL.md << 'EOF'
---
action: email_send
status: pending_approval
to: client@example.com
subject: Project Update
---
# Email: Project Update
Dear Client, here is your weekly project update...
EOF"

# 2. Trigger WhatsApp notification
ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101 "cd ~/ai_employee && source ~/.local/bin/env && uv run python -c \"
from pathlib import Path
from skills.whatsapp_notifier import send_approval_request
vault = Path('AI_Employee_Vault')
f = vault / 'Pending_Approval' / 'TEST_APPROVAL.md'
print(send_approval_request(f, vault))
\""

# 3. Check your WhatsApp — you'll receive:
#    "AI Employee needs approval:
#     File: TEST_APPROVAL.md
#     Action: email_send
#     Reply: APPROVE TEST_APPROVAL.md"

# 4. Reply on WhatsApp: APPROVE TEST_APPROVAL.md

# 5. Webhook processes reply → file moves to Approved/
# 6. Local zone orchestrator executes the action
```

### Live Demo: Zone System

```bash
# Show cloud zone is processing triage/drafts
ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101 "sudo journalctl -u ai-employee-cloud --no-pager -n 20"
# Look for: "Processing: EMAIL_*", "Dashboard updated", "[Zone:cloud] Skipping approved actions"

# Show local zone handles executions
# In local terminal: look for "process_approved_actions" entries

# Key point: Cloud NEVER executes approved actions (zero-trust)
```

### Live Demo: Vault Git Sync

```bash
# Show git log with zone-attributed commits
cd AI_Employee_Vault && git log --oneline -10
# Shows: [cloud] auto-sync ..., [local] auto-sync ...

# Show sync happening in real-time
ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101 "cd ~/ai_employee/AI_Employee_Vault && git log --oneline -5"
```

### Live Demo: Demo Gate (Automated Verification)

```bash
# Run the automated end-to-end test
bash scripts/demo_gate.sh

# Checks: vault structure, file processing, logging, health endpoint, git status
# Reports: PASS/FAIL for each check
```

### What to Show Judges

1. **Two Zones Running** — Cloud VM (24/7) + Local laptop simultaneously
2. **Health Endpoint** — http://20.64.238.101:8080/health returns live JSON
3. **WhatsApp on Phone** — Show the approval message and reply flow
4. **Git Sync** — Commits from both zones visible in git log
5. **Zero-Trust Execution** — Cloud creates drafts, only local executes
6. **Auto-Restart** — Kill the process on VM, it comes back in 10 seconds

---

## All Run Modes (Quick Reference)

```bash
# === Basic Modes ===
uv run python main.py                          # File watcher only
uv run python main.py --orchestrator           # Orchestrator only
uv run python main.py --once                   # Process once and exit
uv run python main.py --scheduler              # Full scheduler (all jobs)

# === Zone Modes (Platinum) ===
uv run python main.py --scheduler --zone cloud # Cloud zone (triage, drafts, briefings)
uv run python main.py --scheduler --zone local # Local zone (approvals, WhatsApp, execution)

# === Azure VM Management ===
az vm start --resource-group ai-employee-rg --name ai-employee-vm      # Start VM
az vm deallocate --resource-group ai-employee-rg --name ai-employee-vm # Stop VM (free)
az vm show -g ai-employee-rg -n ai-employee-vm -d --query powerState -o tsv  # Check status
ssh -i ~/.ssh/id_rsa aiemployee@20.64.238.101                         # SSH into VM

# === Cloud Zone Service (on VM via SSH) ===
sudo systemctl start ai-employee-cloud          # Start service
sudo systemctl stop ai-employee-cloud           # Stop service
sudo systemctl restart ai-employee-cloud        # Restart
sudo systemctl status ai-employee-cloud         # Check status
sudo journalctl -u ai-employee-cloud -f         # Live logs

# === Azure Container (Odoo) ===
az container start --resource-group ai-employee-rg --name odoo-server  # Start Odoo
az container stop --resource-group ai-employee-rg --name odoo-server   # Stop Odoo

# === Health Checks ===
curl -s http://20.64.238.101:8080/health | python -m json.tool        # Cloud health
curl -s http://localhost:8080/health | python -m json.tool             # Local health

# === WhatsApp (on VM) ===
sudo systemctl status ai-employee-webhook       # Webhook status
sudo journalctl -u ai-employee-webhook -f       # Webhook logs
```

---

## Tier Summary Table

| Feature | Bronze | Silver | Gold | Platinum |
|---------|--------|--------|------|----------|
| Obsidian Vault (10 folders) | ✅ | ✅ | ✅ | ✅ |
| Filesystem Watcher | ✅ | ✅ | ✅ | ✅ |
| Claude Code Integration | ✅ | ✅ | ✅ | ✅ |
| Agent Skills (CLAUDE.md) | ✅ | ✅ | ✅ | ✅ |
| Gmail Watcher | | ✅ | ✅ | ✅ |
| LinkedIn Posting | | ✅ | ✅ | ✅ |
| Email MCP Server | | ✅ | ✅ | ✅ |
| Human-in-the-Loop Approval | | ✅ | ✅ | ✅ |
| Task Plans (Claude reasoning) | | ✅ | ✅ | ✅ |
| Scheduling | | ✅ | ✅ | ✅ |
| Daily Briefings | | ✅ | ✅ | ✅ |
| Odoo Accounting (Azure) | | | ✅ | ✅ |
| Facebook + Instagram | | | ✅ | ✅ |
| Twitter/X | | | ✅ | ✅ |
| Social Media MCP Server | | | ✅ | ✅ |
| Weekly Audit + CEO Briefing | | | ✅ | ✅ |
| Error Recovery + Health | | | ✅ | ✅ |
| Ralph Wiggum Loop | | | ✅ | ✅ |
| Cloud/Local Zone System | | | | ✅ |
| Azure VM (24/7) | | | | ✅ |
| Vault Git Sync | | | | ✅ |
| WhatsApp Approvals | | | | ✅ |
| HTTP Health Endpoint | | | | ✅ |
| Odoo HTTPS + Backups | | | | ✅ |
| Demo Gate (auto-verify) | | | | ✅ |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| VM not starting | `az vm start -g ai-employee-rg -n ai-employee-vm` |
| Cloud service crashed | `ssh ... "sudo systemctl restart ai-employee-cloud"` |
| Health endpoint not responding | Check port 8080 is open: `az vm open-port -g ai-employee-rg -n ai-employee-vm --port 8080 --priority 1010` |
| WhatsApp not sending | Token expires every 24h — regenerate on Meta dashboard |
| Gmail not polling | Check `credentials.json` and `token.json` exist |
| Odoo not reachable | `az container start -g ai-employee-rg -n odoo-server` |
| ngrok tunnel expired | SSH into VM, restart: `pkill ngrok && nohup ngrok http 5001 &` |
| Vault sync failing | Check git remote configured in `AI_Employee_Vault/` |
| DRY_RUN blocking actions | Set `DRY_RUN=false` in `.env` |

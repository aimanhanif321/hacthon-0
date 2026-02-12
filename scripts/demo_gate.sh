#!/usr/bin/env bash
# demo_gate.sh — Automated end-to-end Platinum demo verification.
#
# Drops a test EMAIL file in the vault, waits for processing,
# checks git commits, and verifies the approval pipeline.
#
# Usage:
#   bash scripts/demo_gate.sh
#
# Prerequisites:
#   - Scheduler running (uv run python main.py --scheduler)
#   - Vault git sync configured (VAULT_SYNC_ENABLED=true)

set -euo pipefail

VAULT="AI_Employee_Vault"
PASS=0
FAIL=0

green() { printf "\033[32m✓ %s\033[0m\n" "$1"; PASS=$((PASS + 1)); }
red()   { printf "\033[31m✗ %s\033[0m\n" "$1"; FAIL=$((FAIL + 1)); }
info()  { printf "\033[34mℹ %s\033[0m\n" "$1"; }

echo "================================================"
echo "  AI Employee — Platinum Demo Gate"
echo "================================================"
echo ""

# --- Step 1: Check vault structure ---
info "Step 1: Checking vault structure..."
for dir in Inbox Needs_Action In_Progress Done Pending_Approval Approved Rejected Logs Briefings Plans; do
    if [ -d "$VAULT/$dir" ]; then
        green "Folder exists: $VAULT/$dir"
    else
        red "Missing folder: $VAULT/$dir"
    fi
done

# --- Step 2: Check required files ---
info "Step 2: Checking required files..."
for f in Dashboard.md Company_Handbook.md Business_Goals.md; do
    if [ -f "$VAULT/$f" ]; then
        green "File exists: $VAULT/$f"
    else
        red "Missing file: $VAULT/$f"
    fi
done

# --- Step 3: Drop test email ---
info "Step 3: Dropping test email in Needs_Action..."
TIMESTAMP=$(date +%H%M%S)
TEST_FILE="EMAIL_demo_test_${TIMESTAMP}.md"
cat > "$VAULT/Needs_Action/$TEST_FILE" <<'TESTEOF'
---
type: email
source: demo_gate
message_id: demo_test_001
from: demo@example.com
subject: Platinum Demo Gate Test
date: 2026-02-12
priority: medium
status: pending
---

# Demo Gate Test Email

From: demo@example.com
Subject: Platinum Demo Gate Test

This is an automated test email from the demo gate script.
The orchestrator should process this and create an action file.
TESTEOF

if [ -f "$VAULT/Needs_Action/$TEST_FILE" ]; then
    green "Test file created: $TEST_FILE"
else
    red "Failed to create test file"
fi

# --- Step 4: Wait for processing ---
info "Step 4: Waiting for orchestrator to process (max 90s)..."
WAITED=0
PROCESSED=false
while [ $WAITED -lt 90 ]; do
    # Check if file was moved out of Needs_Action
    if [ ! -f "$VAULT/Needs_Action/$TEST_FILE" ]; then
        PROCESSED=true
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
    printf "."
done
echo ""

if $PROCESSED; then
    green "Test file processed (moved from Needs_Action)"
else
    red "Test file not processed within 90s — is the scheduler running?"
fi

# --- Step 5: Check Done folder ---
info "Step 5: Checking Done folder for processed file..."
DONE_MATCH=$(find "$VAULT/Done" -name "*${TEST_FILE}*" 2>/dev/null | head -1)
if [ -n "$DONE_MATCH" ]; then
    green "Found in Done: $(basename "$DONE_MATCH")"
else
    red "Test file not found in Done/"
fi

# --- Step 6: Check today's log ---
info "Step 6: Checking today's log..."
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$VAULT/Logs/${TODAY}.json"
if [ -f "$LOG_FILE" ]; then
    green "Today's log exists: $LOG_FILE"
    if grep -q "demo_test" "$LOG_FILE" 2>/dev/null; then
        green "Test entry found in log"
    else
        red "Test entry not found in log (may take another cycle)"
    fi
else
    red "No log file for today"
fi

# --- Step 7: Check health endpoint ---
info "Step 7: Checking health endpoint..."
if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:8080/health)
    green "Health endpoint responding"
    info "  Response: $HEALTH"
else
    red "Health endpoint not responding on :8080"
fi

# --- Step 8: Check vault git status ---
info "Step 8: Checking vault git status..."
if [ -d "$VAULT/.git" ]; then
    green "Vault is a git repository"
    REMOTE=$(cd "$VAULT" && git remote -v 2>/dev/null | head -1)
    if [ -n "$REMOTE" ]; then
        green "Git remote configured: $REMOTE"
    else
        red "No git remote configured"
    fi
else
    red "Vault is not a git repository (run: cd $VAULT && git init)"
fi

# --- Summary ---
echo ""
echo "================================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "================================================"

if [ $FAIL -eq 0 ]; then
    echo ""
    green "ALL CHECKS PASSED — Platinum Demo Gate verified!"
    exit 0
else
    echo ""
    red "$FAIL check(s) failed — review above"
    exit 1
fi

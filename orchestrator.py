"""
Orchestrator - The master coordinator for the AI Employee.

This script:
1. Monitors /Needs_Action for pending tasks
2. Triggers Claude Code to process each task
3. Creates Plans for complex multi-step tasks
4. Watches /Approved folder for human-approved actions
5. Processes /Rejected folder for denied actions
6. Logs all activity to /Logs
7. Updates Dashboard.md with current status

Usage:
    python orchestrator.py                          # Run once (process pending tasks)
    python orchestrator.py --watch                  # Run continuously
    python orchestrator.py --watch --interval 30    # Custom check interval (seconds)
"""

import os
import re
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("Orchestrator")

VAULT_PATH = Path(__file__).parent / "AI_Employee_Vault"

# Frontmatter keys that signal a task needs planning instead of direct execution
COMPLEX_TASK_INDICATORS = {"multi_step", "complex", "project"}


def parse_frontmatter(content: str) -> dict:
    """Parse YAML-style frontmatter from a markdown file."""
    fm = {}
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return fm
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def needs_planning(task_content: str) -> bool:
    """Determine if a task requires a plan rather than direct execution."""
    fm = parse_frontmatter(task_content)

    # Explicit flag in frontmatter
    if fm.get("type") in COMPLEX_TASK_INDICATORS:
        return True
    if fm.get("needs_plan", "").lower() == "true":
        return True

    # Heuristic: tasks with many checklist items or "multi-step" in body
    checklist_count = task_content.count("- [ ]")
    if checklist_count >= 5:
        return True
    if "multi-step" in task_content.lower() or "complex task" in task_content.lower():
        return True

    return False


def get_pending_tasks(vault: Path) -> list[Path]:
    """Get all pending .md action files from /Needs_Action."""
    needs_action = vault / "Needs_Action"
    if not needs_action.exists():
        return []
    tasks = sorted(needs_action.glob("*.md"), key=lambda p: p.stat().st_mtime)
    return [t for t in tasks if t.stem.startswith((
        "FILE_", "EMAIL_", "TASK_", "LINKEDIN_",
        "FB_", "IG_", "TWEET_", "ODOO_",
    ))]


def get_approved_actions(vault: Path) -> list[Path]:
    """Get all approved action files from /Approved."""
    approved = vault / "Approved"
    if not approved.exists():
        return []
    return list(approved.glob("*.md"))


def get_rejected_actions(vault: Path) -> list[Path]:
    """Get all rejected action files from /Rejected."""
    rejected = vault / "Rejected"
    if not rejected.exists():
        return []
    return list(rejected.glob("*.md"))


def move_to_done(file_path: Path, vault: Path):
    """Move a completed task file to /Done with timestamp."""
    done_dir = vault / "Done"
    done_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = done_dir / f"{timestamp}_{file_path.name}"
    shutil.move(str(file_path), str(dest))
    logger.info(f"Moved to Done: {dest.name}")
    return dest


def move_to_in_progress(file_path: Path, vault: Path):
    """Move a task to /In_Progress to claim it."""
    in_progress = vault / "In_Progress"
    in_progress.mkdir(exist_ok=True)
    dest = in_progress / file_path.name
    shutil.move(str(file_path), str(dest))
    logger.info(f"Claimed task: {file_path.name}")
    return dest


def log_action(vault: Path, action: dict):
    """Append an action entry to today's log file."""
    logs_dir = vault / "Logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []

    action["timestamp"] = datetime.now(timezone.utc).isoformat()
    entries.append(action)
    log_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def invoke_claude(prompt: str, vault: Path, max_retries: int = 2) -> str:
    """
    Invoke Claude Code CLI to process a task.
    Claude Code reads from the vault and writes results back.
    Retries up to *max_retries* times on timeout.
    """
    logger.info("Invoking Claude Code...")

    # On Windows, use claude.cmd; on Unix, use claude
    claude_cmd = "claude.cmd" if os.name == "nt" else "claude"

    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                [
                    claude_cmd,
                    "-p", prompt,
                    "--output-format", "text",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(vault),
                shell=(os.name == "nt"),
            )

            if result.returncode == 0:
                logger.info("Claude Code completed successfully")
                return result.stdout.strip()
            else:
                logger.error(f"Claude Code error: {result.stderr}")
                return f"ERROR: {result.stderr}"

        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                logger.warning(f"Claude Code timed out (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                continue
            logger.error("Claude Code timed out after all retries")
            return "ERROR: Claude Code timed out after 120 seconds"
        except FileNotFoundError:
            logger.error("Claude Code CLI not found. Is it installed?")
            return "ERROR: Claude Code CLI not found"

    return "ERROR: invoke_claude exhausted all retries"


def create_plan(task_path: Path, task_content: str, vault: Path) -> Path:
    """
    Create a Plan.md file for a complex task.

    Uses Claude to generate a structured plan with objectives,
    step-by-step checklist, required approvals, and estimated actions.
    """
    plans_dir = vault / "Plans"
    plans_dir.mkdir(exist_ok=True)

    task_name = task_path.stem
    plan_filename = f"PLAN_{task_name}.md"
    plan_path = plans_dir / plan_filename

    handbook = (vault / "Company_Handbook.md").read_text(encoding="utf-8")

    prompt = f"""You are an AI Employee creating a detailed plan for a complex task.

## Company Rules
{handbook}

## Task to Plan
{task_content}

## Instructions
Create a structured plan in markdown format with these sections:
1. **Objective**: One sentence describing the goal
2. **Steps**: Numbered checklist of concrete actions (use - [ ] format)
3. **Required Approvals**: List any steps that need human approval
4. **Estimated Actions**: How many automated actions this plan involves
5. **Priority**: Based on the task priority
6. **Dependencies**: Any prerequisites or blockers

Write ONLY the plan content (no extra commentary). Start with a YAML frontmatter block containing type: plan, status: active, and the task source filename."""

    response = invoke_claude(prompt, vault)

    if "ERROR" in response:
        # Fallback: create a basic plan template
        now = datetime.now(timezone.utc).isoformat()
        fm = parse_frontmatter(task_content)
        response = f"""---
type: plan
status: active
source_task: {task_path.name}
priority: {fm.get('priority', 'medium')}
created: {now}
---

# Plan: {task_name}

## Objective
Process task: {task_name}

## Steps
- [ ] Review task content and requirements
- [ ] Determine necessary actions
- [ ] Execute actions (with approvals if needed)
- [ ] Verify completion
- [ ] Log results

## Required Approvals
- Review task details to determine if approvals are needed

## Estimated Actions
- 3-5 automated actions

## Notes
_Auto-generated plan template. Claude was unable to generate a detailed plan._
"""

    plan_path.write_text(response, encoding="utf-8")
    logger.info(f"Created plan: {plan_filename}")

    log_action(vault, {
        "action_type": "plan_created",
        "task_file": task_path.name,
        "plan_file": plan_filename,
        "actor": "orchestrator",
    })

    return plan_path


def process_task(task_path: Path, vault: Path):
    """Process a single task file using Claude Code."""
    logger.info(f"Processing: {task_path.name}")

    # Read the task content
    task_content = task_path.read_text(encoding="utf-8")

    # Check if this task needs a plan
    if needs_planning(task_content):
        logger.info(f"Complex task detected - creating plan for: {task_path.name}")
        plan_path = create_plan(task_path, task_content, vault)

        # Initialize Ralph Wiggum task state from plan steps
        try:
            from skills.task_state import start_multi_step_task
            plan_text = plan_path.read_text(encoding="utf-8")
            # Extract checklist items as steps
            steps = []
            for line in plan_text.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- [ ]"):
                    step_desc = stripped[5:].strip()
                    step_id = step_desc[:40].lower().replace(" ", "_")
                    steps.append({"id": step_id, "description": step_desc})
            if steps:
                start_multi_step_task(vault, task_path.stem, steps)
                logger.info(f"Ralph Wiggum loop initialized with {len(steps)} steps")
        except Exception as e:
            logger.warning(f"Could not initialize Ralph Wiggum state: {e}")

    # Move to in-progress
    in_progress_path = move_to_in_progress(task_path, vault)

    # Build the prompt for Claude
    handbook = (vault / "Company_Handbook.md").read_text(encoding="utf-8")

    prompt = f"""You are an AI Employee processing a task from the vault.

## Company Rules
{handbook}

## Task to Process
{task_content}

## Instructions
1. Read and understand the task
2. Determine what actions are needed
3. If the task requires human approval (payments, sensitive actions), create a file in Pending_Approval/
4. Otherwise, process the task and provide a summary
5. Be concise in your response

Respond with a brief summary of what you did or what needs to happen next."""

    # Invoke Claude
    response = invoke_claude(prompt, vault)

    # Log the action
    log_action(vault, {
        "action_type": "task_processed",
        "task_file": task_path.name,
        "actor": "claude_code",
        "result": "success" if "ERROR" not in response else "error",
        "summary": response[:500],
    })

    # Move to done
    move_to_done(in_progress_path, vault)

    # Also move any associated non-.md files
    needs_action = vault / "Needs_Action"
    for associated in needs_action.iterdir():
        if not associated.name.endswith(".md") and not associated.name.startswith("."):
            move_to_done(associated, vault)

    return response


def process_approved_actions(vault: Path):
    """
    Process files in /Approved folder.

    Reads the frontmatter 'action' field to determine what to execute:
    - email_send: Send email via MCP server
    - linkedin_post: Publish to LinkedIn
    - general: Process via Claude
    """
    approved_files = get_approved_actions(vault)
    if not approved_files:
        return

    logger.info(f"Found {len(approved_files)} approved action(s)")

    for approved_file in approved_files:
        content = approved_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        action_type = fm.get("action", "general")

        logger.info(f"Executing approved action: {approved_file.name} (type: {action_type})")

        result = {"success": False, "error": "Unknown action type"}

        if action_type == "linkedin_post":
            try:
                from skills.linkedin_poster import execute_approved_post
                result = execute_approved_post(approved_file)
            except ImportError:
                result = {"success": False, "error": "LinkedIn poster module not available"}
            except Exception as e:
                result = {"success": False, "error": str(e)}

        elif action_type in ("facebook_post", "instagram_post"):
            try:
                from skills.meta_poster import execute_approved_post as meta_execute
                result = meta_execute(approved_file)
            except ImportError:
                result = {"success": False, "error": "Meta poster module not available"}
            except Exception as e:
                result = {"success": False, "error": str(e)}

        elif action_type == "twitter_post":
            try:
                from skills.twitter_poster import execute_approved_post as twitter_execute
                result = twitter_execute(approved_file)
            except ImportError:
                result = {"success": False, "error": "Twitter poster module not available"}
            except Exception as e:
                result = {"success": False, "error": str(e)}

        elif action_type == "odoo_invoice":
            prompt = f"""You are an AI Employee. Execute this approved Odoo invoice action:

{content}

Use the create_invoice MCP tool. If the tool is not available, report that the Odoo MCP server needs to be configured."""
            response = invoke_claude(prompt, vault)
            result = {"success": "ERROR" not in response, "response": response[:500]}

        elif action_type == "odoo_payment":
            prompt = f"""You are an AI Employee. Execute this approved Odoo payment:

{content}

Use the create_payment MCP tool. This payment was human-approved."""
            response = invoke_claude(prompt, vault)
            result = {"success": "ERROR" not in response, "response": response[:500]}

        elif action_type == "email_send":
            # Delegate to Claude Code which can use the MCP email server
            prompt = f"""You are an AI Employee. Execute this approved email action:

{content}

Use the send_email MCP tool to send this email. If the tool is not available, report that the email MCP server needs to be configured."""
            response = invoke_claude(prompt, vault)
            result = {"success": "ERROR" not in response, "response": response[:500]}

        else:
            # General approved action - process via Claude
            prompt = f"""You are an AI Employee. This action has been APPROVED by a human. Execute it:

{content}

Carry out the approved action and provide a brief summary."""
            response = invoke_claude(prompt, vault)
            result = {"success": "ERROR" not in response, "response": response[:500]}

        # Log the result
        log_action(vault, {
            "action_type": "approved_action_executed",
            "file": approved_file.name,
            "action": action_type,
            "actor": "orchestrator",
            "result": "success" if result.get("success") else "error",
            "details": str(result)[:500],
        })

        # Move to Done
        move_to_done(approved_file, vault)


def process_rejected_actions(vault: Path):
    """Log and archive rejected actions from /Rejected folder."""
    rejected_files = get_rejected_actions(vault)
    if not rejected_files:
        return

    for rejected_file in rejected_files:
        logger.info(f"Archiving rejected action: {rejected_file.name}")

        log_action(vault, {
            "action_type": "action_rejected",
            "file": rejected_file.name,
            "actor": "human",
            "result": "rejected",
        })

        move_to_done(rejected_file, vault)


def update_dashboard(vault: Path):
    """Update Dashboard.md with current status."""
    folders = {
        "Needs_Action": 0,
        "In_Progress": 0,
        "Pending_Approval": 0,
        "Approved": 0,
        "Rejected": 0,
        "Plans": 0,
    }
    for folder in folders:
        folder_path = vault / folder
        if folder_path.exists():
            folders[folder] = len(list(folder_path.glob("*.md")))

    done_today = len([
        f for f in (vault / "Done").glob("*.md")
        if f.name.startswith(datetime.now().strftime("%Y%m%d"))
    ])

    # Count social media drafts pending
    pending_dir = vault / "Pending_Approval"
    social_pending = 0
    if pending_dir.exists():
        for f in pending_dir.glob("*.md"):
            if f.stem.startswith(("FB_POST", "IG_POST", "TWEET", "LINKEDIN_POST")):
                social_pending += 1

    # Odoo connection status
    odoo_url = os.environ.get("ODOO_URL", "not configured")
    odoo_status = f"Configured ({odoo_url})" if odoo_url != "not configured" else "Not configured"

    now = datetime.now(timezone.utc).isoformat()

    dashboard = f"""---
last_updated: {now}
version: 0.3.0
---

# AI Employee Dashboard

## System Status
| Component | Status | Last Check |
|-----------|--------|------------|
| File Watcher | Check manually | {now} |
| Gmail Watcher | Check manually | {now} |
| Orchestrator | Active | {now} |
| Scheduler | Check manually | {now} |
| Odoo (Accounting) | {odoo_status} | {now} |

## Inbox Summary
- **Pending Actions**: {folders['Needs_Action']}
- **In Progress**: {folders['In_Progress']}
- **Completed Today**: {done_today}

## Approval Queue
- **Pending Approval**: {folders['Pending_Approval']}
- **Social Media Drafts Pending**: {social_pending}
- **Approved (ready)**: {folders['Approved']}
- **Active Plans**: {folders['Plans']}

## Quick Links
- [[Company_Handbook]] - Rules of engagement
- [[Business_Goals]] - Content strategy (LinkedIn, Facebook, Twitter, Instagram)
- [[Needs_Action/]] - Items requiring processing
- [[Pending_Approval/]] - Awaiting human approval
- [[Plans/]] - Active task plans
- [[Done/]] - Completed tasks
- [[Logs/]] - Audit trail
- [[Briefings/]] - Daily & weekly summaries

## Recent Activity
_Updated automatically by Orchestrator_
"""
    (vault / "Dashboard.md").write_text(dashboard, encoding="utf-8")
    logger.info("Dashboard updated")


def run_once(vault: Path):
    """Process all pending tasks, approved actions, and rejected items once."""
    # Process pending tasks
    tasks = get_pending_tasks(vault)
    if tasks:
        logger.info(f"Found {len(tasks)} pending task(s)")
        for task in tasks:
            process_task(task, vault)

    # Process approved actions
    process_approved_actions(vault)

    # Archive rejected actions
    process_rejected_actions(vault)

    if tasks or get_approved_actions(vault) or get_rejected_actions(vault):
        update_dashboard(vault)
    else:
        logger.info("No pending tasks or actions found")


def run_continuous(vault: Path, interval: int = 30):
    """Continuously watch for and process tasks."""
    logger.info(f"Running continuously (checking every {interval}s). Ctrl+C to stop.")

    try:
        while True:
            run_once(vault)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")


def main():
    parser = argparse.ArgumentParser(description="AI Employee Orchestrator")
    parser.add_argument(
        "--watch", action="store_true", help="Run continuously"
    )
    parser.add_argument(
        "--interval", type=int, default=30, help="Check interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--vault", type=str, default=str(VAULT_PATH), help="Path to Obsidian vault"
    )
    args = parser.parse_args()

    vault = Path(args.vault)
    if not vault.exists():
        logger.error(f"Vault not found: {vault}")
        sys.exit(1)

    logger.info(f"Vault: {vault}")

    if args.watch:
        run_continuous(vault, args.interval)
    else:
        run_once(vault)


if __name__ == "__main__":
    main()

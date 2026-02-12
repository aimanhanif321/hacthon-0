"""
Scheduler - Runs all AI Employee jobs on a schedule.

Combines the filesystem watcher, Gmail watcher, orchestrator,
and scheduled tasks into a single entry point.
Zone-aware: cloud and local zones run different subsets of jobs.

Jobs:
    - Every 2 min:  Poll Gmail for new emails (cloud)
    - Every 30 sec: Process /Needs_Action tasks (both)
    - Every 5 min:  Odoo health check (both)
    - Every 60 sec: Vault Git sync (both, if VAULT_SYNC_ENABLED)
    - Every 5 min:  WhatsApp notify pending approvals (local)
    - Daily 8:00 AM: Generate daily briefing (cloud)
    - Daily 10:00 AM: Generate LinkedIn post draft (cloud)
    - Sunday 8:00 PM: Weekly audit + CEO briefing (cloud)

Usage:
    uv run python scheduler.py
"""

import os
import sys
import json
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone

import schedule
import time

from orchestrator import (
    run_once, update_dashboard, invoke_claude, log_action,
    VAULT_PATH, ZONE,
)
from watchers.filesystem_watcher import run_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("Scheduler")


# ---------------------------------------------------------------------------
# Job definitions
# ---------------------------------------------------------------------------

def job_poll_gmail():
    """Poll Gmail for new unread emails."""
    logger.info("[Job] Polling Gmail...")
    try:
        from watchers.gmail_watcher import poll_gmail
        poll_gmail(VAULT_PATH)
    except Exception as e:
        logger.error(f"Gmail poll failed: {e}")


def job_process_tasks():
    """Process pending tasks in /Needs_Action."""
    logger.info("[Job] Processing pending tasks...")
    try:
        run_once(VAULT_PATH)
    except Exception as e:
        logger.error(f"Task processing failed: {e}")


def job_vault_sync():
    """Sync vault via Git (pull/commit/push)."""
    if os.getenv("VAULT_SYNC_ENABLED", "false").lower() != "true":
        return
    try:
        from utils.vault_sync import sync_vault
        result = sync_vault(VAULT_PATH)
        if result.get("error"):
            logger.warning(f"Vault sync error: {result['error']}")
    except Exception as e:
        logger.error(f"Vault sync job failed: {e}")


def job_notify_pending_approvals():
    """Send WhatsApp notifications for un-notified pending approvals (local only)."""
    if os.getenv("WHATSAPP_ENABLED", "false").lower() != "true":
        return
    try:
        pending_dir = VAULT_PATH / "Pending_Approval"
        if not pending_dir.exists():
            return

        from skills.whatsapp_notifier import send_approval_request

        for f in pending_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            if "<!-- whatsapp_notified: true -->" in content:
                continue
            logger.info(f"[WhatsApp] Notifying for: {f.name}")
            send_approval_request(f, VAULT_PATH)
            # Stamp the file so we don't re-notify
            with open(f, "a", encoding="utf-8") as fh:
                fh.write("\n<!-- whatsapp_notified: true -->\n")
    except Exception as e:
        logger.error(f"WhatsApp notify job failed: {e}")


def job_daily_briefing():
    """Generate a daily briefing report."""
    logger.info("[Job] Generating daily briefing...")
    try:
        briefings_dir = VAULT_PATH / "Briefings"
        briefings_dir.mkdir(exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        briefing_file = briefings_dir / f"{date_str}_Daily.md"

        if briefing_file.exists():
            logger.info("Daily briefing already exists for today")
            return

        # Gather data for the briefing
        done_today = list((VAULT_PATH / "Done").glob(f"{datetime.now().strftime('%Y%m%d')}*.md"))
        pending = list((VAULT_PATH / "Needs_Action").glob("*.md"))
        awaiting = list((VAULT_PATH / "Pending_Approval").glob("*.md"))

        # Read today's log for activity details
        log_file = VAULT_PATH / "Logs" / f"{date_str}.json"
        log_entries = []
        if log_file.exists():
            try:
                log_entries = json.loads(log_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        prompt = f"""You are an AI Employee generating a daily briefing report.

## Data for Today ({date_str})

### Completed Tasks ({len(done_today)})
{chr(10).join(f'- {f.name}' for f in done_today) or '- None'}

### Pending Items ({len(pending)})
{chr(10).join(f'- {f.name}' for f in pending) or '- None'}

### Awaiting Approval ({len(awaiting)})
{chr(10).join(f'- {f.name}' for f in awaiting) or '- None'}

### Activity Log ({len(log_entries)} entries)
{json.dumps(log_entries[-10:], indent=2) if log_entries else 'No activity logged yet.'}

## Instructions
Generate a concise daily briefing in markdown. Include:
1. Summary of completed work
2. Pending items that need attention
3. Items awaiting human approval
4. Recommendations for tomorrow

Start with YAML frontmatter: type: briefing, date: {date_str}
Keep it professional and actionable."""

        response = invoke_claude(prompt, VAULT_PATH)

        if "ERROR" in response:
            # Fallback template
            now = datetime.now(timezone.utc).isoformat()
            response = f"""---
type: briefing
date: {date_str}
generated: {now}
---

# Daily Briefing - {date_str}

## Completed Today
- {len(done_today)} task(s) completed

## Pending
- {len(pending)} item(s) in Needs_Action
- {len(awaiting)} item(s) awaiting approval

## Activity
- {len(log_entries)} actions logged today

## Recommendations
- Review pending items in Needs_Action/
- Check Pending_Approval/ for items needing your attention
"""

        briefing_file.write_text(response, encoding="utf-8")
        logger.info(f"Daily briefing saved: {briefing_file.name}")

        log_action(VAULT_PATH, {
            "action_type": "daily_briefing_generated",
            "file": briefing_file.name,
            "actor": "scheduler",
        })

    except Exception as e:
        logger.error(f"Daily briefing failed: {e}")


def job_linkedin_draft():
    """Generate a LinkedIn post draft for approval."""
    logger.info("[Job] Generating LinkedIn post draft...")
    try:
        from skills.linkedin_poster import create_post_draft
        draft_path = create_post_draft(VAULT_PATH)

        # Now use Claude to fill in the draft content
        goals_path = VAULT_PATH / "Business_Goals.md"
        goals = ""
        if goals_path.exists():
            goals = goals_path.read_text(encoding="utf-8")

        prompt = f"""You are an AI Employee creating a LinkedIn post.

## Business Goals
{goals}

## Instructions
Write a short, engaging LinkedIn post (under 1300 characters) based on the business goals above.
The post should:
- Be professional but approachable
- Include a concrete example or insight about AI automation
- End with a question or call-to-action
- NOT use hashtags excessively (max 3)

Output ONLY the post text, nothing else."""

        post_content = invoke_claude(prompt, VAULT_PATH)

        if "ERROR" not in post_content and draft_path.exists():
            # Update the draft with generated content
            draft_content = draft_path.read_text(encoding="utf-8")
            updated = draft_content.replace(
                "_Draft pending: Run the orchestrator or use /draft-linkedin-post to generate content._",
                post_content,
            )
            draft_path.write_text(updated, encoding="utf-8")
            logger.info("LinkedIn draft updated with generated content")

        log_action(VAULT_PATH, {
            "action_type": "linkedin_draft_generated",
            "file": draft_path.name,
            "actor": "scheduler",
        })

    except Exception as e:
        logger.error(f"LinkedIn draft generation failed: {e}")


def job_facebook_draft():
    """Generate a Facebook post draft for approval."""
    logger.info("[Job] Generating Facebook post draft...")
    try:
        from skills.meta_poster import create_post_draft
        draft_path = create_post_draft(VAULT_PATH, platform="facebook")
        _fill_social_draft(draft_path, "Facebook")
    except Exception as e:
        logger.error(f"Facebook draft generation failed: {e}")


def job_twitter_draft():
    """Generate a Twitter post draft for approval."""
    logger.info("[Job] Generating Twitter/X post draft...")
    try:
        from skills.twitter_poster import create_post_draft
        draft_path = create_post_draft(VAULT_PATH)
        _fill_social_draft(draft_path, "Twitter", max_chars=280)
    except Exception as e:
        logger.error(f"Twitter draft generation failed: {e}")


def job_instagram_draft():
    """Generate an Instagram post draft for approval."""
    logger.info("[Job] Generating Instagram post draft...")
    try:
        from skills.meta_poster import create_post_draft
        draft_path = create_post_draft(VAULT_PATH, platform="instagram")
        _fill_social_draft(draft_path, "Instagram")
    except Exception as e:
        logger.error(f"Instagram draft generation failed: {e}")


def job_weekly_audit():
    """Run the weekly audit and generate CEO briefing."""
    logger.info("[Job] Running weekly audit...")
    try:
        from skills.weekly_audit import run_weekly_audit
        run_weekly_audit(VAULT_PATH)
    except Exception as e:
        logger.error(f"Weekly audit failed: {e}")


def job_odoo_health_check():
    """Ping the Azure-hosted Odoo to verify connectivity."""
    try:
        from utils.retry import health
        import httpx
        odoo_url = os.getenv("ODOO_URL", "")
        if not odoo_url:
            return
        resp = httpx.get(f"{odoo_url}/web/login", timeout=10)
        if resp.status_code == 200:
            health.record_success("odoo")
        else:
            health.record_failure("odoo", f"HTTP {resp.status_code}")
    except Exception as e:
        from utils.retry import health
        health.record_failure("odoo", str(e))
        logger.warning(f"Odoo health check failed: {e}")
        # Write degraded flag to Logs/
        try:
            flag_path = VAULT_PATH / "Logs" / "odoo_degraded.flag"
            flag_path.write_text(
                f"Odoo health check failed at {datetime.now(timezone.utc).isoformat()}: {e}",
                encoding="utf-8",
            )
            log_action(VAULT_PATH, {
                "action_type": "odoo_health_degraded",
                "actor": "scheduler",
                "error": str(e)[:300],
            })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fill_social_draft(draft_path, platform: str, max_chars: int = 1300):
    """Use Claude to fill in the generated draft with actual content."""
    goals_path = VAULT_PATH / "Business_Goals.md"
    goals = ""
    if goals_path.exists():
        goals = goals_path.read_text(encoding="utf-8")

    char_note = f" (max {max_chars} characters)" if max_chars < 1300 else ""
    prompt = f"""You are an AI Employee creating a {platform} post.

## Business Goals
{goals}

## Instructions
Write a short, engaging {platform} post{char_note} based on the business goals above.
The post should:
- Be professional but approachable
- Include a concrete example or insight about AI automation
- End with a question or call-to-action
- NOT use hashtags excessively (max 3)

Output ONLY the post text, nothing else."""

    post_content = invoke_claude(prompt, VAULT_PATH)

    if "ERROR" not in post_content and draft_path.exists():
        draft_content = draft_path.read_text(encoding="utf-8")
        updated = draft_content.replace(
            f"_Draft pending: Run the orchestrator or use /draft-{platform.lower()}-post to generate content._",
            post_content,
        )
        # Also try the generic placeholder pattern
        if updated == draft_content:
            updated = draft_content.replace(
                "_Draft pending: Run the orchestrator or use /draft-tweet to generate content._",
                post_content,
            )
        draft_path.write_text(updated, encoding="utf-8")
        logger.info(f"{platform} draft updated with generated content")

    log_action(VAULT_PATH, {
        "action_type": f"{platform.lower()}_draft_generated",
        "file": draft_path.name,
        "actor": "scheduler",
    })


# ---------------------------------------------------------------------------
# Schedule setup & runner
# ---------------------------------------------------------------------------

def setup_schedule():
    """Configure all scheduled jobs, zone-aware."""
    sync_interval = int(os.getenv("VAULT_SYNC_INTERVAL", "60"))

    # Both zones: task processing, vault sync, Odoo health
    schedule.every(30).seconds.do(job_process_tasks)
    schedule.every(5).minutes.do(job_odoo_health_check)
    schedule.every(sync_interval).seconds.do(job_vault_sync)

    # Cloud-only jobs
    if ZONE == "cloud":
        schedule.every(2).minutes.do(job_poll_gmail)
        schedule.every().day.at("08:00").do(job_daily_briefing)
        schedule.every().monday.at("10:00").do(job_linkedin_draft)
        schedule.every().tuesday.at("10:30").do(job_facebook_draft)
        schedule.every().wednesday.at("10:30").do(job_twitter_draft)
        schedule.every().thursday.at("10:30").do(job_instagram_draft)
        schedule.every().sunday.at("20:00").do(job_weekly_audit)

    # Local-only jobs
    if ZONE == "local":
        schedule.every(5).minutes.do(job_notify_pending_approvals)

    logger.info(f"Schedule configured for zone={ZONE}:")
    logger.info("  [both]  Task processing: every 30 seconds")
    logger.info("  [both]  Odoo health check: every 5 minutes")
    logger.info(f"  [both]  Vault sync: every {sync_interval} seconds")
    if ZONE == "cloud":
        logger.info("  [cloud] Gmail poll: every 2 minutes")
        logger.info("  [cloud] Daily briefing: 8:00 AM")
        logger.info("  [cloud] LinkedIn draft: Monday 10:00 AM")
        logger.info("  [cloud] Facebook draft: Tuesday 10:30 AM")
        logger.info("  [cloud] Twitter draft: Wednesday 10:30 AM")
        logger.info("  [cloud] Instagram draft: Thursday 10:30 AM")
        logger.info("  [cloud] Weekly audit + CEO briefing: Sunday 8:00 PM")
    if ZONE == "local":
        logger.info("  [local] WhatsApp pending approval notify: every 5 minutes")


def run_scheduler():
    """Run the scheduler loop."""
    logger.info(f"AI Employee Scheduler starting — zone={ZONE}")

    # Start health server (Phase 3) if available
    try:
        from utils.health_server import start_health_server
        start_health_server()
        logger.info("Health server started on port 8080")
    except ImportError:
        logger.debug("Health server module not available — skipping")
    except Exception as e:
        logger.warning(f"Health server failed to start: {e}")

    setup_schedule()

    # Start filesystem watcher in a background thread
    watcher_thread = threading.Thread(
        target=run_watcher, args=(VAULT_PATH,), daemon=True
    )
    watcher_thread.start()
    logger.info("File watcher started in background")

    # Run initial task processing
    logger.info("Running initial task processing...")
    job_process_tasks()

    # Update dashboard
    update_dashboard(VAULT_PATH)

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")


if __name__ == "__main__":
    run_scheduler()

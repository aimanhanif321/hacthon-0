"""
Weekly Audit & CEO Briefing - Aggregates weekly data and generates reports.

Generates:
    - Briefings/YYYY-WXX_Weekly.md   — detailed weekly summary
    - Briefings/YYYY-WXX_CEO_Briefing.md — executive KPI dashboard

Usage:
    python -m skills.weekly_audit
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("WeeklyAudit")

DEFAULT_VAULT = Path(__file__).parent.parent / "AI_Employee_Vault"


def aggregate_weekly_data(vault: Path, days: int = 7) -> dict:
    """Read Done/, Logs/, Pending_Approval/ and build weekly statistics."""
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y%m%d")

    # --- Done tasks ---
    done_dir = vault / "Done"
    done_files = []
    if done_dir.exists():
        for f in done_dir.glob("*.md"):
            # Files are named YYYYMMDD_HHMMSS_<original>.md
            if f.name[:8] >= cutoff_str:
                done_files.append(f.name)

    # --- Log entries ---
    logs_dir = vault / "Logs"
    all_entries: list[dict] = []
    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.json")):
            # log files named YYYY-MM-DD.json
            file_date = log_file.stem
            if file_date >= cutoff.strftime("%Y-%m-%d"):
                try:
                    entries = json.loads(log_file.read_text(encoding="utf-8"))
                    all_entries.extend(entries)
                except (json.JSONDecodeError, KeyError):
                    continue

    # --- Pending approvals ---
    pending_dir = vault / "Pending_Approval"
    pending_files = list(pending_dir.glob("*.md")) if pending_dir.exists() else []

    # --- Rejected ---
    rejected_dir = vault / "Rejected"
    rejected_files = list(rejected_dir.glob("*.md")) if rejected_dir.exists() else []

    # --- Count by action type ---
    action_counts: dict[str, int] = {}
    for entry in all_entries:
        at = entry.get("action_type", "unknown")
        action_counts[at] = action_counts.get(at, 0) + 1

    # Social media stats
    linkedin_posts = action_counts.get("linkedin_draft_generated", 0)
    facebook_posts = action_counts.get("facebook_draft_generated", 0)
    twitter_posts = action_counts.get("twitter_draft_generated", 0)
    instagram_posts = action_counts.get("instagram_draft_generated", 0)
    emails_processed = action_counts.get("task_processed", 0)

    return {
        "period_start": cutoff.strftime("%Y-%m-%d"),
        "period_end": now.strftime("%Y-%m-%d"),
        "tasks_completed": len(done_files),
        "done_files": done_files[:20],  # Cap for readability
        "total_log_entries": len(all_entries),
        "action_counts": action_counts,
        "pending_approvals": [f.name for f in pending_files],
        "rejected_items": [f.name for f in rejected_files],
        "social_media": {
            "linkedin": linkedin_posts,
            "facebook": facebook_posts,
            "twitter": twitter_posts,
            "instagram": instagram_posts,
        },
        "emails_processed": emails_processed,
    }


def generate_weekly_briefing(vault: Path, data: dict) -> Path:
    """Generate Briefings/YYYY-WXX_Weekly.md with detailed weekly summary."""
    briefings = vault / "Briefings"
    briefings.mkdir(exist_ok=True)

    now = datetime.now()
    week_num = now.isocalendar()[1]
    filename = f"{now.year}-W{week_num:02d}_Weekly.md"
    filepath = briefings / filename

    social = data["social_media"]
    total_social = sum(social.values())

    pending_list = "\n".join(f"- {f}" for f in data["pending_approvals"]) or "- None"
    rejected_list = "\n".join(f"- {f}" for f in data["rejected_items"]) or "- None"
    done_list = "\n".join(f"- {f}" for f in data["done_files"]) or "- None"

    action_table = "\n".join(
        f"| {k} | {v} |" for k, v in sorted(data["action_counts"].items(), key=lambda x: -x[1])
    )

    content = f"""---
type: weekly_briefing
period: {data['period_start']} to {data['period_end']}
generated: {datetime.now(timezone.utc).isoformat()}
---

# Weekly Summary — {data['period_start']} to {data['period_end']}

## Overview
- **Tasks Completed**: {data['tasks_completed']}
- **Total Log Entries**: {data['total_log_entries']}
- **Emails Processed**: {data['emails_processed']}
- **Social Media Drafts**: {total_social} (LinkedIn: {social['linkedin']}, Facebook: {social['facebook']}, Twitter: {social['twitter']}, Instagram: {social['instagram']})

## Completed Tasks
{done_list}

## Action Breakdown
| Action Type | Count |
|-------------|-------|
{action_table}

## Pending Approvals
{pending_list}

## Rejected Items
{rejected_list}

## Recommendations
- Review any stale items in Pending_Approval/
- Check rejected items for patterns to improve automation
- Monitor social media engagement from published posts
"""
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Weekly briefing saved: {filename}")
    return filepath


def generate_ceo_briefing(vault: Path, data: dict) -> Path:
    """Generate Briefings/YYYY-WXX_CEO_Briefing.md with executive-level KPI dashboard."""
    briefings = vault / "Briefings"
    briefings.mkdir(exist_ok=True)

    now = datetime.now()
    week_num = now.isocalendar()[1]
    filename = f"{now.year}-W{week_num:02d}_CEO_Briefing.md"
    filepath = briefings / filename

    social = data["social_media"]
    total_social = sum(social.values())

    content = f"""---
type: ceo_briefing
period: {data['period_start']} to {data['period_end']}
generated: {datetime.now(timezone.utc).isoformat()}
---

# CEO Briefing — Week {week_num}, {now.year}

## KPI Dashboard

| Metric | This Week |
|--------|-----------|
| Tasks Completed | {data['tasks_completed']} |
| Emails Processed | {data['emails_processed']} |
| Social Posts Drafted | {total_social} |
| Pending Approvals | {len(data['pending_approvals'])} |
| Rejected Actions | {len(data['rejected_items'])} |
| Total Automated Actions | {data['total_log_entries']} |

## Social Media Breakdown

| Platform | Drafts Created |
|----------|---------------|
| LinkedIn | {social['linkedin']} |
| Facebook | {social['facebook']} |
| Twitter/X | {social['twitter']} |
| Instagram | {social['instagram']} |

## Key Achievements
- Processed **{data['tasks_completed']}** tasks autonomously
- Generated **{total_social}** social media drafts for review
- Logged **{data['total_log_entries']}** automated actions

## Action Items
{"- **" + str(len(data['pending_approvals'])) + " items** awaiting your approval in Pending_Approval/" if data['pending_approvals'] else "- No items pending approval"}
{"- **" + str(len(data['rejected_items'])) + " items** were rejected this week — review for automation improvements" if data['rejected_items'] else "- No rejections this week"}

## Strategic Recommendations
- Maintain consistent social media posting cadence across all platforms
- Review approval turnaround times to reduce bottlenecks
- Consider expanding automation to additional business processes
"""
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"CEO briefing saved: {filename}")
    return filepath


def run_weekly_audit(vault: Path | None = None):
    """Main entry point: aggregate data and generate both reports."""
    vault = vault or DEFAULT_VAULT
    logger.info("Running weekly audit...")

    data = aggregate_weekly_data(vault)
    weekly_path = generate_weekly_briefing(vault, data)
    ceo_path = generate_ceo_briefing(vault, data)

    # Log the audit
    from utils.audit import log
    log(vault, action_type="weekly_audit_completed", actor="weekly_audit",
        weekly_briefing=weekly_path.name, ceo_briefing=ceo_path.name,
        tasks_completed=data["tasks_completed"])

    logger.info("Weekly audit complete.")
    return {"weekly": weekly_path, "ceo": ceo_path, "data": data}


if __name__ == "__main__":
    run_weekly_audit()

"""
Twitter/X Auto-Poster - Generates and posts tweets.

Posts go through the approval workflow:
1. Claude generates a draft based on Business_Goals.md
2. Draft is saved to /Pending_Approval/TWEET_<date>.md
3. Human reviews and moves to /Approved/ or /Rejected/
4. Orchestrator picks up approved tweets and publishes them

Requires:
    - Twitter Developer Account with API v2 access
    - See docs/TWITTER_SETUP.md for setup instructions

Usage:
    python -m skills.twitter_poster              # Create draft for approval
    python -m skills.twitter_poster --post FILE  # Post an approved file
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("TwitterPoster")

DEFAULT_VAULT = Path(__file__).parent.parent / "AI_Employee_Vault"

TWEET_MAX_LENGTH = 280


def get_twitter_config() -> dict | None:
    """Load Twitter credentials from environment."""
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, access_token, access_token_secret]):
        logger.error(
            "Twitter API credentials must be set in .env. "
            "See docs/TWITTER_SETUP.md for setup instructions."
        )
        return None

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "access_token": access_token,
        "access_token_secret": access_token_secret,
        "bearer_token": os.getenv("TWITTER_BEARER_TOKEN", ""),
    }


def get_twitter_client():
    """Create an authenticated tweepy Client."""
    config = get_twitter_config()
    if not config:
        return None

    import tweepy
    return tweepy.Client(
        bearer_token=config["bearer_token"] or None,
        consumer_key=config["api_key"],
        consumer_secret=config["api_secret"],
        access_token=config["access_token"],
        access_token_secret=config["access_token_secret"],
    )


def post_tweet(text: str) -> dict:
    """Post a tweet. Enforces 280-character limit."""
    if len(text) > TWEET_MAX_LENGTH:
        return {"success": False, "error": f"Tweet exceeds {TWEET_MAX_LENGTH} chars ({len(text)})"}

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    if dry_run:
        logger.info("[DRY RUN] Would tweet:")
        logger.info(text)
        return {"success": True, "dry_run": True, "message": "Tweet simulated (DRY_RUN=true)"}

    client = get_twitter_client()
    if not client:
        return {"success": False, "error": "Twitter not configured"}

    try:
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        logger.info(f"Posted tweet: {tweet_id}")
        return {"success": True, "tweet_id": tweet_id}
    except Exception as e:
        logger.error(f"Twitter API error: {e}")
        return {"success": False, "error": str(e)}


def create_post_draft(vault: Path | None = None) -> Path:
    """Create a tweet draft in /Pending_Approval for human review."""
    vault = vault or DEFAULT_VAULT
    pending = vault / "Pending_Approval"
    pending.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"TWEET_{date_str}.md"
    filepath = pending / filename

    if filepath.exists():
        logger.info(f"Draft already exists for today: {filename}")
        return filepath

    goals_path = vault / "Business_Goals.md"
    goals_context = ""
    if goals_path.exists():
        goals_context = goals_path.read_text(encoding="utf-8")

    content = f"""---
type: tweet
action: twitter_post
status: pending_approval
created: {now}
priority: medium
---

# Tweet Draft - {date_str}

## Business Context
{goals_context or "_No Business_Goals.md found._"}

## Post Content
<!-- Replace this section with your tweet (max 280 chars) before approving -->

_Draft pending: Run the orchestrator or use /draft-tweet to generate content._

## Instructions
1. Review and edit the tweet above (max {TWEET_MAX_LENGTH} characters)
2. Move this file to `/Approved/` to publish
3. Move to `/Rejected/` to discard
"""
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Created tweet draft: {filename}")
    return filepath


def execute_approved_post(approved_file: Path) -> dict:
    """Execute an approved tweet from /Approved."""
    content = approved_file.read_text(encoding="utf-8")

    # Extract post text
    post_text = ""
    in_post_section = False
    for line in content.split("\n"):
        if line.startswith("## Post Content"):
            in_post_section = True
            continue
        if in_post_section and line.startswith("## "):
            break
        if in_post_section:
            post_text += line + "\n"

    post_text = post_text.strip()
    if not post_text or post_text.startswith("<!--") or post_text.startswith("_Draft pending"):
        return {"success": False, "error": "Tweet content is empty or still a placeholder."}

    return post_tweet(post_text)


def generate_twitter_summary(vault: Path | None = None, days: int = 7) -> dict:
    """Aggregate tweet stats from logs for the last N days."""
    vault = vault or DEFAULT_VAULT
    logs_dir = vault / "Logs"
    tweet_count = 0

    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.json"))[-days:]:
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
                for entry in entries:
                    if "twitter" in entry.get("action_type", "") or "tweet" in entry.get("action_type", ""):
                        tweet_count += 1
            except (json.JSONDecodeError, KeyError):
                continue

    return {"tweets_posted": tweet_count, "days": days}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--post":
        result = execute_approved_post(Path(sys.argv[2]))
        print(json.dumps(result, indent=2))
    else:
        create_post_draft()

"""
Meta (Facebook/Instagram) Auto-Poster - Generates and posts content.

Posts go through the approval workflow:
1. Claude generates a draft based on Business_Goals.md
2. Draft is saved to /Pending_Approval/FB_POST_<date>.md or IG_POST_<date>.md
3. Human reviews and moves to /Approved/ or /Rejected/
4. Orchestrator picks up approved posts and publishes them

Requires:
    - Meta Developer App with Page Access Token
    - See docs/META_SETUP.md for setup instructions

Usage:
    python -m skills.meta_poster              # Create Facebook draft for approval
    python -m skills.meta_poster --instagram  # Create Instagram draft
    python -m skills.meta_poster --post FILE  # Post an approved file
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("MetaPoster")

DEFAULT_VAULT = Path(__file__).parent.parent / "AI_Employee_Vault"

META_GRAPH_URL = "https://graph.facebook.com/v19.0"


def get_meta_config() -> dict | None:
    """Load Meta credentials from environment."""
    token = os.getenv("META_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")

    if not token or not page_id:
        logger.error(
            "META_ACCESS_TOKEN and META_PAGE_ID must be set in .env. "
            "See docs/META_SETUP.md for setup instructions."
        )
        return None

    return {
        "access_token": token,
        "page_id": page_id,
        "ig_account_id": os.getenv("META_INSTAGRAM_ACCOUNT_ID", ""),
    }


def post_to_facebook(text: str, config: dict) -> dict:
    """Post content to a Facebook Page."""
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        logger.info("[DRY RUN] Would post to Facebook:")
        logger.info(text[:200])
        return {"success": True, "dry_run": True, "message": "Post simulated (DRY_RUN=true)"}

    try:
        url = f"{META_GRAPH_URL}/{config['page_id']}/feed"
        response = httpx.post(url, params={
            "message": text,
            "access_token": config["access_token"],
        }, timeout=30)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"Posted to Facebook: {data.get('id')}")
            return {"success": True, "post_id": data.get("id")}
        else:
            logger.error(f"Facebook API error: {response.status_code} {response.text}")
            return {"success": False, "error": f"{response.status_code}: {response.text}"}

    except httpx.HTTPError as e:
        logger.error(f"HTTP error posting to Facebook: {e}")
        return {"success": False, "error": str(e)}


def post_to_instagram(text: str, image_url: str, config: dict) -> dict:
    """Post content to Instagram (requires an image URL)."""
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        logger.info("[DRY RUN] Would post to Instagram:")
        logger.info(text[:200])
        return {"success": True, "dry_run": True, "message": "Post simulated (DRY_RUN=true)"}

    ig_account_id = config.get("ig_account_id")
    if not ig_account_id:
        return {"success": False, "error": "META_INSTAGRAM_ACCOUNT_ID not configured"}

    try:
        # Step 1: Create media container
        container_url = f"{META_GRAPH_URL}/{ig_account_id}/media"
        container_resp = httpx.post(container_url, params={
            "image_url": image_url,
            "caption": text,
            "access_token": config["access_token"],
        }, timeout=30)

        if container_resp.status_code != 200:
            return {"success": False, "error": f"Container creation failed: {container_resp.text}"}

        creation_id = container_resp.json().get("id")

        # Step 2: Publish the container
        publish_url = f"{META_GRAPH_URL}/{ig_account_id}/media_publish"
        publish_resp = httpx.post(publish_url, params={
            "creation_id": creation_id,
            "access_token": config["access_token"],
        }, timeout=30)

        if publish_resp.status_code == 200:
            data = publish_resp.json()
            logger.info(f"Posted to Instagram: {data.get('id')}")
            return {"success": True, "post_id": data.get("id")}
        else:
            return {"success": False, "error": f"Publish failed: {publish_resp.text}"}

    except httpx.HTTPError as e:
        logger.error(f"HTTP error posting to Instagram: {e}")
        return {"success": False, "error": str(e)}


def create_post_draft(vault: Path | None = None, platform: str = "facebook") -> Path:
    """Create a social media post draft in /Pending_Approval for human review."""
    vault = vault or DEFAULT_VAULT
    pending = vault / "Pending_Approval"
    pending.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now().strftime("%Y-%m-%d")

    if platform == "instagram":
        prefix = "IG_POST"
        action = "instagram_post"
    else:
        prefix = "FB_POST"
        action = "facebook_post"

    filename = f"{prefix}_{date_str}.md"
    filepath = pending / filename

    if filepath.exists():
        logger.info(f"Draft already exists for today: {filename}")
        return filepath

    goals_path = vault / "Business_Goals.md"
    goals_context = ""
    if goals_path.exists():
        goals_context = goals_path.read_text(encoding="utf-8")

    content = f"""---
type: {platform}_post
action: {action}
status: pending_approval
created: {now}
priority: medium
---

# {platform.title()} Post Draft - {date_str}

## Business Context
{goals_context or "_No Business_Goals.md found._"}

## Post Content
<!-- Replace this section with your post text before approving -->

_Draft pending: Run the orchestrator or use /draft-{platform}-post to generate content._

## Instructions
1. Review and edit the post content above
2. Move this file to `/Approved/` to publish
3. Move to `/Rejected/` to discard
"""
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Created {platform} post draft: {filename}")
    return filepath


def execute_approved_post(approved_file: Path) -> dict:
    """Execute an approved Meta post from /Approved."""
    config = get_meta_config()
    if not config:
        return {"success": False, "error": "Meta not configured"}

    content = approved_file.read_text(encoding="utf-8")

    # Determine platform from frontmatter
    from utils.frontmatter import parse_frontmatter
    fm = parse_frontmatter(content)
    action = fm.get("action", "facebook_post")

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
        return {"success": False, "error": "Post content is empty or still a placeholder."}

    if action == "instagram_post":
        image_url = fm.get("image_url", "")
        if not image_url:
            return {"success": False, "error": "Instagram posts require an image_url in frontmatter."}
        return post_to_instagram(post_text, image_url, config)
    else:
        return post_to_facebook(post_text, config)


def generate_meta_summary(vault: Path | None = None, days: int = 7) -> dict:
    """Aggregate posting stats from logs for the last N days."""
    vault = vault or DEFAULT_VAULT
    logs_dir = vault / "Logs"
    fb_posts = 0
    ig_posts = 0

    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.json"))[-days:]:
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
                for entry in entries:
                    at = entry.get("action_type", "")
                    if "facebook" in at:
                        fb_posts += 1
                    if "instagram" in at:
                        ig_posts += 1
            except (json.JSONDecodeError, KeyError):
                continue

    return {"facebook_posts": fb_posts, "instagram_posts": ig_posts, "days": days}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--post":
        result = execute_approved_post(Path(sys.argv[2]))
        print(json.dumps(result, indent=2))
    elif "--instagram" in sys.argv:
        create_post_draft(platform="instagram")
    else:
        create_post_draft(platform="facebook")

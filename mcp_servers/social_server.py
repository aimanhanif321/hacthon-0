"""
Social Media MCP Server - Exposes social media tools via stdin/stdout JSON-RPC.

Tools:
    - post_facebook: Post to a Facebook Page
    - post_instagram: Post to Instagram (requires image URL)
    - post_tweet: Post a tweet (max 280 chars)
    - draft_social_post: Create a draft for any platform in Pending_Approval/
    - get_social_summary: Get posting stats from logs
    - list_pending_posts: List social media posts awaiting approval

Delegates to skills/meta_poster.py and skills/twitter_poster.py.
All API calls go directly to cloud endpoints (Meta Graph API, Twitter API).

Usage:
    python -m mcp_servers.social_server

Configure in .claude/mcp.json to use with Claude Code.
"""

import os
import sys
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# Add parent to path for skill imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("SocialMCPServer")

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "social-server"
SERVER_VERSION = "0.1.0"

VAULT_PATH = Path(__file__).parent.parent / "AI_Employee_Vault"


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def handle_post_facebook(params: dict) -> dict:
    """Post to Facebook via meta_poster skill."""
    text = params.get("text", "")
    if not text:
        return {"error": "Required: text"}
    from skills.meta_poster import post_to_facebook, get_meta_config
    config = get_meta_config()
    if not config:
        return {"error": "Meta not configured — see docs/META_SETUP.md"}
    return post_to_facebook(text, config)


def handle_post_instagram(params: dict) -> dict:
    """Post to Instagram via meta_poster skill."""
    text = params.get("text", "")
    image_url = params.get("image_url", "")
    if not text or not image_url:
        return {"error": "Required: text and image_url"}
    from skills.meta_poster import post_to_instagram, get_meta_config
    config = get_meta_config()
    if not config:
        return {"error": "Meta not configured — see docs/META_SETUP.md"}
    return post_to_instagram(text, image_url, config)


def handle_post_tweet(params: dict) -> dict:
    """Post a tweet via twitter_poster skill."""
    text = params.get("text", "")
    if not text:
        return {"error": "Required: text"}
    from skills.twitter_poster import post_tweet
    return post_tweet(text)


def handle_draft_social_post(params: dict) -> dict:
    """Create a draft for the specified platform."""
    platform = params.get("platform", "facebook").lower()
    if platform in ("facebook", "instagram"):
        from skills.meta_poster import create_post_draft
        path = create_post_draft(VAULT_PATH, platform=platform)
    elif platform in ("twitter", "tweet"):
        from skills.twitter_poster import create_post_draft
        path = create_post_draft(VAULT_PATH)
    else:
        return {"error": f"Unknown platform: {platform}. Use facebook, instagram, or twitter."}
    return {"success": True, "file": str(path.name)}


def handle_get_social_summary(params: dict) -> dict:
    """Aggregate posting stats across all platforms."""
    days = params.get("days", 7)
    from skills.meta_poster import generate_meta_summary
    from skills.twitter_poster import generate_twitter_summary
    meta = generate_meta_summary(VAULT_PATH, days)
    twitter = generate_twitter_summary(VAULT_PATH, days)
    return {
        "success": True,
        "days": days,
        "facebook_posts": meta["facebook_posts"],
        "instagram_posts": meta["instagram_posts"],
        "tweets": twitter["tweets_posted"],
    }


def handle_list_pending_posts(params: dict) -> dict:
    """List social media posts awaiting approval."""
    pending_dir = VAULT_PATH / "Pending_Approval"
    posts = []
    if pending_dir.exists():
        for f in pending_dir.glob("*.md"):
            if f.stem.startswith(("FB_POST", "IG_POST", "TWEET", "LINKEDIN_POST")):
                posts.append({"file": f.name, "platform": _detect_platform(f.name)})
    return {"success": True, "pending_posts": posts, "count": len(posts)}


def _detect_platform(filename: str) -> str:
    if filename.startswith("FB_POST"):
        return "facebook"
    if filename.startswith("IG_POST"):
        return "instagram"
    if filename.startswith("TWEET"):
        return "twitter"
    if filename.startswith("LINKEDIN"):
        return "linkedin"
    return "unknown"


# ---------------------------------------------------------------------------
# MCP Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "post_facebook",
        "description": "Post text content to a Facebook Page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Post text content"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "post_instagram",
        "description": "Post to Instagram (requires image URL and caption text).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Caption text"},
                "image_url": {"type": "string", "description": "Public URL of the image to post"},
            },
            "required": ["text", "image_url"],
        },
    },
    {
        "name": "post_tweet",
        "description": "Post a tweet (max 280 characters).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Tweet text (max 280 chars)"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "draft_social_post",
        "description": "Create a social media post draft in Pending_Approval/ for human review.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "Platform: facebook, instagram, or twitter",
                    "enum": ["facebook", "instagram", "twitter"],
                },
            },
            "required": ["platform"],
        },
    },
    {
        "name": "get_social_summary",
        "description": "Get posting statistics across all social media platforms.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Number of days to aggregate (default 7)", "default": 7},
            },
        },
    },
    {
        "name": "list_pending_posts",
        "description": "List all social media posts currently awaiting human approval.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

TOOL_HANDLERS = {
    "post_facebook": handle_post_facebook,
    "post_instagram": handle_post_instagram,
    "post_tweet": handle_post_tweet,
    "draft_social_post": handle_draft_social_post,
    "get_social_summary": handle_get_social_summary,
    "list_pending_posts": handle_list_pending_posts,
}


# ---------------------------------------------------------------------------
# JSON-RPC transport
# ---------------------------------------------------------------------------

def send_response(response: dict):
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_request(request: dict) -> dict | None:
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool_name}"})}],
                    "isError": True,
                },
            }
        result = handler(tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}],
                "isError": "error" in result,
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    logger.info("Social Media MCP Server starting...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            send_response({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        response = handle_request(request)
        if response is not None:
            send_response(response)
    logger.info("Social Media MCP Server stopped.")


if __name__ == "__main__":
    main()

"""
WhatsApp Notifier - Send approval-request notifications via WhatsApp Business API.

When a sensitive action lands in Pending_Approval/, this module sends a WhatsApp
message to the human operator so they can approve/reject from their phone.

Requires Meta Graph API access for WhatsApp Business.
See docs/WHATSAPP_SETUP.md for setup instructions.

Usage:
    from skills.whatsapp_notifier import send_approval_request, process_whatsapp_reply
    send_approval_request(file_path, vault)
    process_whatsapp_reply("APPROVE EMAIL_REPLY_123.md", vault)
"""

import os
import re
import json
import shutil
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
logger = logging.getLogger("WhatsAppNotifier")

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _config() -> dict | None:
    """Load WhatsApp credentials from environment."""
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    recipient = os.getenv("WHATSAPP_RECIPIENT_NUMBER")

    if not all([phone_id, token, recipient]):
        logger.error(
            "WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ACCESS_TOKEN, and "
            "WHATSAPP_RECIPIENT_NUMBER must be set in .env. "
            "See docs/WHATSAPP_SETUP.md for setup."
        )
        return None

    return {
        "phone_number_id": phone_id,
        "access_token": token,
        "recipient_number": recipient,
    }


def send_approval_request(file_path: Path, vault: Path) -> dict:
    """Send a WhatsApp message asking the human to approve/reject *file_path*.

    Returns dict with 'success' boolean and 'message_id' or 'error'.
    """
    cfg = _config()
    if not cfg:
        return {"success": False, "error": "WhatsApp not configured"}

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    # Read the file to extract action type from frontmatter
    content = file_path.read_text(encoding="utf-8")
    action = "unknown"
    for line in content.split("\n"):
        if line.strip().startswith("action:"):
            action = line.split(":", 1)[1].strip()
            break

    filename = file_path.name
    text = (
        f"AI Employee needs approval:\n\n"
        f"File: {filename}\n"
        f"Action: {action}\n\n"
        f"Reply:\n"
        f"  APPROVE {filename}\n"
        f"  REJECT {filename}"
    )

    if dry_run:
        logger.info(f"[DRY RUN] Would send WhatsApp: {text[:200]}")
        return {"success": True, "dry_run": True, "message": text}

    url = f"{GRAPH_API_BASE}/{cfg['phone_number_id']}/messages"
    headers = {
        "Authorization": f"Bearer {cfg['access_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": cfg["recipient_number"],
        "type": "text",
        "text": {"body": text},
    }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "unknown")
            logger.info(f"WhatsApp sent for {filename}: message_id={msg_id}")
            return {"success": True, "message_id": msg_id}
        else:
            logger.error(f"WhatsApp API error: {resp.status_code} {resp.text}")
            return {"success": False, "error": f"{resp.status_code}: {resp.text[:300]}"}
    except httpx.HTTPError as e:
        logger.error(f"WhatsApp HTTP error: {e}")
        return {"success": False, "error": str(e)}


def process_whatsapp_reply(reply_text: str, vault: Path) -> dict:
    """Parse an inbound WhatsApp reply and move the file accordingly.

    Expected formats:
        APPROVE <filename>
        REJECT <filename>

    Returns dict with 'success', 'action', 'file'.
    """
    reply_text = reply_text.strip()
    match = re.match(r"^(APPROVE|REJECT)\s+(.+)$", reply_text, re.IGNORECASE)
    if not match:
        return {"success": False, "error": f"Unrecognized reply: {reply_text[:100]}"}

    action = match.group(1).upper()
    filename = match.group(2).strip()

    pending_dir = vault / "Pending_Approval"
    source = pending_dir / filename

    if not source.exists():
        # Try case-insensitive search
        found = [f for f in pending_dir.iterdir() if f.name.lower() == filename.lower()]
        if found:
            source = found[0]
        else:
            return {"success": False, "error": f"File not found: {filename}"}

    if action == "APPROVE":
        dest_dir = vault / "Approved"
    else:
        dest_dir = vault / "Rejected"

    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / source.name
    shutil.move(str(source), str(dest))

    logger.info(f"WhatsApp {action}: {source.name} → {dest_dir.name}/")

    # Log the action
    try:
        from utils.audit import log as audit_log
        audit_log(
            vault,
            action_type=f"whatsapp_{action.lower()}",
            actor="whatsapp_user",
            file=source.name,
        )
    except Exception:
        pass

    return {"success": True, "action": action, "file": source.name}

"""
Gmail Watcher - Polls Gmail for unread important emails
and creates action items in /Needs_Action for Claude to process.

Requires:
    - Google Cloud project with Gmail API enabled
    - credentials.json (OAuth client ID)
    - See docs/GMAIL_SETUP.md for full setup instructions

Usage:
    python -m watchers.gmail_watcher
"""

import json
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(override=True)

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("GmailWatcher")

DEFAULT_VAULT = Path(__file__).parent.parent / "AI_Employee_Vault"

# Gmail API scopes - read-only for watching
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Track processed message IDs to avoid duplicates
PROCESSED_IDS_FILE = Path(__file__).parent / ".gmail_processed_ids.json"


def get_gmail_service():
    """Authenticate and return a Gmail API service instance."""
    creds_path = os.getenv("GMAIL_CREDENTIALS_PATH", "./credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "./token.json")

    creds = None

    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(creds_path).exists():
                logger.error(
                    f"credentials.json not found at {creds_path}. "
                    "See docs/GMAIL_SETUP.md for setup instructions."
                )
                return None
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        Path(token_path).write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def load_processed_ids() -> set[str]:
    """Load previously processed message IDs."""
    if PROCESSED_IDS_FILE.exists():
        try:
            data = json.loads(PROCESSED_IDS_FILE.read_text(encoding="utf-8"))
            return set(data)
        except (json.JSONDecodeError, TypeError):
            return set()
    return set()


def save_processed_ids(ids: set[str]):
    """Save processed message IDs to disk."""
    # Keep only the last 1000 IDs to prevent unbounded growth
    trimmed = sorted(ids)[-1000:]
    PROCESSED_IDS_FILE.write_text(json.dumps(trimmed), encoding="utf-8")


def classify_email_priority(subject: str, labels: list[str]) -> str:
    """Classify email priority based on subject and labels."""
    subject_lower = subject.lower()

    if "IMPORTANT" in labels or "CATEGORY_PERSONAL" in labels:
        if any(kw in subject_lower for kw in ["urgent", "asap", "critical", "payment", "invoice"]):
            return "critical"
        return "high"

    if any(kw in subject_lower for kw in ["meeting", "deadline", "review", "action required"]):
        return "high"

    if any(kw in subject_lower for kw in ["update", "report", "summary", "fyi"]):
        return "medium"

    return "low"


def fetch_unread_emails(service, max_results: int = 10) -> list[dict]:
    """Fetch unread emails from Gmail."""
    try:
        results = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=max_results,
        ).execute()
    except Exception as e:
        logger.error(f"Failed to fetch emails: {e}")
        return []

    messages = results.get("messages", [])
    if not messages:
        logger.info("No unread emails found")
        return []

    emails = []
    for msg_info in messages:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=msg_info["id"],
                format="full",
            ).execute()

            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            labels = msg.get("labelIds", [])

            # Extract body snippet
            snippet = msg.get("snippet", "")

            # Try to get plain text body
            body = ""
            payload = msg["payload"]
            if "parts" in payload:
                for part in payload["parts"]:
                    if part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                        break
            elif "body" in payload and "data" in payload["body"]:
                body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

            emails.append({
                "id": msg_info["id"],
                "subject": headers.get("Subject", "(no subject)"),
                "from": headers.get("From", "unknown"),
                "date": headers.get("Date", ""),
                "snippet": snippet,
                "body": body[:2000],  # Limit body size
                "labels": labels,
            })

        except Exception as e:
            logger.error(f"Failed to process message {msg_info['id']}: {e}")

    return emails


def create_email_action(email: dict, vault: Path):
    """Create an action file in /Needs_Action for an email."""
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    safe_id = email["id"][:12]
    timestamp = datetime.now().strftime("%H%M%S")
    action_filename = f"EMAIL_{safe_id}_{timestamp}.md"
    action_path = needs_action / action_filename

    priority = classify_email_priority(email["subject"], email["labels"])

    content = f"""---
type: email
source: gmail
message_id: {email['id']}
from: "{email['from']}"
subject: "{email['subject']}"
date: "{email['date']}"
priority: {priority}
status: pending
created: {now}
---

# Email: {email['subject']}

## Sender
{email['from']}

## Date
{email['date']}

## Body
{email['body'] or email['snippet']}

## Suggested Actions
- [ ] Read and understand email content
- [ ] Determine if reply is needed
- [ ] If payment/sensitive: create approval in /Pending_Approval
- [ ] Process and move to /Done
"""
    action_path.write_text(content, encoding="utf-8")
    logger.info(f"Created email action: {action_filename} (priority: {priority})")


def poll_gmail(vault: Path | None = None):
    """Poll Gmail for new unread emails and create action files."""
    vault = vault or DEFAULT_VAULT

    service = get_gmail_service()
    if not service:
        logger.error("Could not connect to Gmail. Check credentials.")
        return

    processed_ids = load_processed_ids()
    emails = fetch_unread_emails(service)

    new_count = 0
    for email in emails:
        if email["id"] not in processed_ids:
            create_email_action(email, vault)
            processed_ids.add(email["id"])
            new_count += 1

    save_processed_ids(processed_ids)

    if new_count:
        logger.info(f"Created {new_count} new email action(s)")
    else:
        logger.info("No new emails to process")


if __name__ == "__main__":
    poll_gmail()

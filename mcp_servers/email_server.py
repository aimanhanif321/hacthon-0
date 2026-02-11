"""
Email MCP Server - Exposes email tools via stdin/stdout JSON-RPC protocol.

Tools:
    - send_email: Send an email via Gmail API
    - draft_email: Create an email draft in Gmail
    - list_drafts: List recent email drafts

Requires:
    - Gmail API credentials with gmail.send scope
    - See docs/GMAIL_SETUP.md for setup instructions

Usage:
    python -m mcp_servers.email_server

Configure in .claude/mcp.json to use with Claude Code.
"""

import os
import sys
import json
import base64
import logging
from pathlib import Path
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv(override=True)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,  # Log to stderr so stdout stays clean for JSON-RPC
)
logger = logging.getLogger("EmailMCPServer")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# MCP Protocol version
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "email-server"
SERVER_VERSION = "0.1.0"


def get_gmail_service():
    """Authenticate and return a Gmail API service."""
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
                raise FileNotFoundError(
                    f"credentials.json not found at {creds_path}. "
                    "See docs/GMAIL_SETUP.md for setup."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(token_path).write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def handle_send_email(params: dict) -> dict:
    """Send an email via Gmail API."""
    to = params.get("to")
    subject = params.get("subject", "")
    body = params.get("body", "")

    if not to:
        return {"error": "Missing required parameter: 'to'"}

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "message": f"[DRY RUN] Would send email to {to} with subject: {subject}",
        }

    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        result = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        return {"success": True, "message_id": result.get("id")}

    except Exception as e:
        return {"error": str(e)}


def handle_draft_email(params: dict) -> dict:
    """Create an email draft in Gmail."""
    to = params.get("to")
    subject = params.get("subject", "")
    body = params.get("body", "")

    if not to:
        return {"error": "Missing required parameter: 'to'"}

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "message": f"[DRY RUN] Would create draft to {to} with subject: {subject}",
        }

    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        draft = service.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()

        return {"success": True, "draft_id": draft.get("id")}

    except Exception as e:
        return {"error": str(e)}


def handle_list_drafts(params: dict) -> dict:
    """List recent email drafts from Gmail."""
    max_results = params.get("max_results", 10)

    try:
        service = get_gmail_service()
        results = service.users().drafts().list(
            userId="me", maxResults=max_results
        ).execute()

        drafts = []
        for draft_info in results.get("drafts", []):
            draft = service.users().drafts().get(
                userId="me", id=draft_info["id"]
            ).execute()
            headers = {
                h["name"]: h["value"]
                for h in draft["message"]["payload"]["headers"]
            }
            drafts.append({
                "id": draft_info["id"],
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", ""),
                "snippet": draft["message"].get("snippet", ""),
            })

        return {"success": True, "drafts": drafts, "count": len(drafts)}

    except Exception as e:
        return {"error": str(e)}


# Tool definitions for MCP
TOOLS = [
    {
        "name": "send_email",
        "description": "Send an email via Gmail. Requires 'to', 'subject', and 'body' parameters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "draft_email",
        "description": "Create an email draft in Gmail. Requires 'to', 'subject', and 'body' parameters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "list_drafts",
        "description": "List recent email drafts from Gmail.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of drafts to return (default: 10)",
                    "default": 10,
                },
            },
        },
    },
]

TOOL_HANDLERS = {
    "send_email": handle_send_email,
    "draft_email": handle_draft_email,
    "list_drafts": handle_list_drafts,
}


def send_response(response: dict):
    """Write a JSON-RPC response to stdout."""
    line = json.dumps(response)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_request(request: dict) -> dict:
    """Handle a single JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    elif method == "notifications/initialized":
        # No response needed for notifications
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"error": f"Unknown tool: {tool_name}"}),
                        }
                    ],
                    "isError": True,
                },
            }

        result = handler(tool_args)
        is_error = "error" in result

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result),
                    }
                ],
                "isError": is_error,
            },
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }


def main():
    """Run the MCP server, reading JSON-RPC messages from stdin."""
    logger.info("Email MCP Server starting...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            send_response({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            })
            continue

        response = handle_request(request)
        if response is not None:
            send_response(response)

    logger.info("Email MCP Server stopped.")


if __name__ == "__main__":
    main()

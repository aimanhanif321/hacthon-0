"""
WhatsApp Webhook - Receives inbound WhatsApp messages via Meta webhook.

Two routes:
  GET  /webhook — Meta verification challenge
  POST /webhook — Inbound message handler (calls process_whatsapp_reply)

Run as a separate process:
    uv run python -m utils.whatsapp_webhook

For hackathon demos, expose via ngrok:
    ngrok http 5001

Then configure the webhook URL in Meta Developer Console.
"""

import os
import json
import logging
from pathlib import Path

from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("WhatsAppWebhook")

app = Flask(__name__)

VAULT_PATH = Path(__file__).parent.parent / "AI_Employee_Vault"
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "ai-employee-token")


@app.route("/webhook", methods=["GET"])
def verify():
    """Meta webhook verification challenge."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return challenge, 200
    else:
        logger.warning("Webhook verification failed")
        return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def receive():
    """Handle inbound WhatsApp messages."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "no data"}), 400

    try:
        # Extract message text from Meta webhook payload
        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    if msg.get("type") == "text":
                        text = msg["text"]["body"]
                        sender = msg.get("from", "unknown")
                        logger.info(f"WhatsApp message from {sender}: {text}")

                        # Process the reply
                        from skills.whatsapp_notifier import process_whatsapp_reply
                        result = process_whatsapp_reply(text, VAULT_PATH)
                        logger.info(f"Reply processed: {result}")

                        # Log via audit
                        try:
                            from utils.audit import log as audit_log
                            audit_log(
                                VAULT_PATH,
                                action_type="whatsapp_webhook_received",
                                actor=f"whatsapp:{sender}",
                                message=text[:200],
                                result=str(result)[:300],
                            )
                        except Exception:
                            pass

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")

    # Always return 200 to acknowledge receipt (Meta requirement)
    return jsonify({"status": "received"}), 200


@app.route("/health", methods=["GET"])
def health():
    """Simple health check for the webhook server."""
    return jsonify({"status": "ok", "service": "whatsapp-webhook"}), 200


def main():
    port = int(os.getenv("WEBHOOK_PORT", "5001"))
    logger.info(f"WhatsApp webhook server starting on port {port}")
    logger.info(f"Vault path: {VAULT_PATH}")
    logger.info(f"Verify token: {VERIFY_TOKEN[:4]}...")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()

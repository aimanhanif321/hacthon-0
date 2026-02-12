# WhatsApp Business API Setup

This guide configures WhatsApp Business API for mobile approval workflows.
The AI Employee sends approval requests to your WhatsApp; you reply APPROVE/REJECT.

## Prerequisites

- Meta Developer Account (https://developers.facebook.com)
- A Meta Business App with WhatsApp product added
- A test phone number (Meta provides one in sandbox)

## 1. Create Meta App

1. Go to https://developers.facebook.com/apps/
2. Click **Create App** → choose **Business** type
3. Add the **WhatsApp** product to your app

## 2. Get Credentials

In the WhatsApp section of your app dashboard:

1. **Phone Number ID**: Found under WhatsApp > API Setup
2. **Access Token**: Generate a temporary token (or use a System User token for production)
3. **Test Phone Number**: Meta provides a sandbox number, or add your own

Add to `.env`:
```env
WHATSAPP_ENABLED=true
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxx...
WHATSAPP_RECIPIENT_NUMBER=+1234567890
WHATSAPP_VERIFY_TOKEN=ai-employee-token
WEBHOOK_PORT=5001
```

## 3. Configure Webhook (for receiving replies)

### Option A: ngrok (for hackathon/testing)

```bash
# Terminal 1: Start the webhook server
uv run python -m utils.whatsapp_webhook

# Terminal 2: Expose via ngrok
ngrok http 5001
```

Copy the ngrok HTTPS URL (e.g., `https://abc123.ngrok-free.app`).

### Option B: Azure VM (production)

The webhook runs alongside the AI Employee on the VM. Open port 5001:
```bash
az vm open-port --resource-group ai-employee-rg --name ai-employee-vm --port 5001
```

### Register the Webhook

1. In Meta App Dashboard → WhatsApp → Configuration
2. Set **Callback URL**: `https://<your-url>/webhook`
3. Set **Verify Token**: `ai-employee-token` (must match `WHATSAPP_VERIFY_TOKEN`)
4. Subscribe to: `messages`

## 4. Test the Flow

1. Create a test file in `Pending_Approval/`:
```bash
echo "---
action: email_send
status: pending_approval
---
# Test Email
To: test@example.com
Subject: Hello" > AI_Employee_Vault/Pending_Approval/TEST_EMAIL.md
```

2. Run the scheduler (local zone):
```bash
ZONE=local WHATSAPP_ENABLED=true uv run python main.py --scheduler
```

3. You should receive a WhatsApp message:
```
AI Employee needs approval:

File: TEST_EMAIL.md
Action: email_send

Reply:
  APPROVE TEST_EMAIL.md
  REJECT TEST_EMAIL.md
```

4. Reply `APPROVE TEST_EMAIL.md` on WhatsApp

5. The webhook moves the file to `Approved/`, and the orchestrator executes it

## 5. DRY_RUN Mode

With `DRY_RUN=true`, WhatsApp messages are logged but not sent:
```
[DRY RUN] Would send WhatsApp: AI Employee needs approval...
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Regenerate the access token in Meta dashboard |
| Webhook verification fails | Check WHATSAPP_VERIFY_TOKEN matches your Meta config |
| No message received | Ensure recipient number is in WhatsApp sandbox allowed list |
| ngrok not working | Use `ngrok http 5001 --log=stdout` to debug |

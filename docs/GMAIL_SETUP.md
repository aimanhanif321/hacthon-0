# Gmail API Setup Guide

## Prerequisites
- A Google account
- Python 3.11+ with `uv` installed

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a Project** → **New Project**
3. Name it `ai-employee` and click **Create**
4. Make sure the new project is selected in the top bar

## Step 2: Enable the Gmail API

1. Go to **APIs & Services** → **Library**
2. Search for **Gmail API**
3. Click on it and press **Enable**

## Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** (or Internal if using Google Workspace)
3. Fill in:
   - App name: `AI Employee`
   - User support email: your email
   - Developer contact email: your email
4. Click **Save and Continue**
5. On **Scopes**, click **Add or Remove Scopes**
   - Add `https://www.googleapis.com/auth/gmail.readonly`
   - For email sending (MCP server), also add `https://www.googleapis.com/auth/gmail.send`
6. Click **Save and Continue**
7. Under **Test users**, add your Gmail address
8. Click **Save and Continue**

## Step 4: Create OAuth Client ID

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `AI Employee Desktop`
5. Click **Create**
6. Click **Download JSON** on the popup
7. Save the file as `credentials.json` in the project root

## Step 5: Configure Environment

Create a `.env` file in the project root:

```env
GMAIL_CREDENTIALS_PATH=./credentials.json
GMAIL_TOKEN_PATH=./token.json
```

## Step 6: First Run (Authentication)

```bash
uv run python -m watchers.gmail_watcher
```

This will:
1. Open a browser window for Google OAuth
2. Ask you to sign in and grant permissions
3. Save the token to `token.json` (auto-refreshes)
4. Start polling for emails

## How It Works

- Polls Gmail every 2 minutes (when used with scheduler)
- Finds unread emails
- Creates `EMAIL_<id>.md` action files in `/Needs_Action`
- Tracks processed message IDs to avoid duplicates (stored in `watchers/.gmail_processed_ids.json`)
- Classifies priority based on email subject and labels

## Security Notes

- `credentials.json` and `token.json` are in `.gitignore` — never commit them
- The watcher uses **read-only** scope; it cannot modify or send emails
- Processed IDs file keeps only the last 1000 entries

## Troubleshooting

- **"credentials.json not found"**: Download from Google Cloud Console → Credentials
- **"Token expired"**: Delete `token.json` and re-run to re-authenticate
- **"Access denied"**: Make sure your email is added as a test user in OAuth consent screen

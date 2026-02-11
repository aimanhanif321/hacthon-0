# LinkedIn API Setup Guide

## Prerequisites
- A LinkedIn account
- A LinkedIn Company Page (optional, for company posts)

## Step 1: Create a LinkedIn App

1. Go to [LinkedIn Developers](https://www.linkedin.com/developers/apps)
2. Click **Create App**
3. Fill in:
   - App name: `AI Employee`
   - LinkedIn Page: select your company page (or create one)
   - App logo: any image
   - Legal agreement: check the box
4. Click **Create App**

## Step 2: Request API Access

1. In your app settings, go to the **Products** tab
2. Request access to **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**
3. Wait for approval (usually instant for Share on LinkedIn)

## Step 3: Get OAuth 2.0 Credentials

1. Go to the **Auth** tab in your app
2. Note down:
   - **Client ID**
   - **Client Secret**
3. Under **OAuth 2.0 Scopes**, ensure you have:
   - `w_member_social` (for posting)
   - `openid` and `profile` (for authentication)

## Step 4: Generate Access Token

For development/testing, use the OAuth 2.0 Authorization Code flow:

1. Open this URL in your browser (replace `YOUR_CLIENT_ID`):
   ```
   https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8080/callback&scope=openid%20profile%20w_member_social
   ```

2. Authorize the app when prompted

3. You'll be redirected to `http://localhost:8080/callback?code=AUTHORIZATION_CODE`

4. Copy the `code` parameter and exchange it for an access token:
   ```bash
   curl -X POST https://www.linkedin.com/oauth/v2/accessToken \
     -d "grant_type=authorization_code" \
     -d "code=AUTHORIZATION_CODE" \
     -d "redirect_uri=http://localhost:8080/callback" \
     -d "client_id=YOUR_CLIENT_ID" \
     -d "client_secret=YOUR_CLIENT_SECRET"
   ```

5. Save the `access_token` from the response

## Step 5: Get Your Person URN

```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     "https://api.linkedin.com/v2/userinfo"
```

Your person URN is `urn:li:person:YOUR_SUB_ID`

## Step 6: Configure Environment

Add to your `.env` file:

```env
LINKEDIN_ACCESS_TOKEN=your_access_token_here
LINKEDIN_PERSON_URN=urn:li:person:your_id_here
DRY_RUN=true
```

**Important**: Set `DRY_RUN=true` for testing. Set to `false` when ready to post live.

## Step 7: Test

```bash
# Create a draft post (goes to Pending_Approval/)
uv run python -m skills.linkedin_poster

# Post an approved file (with DRY_RUN=true)
uv run python -m skills.linkedin_poster --post AI_Employee_Vault/Approved/LINKEDIN_POST_2026-02-10.md
```

## How It Works

1. **Draft Generation**: Claude generates post content based on `Business_Goals.md`
2. **Human Review**: Draft saved to `/Pending_Approval/LINKEDIN_POST_<date>.md`
3. **Approval**: Human moves file to `/Approved/` (or `/Rejected/`)
4. **Publishing**: Scheduler detects approved file and publishes via LinkedIn API

## Token Refresh

LinkedIn access tokens expire after 60 days. To refresh:
1. Generate a new token using Step 4 above
2. Update `LINKEDIN_ACCESS_TOKEN` in `.env`

## Security Notes

- Never commit `.env` or access tokens to git
- Use `DRY_RUN=true` during development
- LinkedIn rate limits: ~100 posts per day per member

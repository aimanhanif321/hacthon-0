# Twitter/X API Setup

This guide covers configuring the Twitter API v2 for posting tweets.

---

## 1. Create a Developer Account

1. Go to /https://developer.twitter.com and sign up / apply for a developer account
2. Create a **Project** and an **App** within it
3. Choose **Free** or **Basic** tier (Free tier allows 1,500 tweets/month)

## 2. Generate API Keys

In the Twitter Developer Portal:

1. Go to your App → **Keys and Tokens**
2. Generate and save:
   - **API Key** (Consumer Key)
   - **API Key Secret** (Consumer Secret)
   - **Access Token**
   - **Access Token Secret**
   - **Bearer Token**

Make sure your App has **Read and Write** permissions (not just Read).

## 3. Configure `.env`

```env
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
TWITTER_BEARER_TOKEN=your_bearer_token
```

## 4. Verify

```bash
# Test with DRY_RUN=true (no actual posting):
uv run python -m skills.twitter_poster

# Should create: AI_Employee_Vault/Pending_Approval/TWEET_<date>.md
```

---

## Notes

- Tweets are limited to 280 characters. The skill enforces this limit.
- Free tier: 1,500 tweets/month, 50 requests per 15-minute window.
- All tweets go through the human approval workflow before publishing.
- Uses `tweepy` library for Twitter API v2 access.

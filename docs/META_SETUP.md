# Meta (Facebook/Instagram) API Setup

This guide covers configuring the Meta Graph API for posting to Facebook Pages and Instagram.

---

## 1. Create a Meta Developer App

1. Go to https://developers.facebook.com/apps/ and click **Create App**
2. Choose **Business** type
3. Name it (e.g., `AI Employee Bot`) and click **Create**
4. In the App Dashboard, add the **Facebook Login** product

## 2. Configure Permissions

Your app needs these permissions:
- `pages_manage_posts` — Post to Facebook Pages
- `pages_read_engagement` — Read page insights
- `instagram_basic` — Basic Instagram access
- `instagram_content_publish` — Post to Instagram

## 3. Get a Page Access Token

1. Go to [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your App from the dropdown
3. Click **Generate Access Token**
4. Select permissions: `pages_manage_posts`, `pages_read_engagement`
5. Click **Generate** and authorize
6. From the token, exchange it for a **long-lived token**:
   ```bash
   uv run python scripts/meta_auth.py
   ```

## 4. Get Your Page ID

1. In Graph API Explorer, query: `GET /me/accounts`
2. Find your page in the response — the `id` field is your Page ID

## 5. Instagram Setup (Optional)

1. Your Facebook Page must be connected to an Instagram Business Account
2. Query: `GET /{page_id}?fields=instagram_business_account`
3. The `instagram_business_account.id` is your `META_INSTAGRAM_ACCOUNT_ID`

## 6. Configure `.env`

```env
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
META_ACCESS_TOKEN=your_long_lived_page_access_token
META_PAGE_ID=your_page_id
META_INSTAGRAM_ACCOUNT_ID=your_ig_business_account_id
```

## 7. Verify

```bash
# Test with DRY_RUN=true (no actual posting):
uv run python -m skills.meta_poster
uv run python -m skills.meta_poster facebook
uv run python -m skills.meta_poster instagram
# Should create: AI_Employee_Vault/Pending_Approval/FB_POST_<date>.md
```

---

## Notes

- Page Access Tokens expire after ~60 days. Re-run `scripts/meta_auth.py` to refresh.
- Instagram posting requires a public image URL — the image must be accessible from Meta's servers.
- All posts go through the human approval workflow (Pending_Approval → Approved → Published).

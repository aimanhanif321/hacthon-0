"""Just opens the properly-encoded LinkedIn auth URL in your browser."""
import os
import webbrowser
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
REDIRECT_URI = "http://localhost:9876/callback"

params = urlencode({
    "response_type": "code",
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "scope": "openid profile w_member_social",
    "state": "ai_employee_auth",
})

url = f"https://www.linkedin.com/oauth/v2/authorization?{params}"

print("Opening this URL:")
print(url)
print()
print("After you authorize, copy the FULL URL from the browser address bar")
print("and paste it back in your Claude Code chat.")

webbrowser.open(url)

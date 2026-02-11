"""
LinkedIn OAuth Helper - Automates the access token + person URN retrieval.

Usage:
    uv run python scripts/linkedin_auth.py

This script will:
1. Open your browser for LinkedIn authorization
2. Capture the callback with the auth code
3. Exchange it for an access token
4. Fetch your person URN
5. Print the values to add to your .env file
"""

import os
import sys
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import httpx
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_PORT = 9876
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SCOPES = "openid profile w_member_social"

# Will be set by the callback handler
auth_code = None
server_done = threading.Event()


class CallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect callback."""

    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Authorization successful!</h2>"
                b"<p>You can close this tab and go back to the terminal.</p>"
                b"</body></html>"
            )
            server_done.set()
        elif "error" in params:
            error = params.get("error", ["unknown"])[0]
            desc = params.get("error_description", [""])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>Error: {error}</h2><p>{desc}</p></body></html>".encode()
            )
            server_done.set()
        else:
            # Might be favicon or other request, keep listening
            self.send_response(200)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def run_server(server):
    """Keep serving until we get the auth code."""
    while not server_done.is_set():
        server.handle_request()


def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token."""
    response = httpx.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    return response.json()


def get_person_urn(access_token: str) -> str:
    """Fetch the user's person URN using the userinfo endpoint."""
    response = httpx.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    data = response.json()
    sub = data.get("sub")
    if sub:
        return f"urn:li:person:{sub}"
    return ""


def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in your .env file first.")
        print()
        print("Example .env:")
        print("  LINKEDIN_CLIENT_ID=774gezua0szema")
        print("  LINKEDIN_CLIENT_SECRET=WPL_AP1.xxxxx")
        sys.exit(1)

    print("=" * 60)
    print("  LinkedIn OAuth Setup")
    print("=" * 60)
    print()
    print(f"  Using redirect URI: {REDIRECT_URI}")
    print(f"  IMPORTANT: Add this EXACT URL to your LinkedIn app's")
    print(f"  Auth tab -> 'Authorized redirect URLs'")
    print()

    # Step 1: Start local server for callback
    try:
        server = HTTPServer(("127.0.0.1", REDIRECT_PORT), CallbackHandler)
    except OSError as e:
        print(f"ERROR: Cannot start server on port {REDIRECT_PORT}: {e}")
        print("       Close any other process using this port and retry.")
        sys.exit(1)

    server.timeout = 5  # 5s timeout per handle_request so we can check server_done
    server_thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    server_thread.start()

    # Step 2: Open browser for authorization
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES.replace(' ', '%20')}"
    )

    print("[1/4] Opening browser for LinkedIn authorization...")
    print()
    print(f"  If the browser doesn't open, paste this URL manually:")
    print(f"  {auth_url}")
    print()
    webbrowser.open(auth_url)

    # Step 3: Wait for callback
    print("[2/4] Waiting for you to authorize in the browser...")
    print("      (timeout: 3 minutes)")
    print()
    server_done.wait(timeout=180)
    server.server_close()

    if not auth_code:
        print("ERROR: No authorization code received.")
        print()
        print("Possible causes:")
        print(f"  1. Redirect URL not configured in LinkedIn app")
        print(f"     -> Add exactly: {REDIRECT_URI}")
        print(f"  2. You denied access or closed the browser")
        print(f"  3. LinkedIn showed an error page")
        sys.exit(1)

    print("      Authorization code received!")
    print()

    # Step 4: Exchange code for token
    print("[3/4] Exchanging code for access token...")
    token_data = exchange_code_for_token(auth_code)

    if "access_token" not in token_data:
        print(f"ERROR: Token exchange failed:")
        print(f"  {token_data}")
        sys.exit(1)

    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", "unknown")
    print(f"      Access token received! (expires in {expires_in}s)")
    print()

    # Step 5: Get person URN
    print("[4/4] Fetching your LinkedIn person URN...")
    person_urn = get_person_urn(access_token)

    if not person_urn:
        print("WARNING: Could not fetch person URN. You may need to add it manually.")
    else:
        print(f"      Person URN: {person_urn}")

    # Print results
    print()
    print("=" * 60)
    print("  SUCCESS! Add these to your .env file:")
    print("=" * 60)
    print()
    print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
    print(f"LINKEDIN_PERSON_URN={person_urn}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()

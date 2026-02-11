"""
Meta Auth Helper - Exchange short-lived token for long-lived Page Access Token.

Usage:
    uv run python scripts/meta_auth.py

Requires META_APP_ID, META_APP_SECRET, and a short-lived user access token.
"""

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

GRAPH_URL = "https://graph.facebook.com/v19.0"


def exchange_for_long_lived_token():
    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")

    if not app_id or not app_secret:
        print("Error: Set META_APP_ID and META_APP_SECRET in .env first.")
        sys.exit(1)

    short_token = input("Paste your short-lived User Access Token from Graph API Explorer:\n> ").strip()
    if not short_token:
        print("No token provided.")
        sys.exit(1)

    # Step 1: Exchange for long-lived user token
    print("\nExchanging for long-lived user token...")
    resp = httpx.get(f"{GRAPH_URL}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token,
    })
    data = resp.json()
    if "access_token" not in data:
        print(f"Error: {data}")
        sys.exit(1)

    long_user_token = data["access_token"]
    print(f"Long-lived user token obtained (expires in ~60 days)")

    # Step 2: Get page access tokens
    print("\nFetching page access tokens...")
    pages_resp = httpx.get(f"{GRAPH_URL}/me/accounts", params={
        "access_token": long_user_token,
    })
    pages_data = pages_resp.json()

    if "data" not in pages_data or not pages_data["data"]:
        print("No pages found. Make sure you have admin access to a Facebook Page.")
        sys.exit(1)

    print("\nYour Pages:")
    for i, page in enumerate(pages_data["data"]):
        print(f"  [{i}] {page['name']} (ID: {page['id']})")

    choice = input("\nEnter the number of the page to use: ").strip()
    try:
        page = pages_data["data"][int(choice)]
    except (ValueError, IndexError):
        print("Invalid choice.")
        sys.exit(1)

    print(f"\nAdd these to your .env file:")
    print(f"META_ACCESS_TOKEN={page['access_token']}")
    print(f"META_PAGE_ID={page['id']}")


if __name__ == "__main__":
    exchange_for_long_lived_token()

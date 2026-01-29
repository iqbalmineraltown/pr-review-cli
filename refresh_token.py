#!/usr/bin/env python3
"""
Refresh OAuth access token and update .env file
"""
import httpx
import asyncio
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

async def refresh_token():
    """Refresh access token using refresh token from .env"""

    # Config file location
    config_dir = Path.home() / ".pr-review-cli"
    env_file = config_dir / ".env"

    # Check if .env exists
    if not env_file.exists():
        print(f"❌ Error: .env file not found!")
        print(f"   Expected location: {env_file}")
        print("\nPlease run oauth_helper.py first to set up OAuth.")
        sys.exit(1)

    # Load current .env file
    load_dotenv(env_file)

    client_id = os.getenv("PR_REVIEWER_BITBUCKET_CLIENT_ID")
    client_secret = os.getenv("PR_REVIEWER_BITBUCKET_CLIENT_SECRET")
    refresh_token = os.getenv("PR_REVIEWER_BITBUCKET_REFRESH_TOKEN")
    username = os.getenv("PR_REVIEWER_BITBUCKET_USERNAME")

    if not all([client_id, client_secret, refresh_token]):
        print("❌ Error: Incomplete credentials in .env file!")
        print("Required fields:")
        print(f"  PR_REVIEWER_BITBUCKET_CLIENT_ID: {'✅' if client_id else '❌'}")
        print(f"  PR_REVIEWER_BITBUCKET_CLIENT_SECRET: {'✅' if client_secret else '❌'}")
        print(f"  PR_REVIEWER_BITBUCKET_REFRESH_TOKEN: {'✅' if refresh_token else '❌'}")
        sys.exit(1)

    print(f"📂 Loaded credentials from: {env_file}")
    print(f"🔄 Refreshing access token...")

    # Refresh the token
    auth = httpx.BasicAuth(client_id, client_secret)
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://bitbucket.org/site/oauth2/access_token",
            data=data,
            auth=auth,
            headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        new_tokens = response.json()

    # Build new .env content (preserving user config and comments)
    new_access_token = new_tokens.get("access_token")
    new_refresh_token = new_tokens.get("refresh_token", refresh_token)

    env_content = f"""# ═══════════════════════════════════════════════════════════════
# Bitbucket OAuth Configuration
# ═══════════════════════════════════════════════════════════════
#
# ⚠️  IMPORTANT NOTES:
#   • Fields marked [AUTO-POPULATED] are managed automatically
#   • DO NOT manually edit [AUTO-POPULATED] fields
#   • Token refresh will update these fields automatically
#
# ═══════════════════════════════════════════════════════════════

# ────────────────────────────────────────────────────────────────────────
# USER CONFIGURATION (Fill these in yourself)
# ────────────────────────────────────────────────────────────────────────

PR_REVIEWER_BITBUCKET_CLIENT_ID={client_id}
PR_REVIEWER_BITBUCKET_CLIENT_SECRET={client_secret}
PR_REVIEWER_BITBUCKET_USERNAME={username or 'your_username'}
PR_REVIEWER_BITBUCKET_WORKSPACE=iqbal2512

# ────────────────────────────────────────────────────────────────────────
# AUTOMATIC TOKENS (DO NOT EDIT - Managed by oauth_helper.py and refresh_token.py)
# ────────────────────────────────────────────────────────────────────────
# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}

# [AUTO-POPULATED] Access token (expires in 2 hours, auto-refreshed)
PR_REVIEWER_BITBUCKET_ACCESS_TOKEN={new_access_token}

# [AUTO-POPULATED] Refresh token (long-lived, used to get new access tokens)
PR_REVIEWER_BITBUCKET_REFRESH_TOKEN={new_refresh_token}
"""

    # Save updated .env
    with open(env_file, 'w') as f:
        f.write(env_content)

    # Set secure permissions
    os.chmod(env_file, 0o600)

    print(f"\n✅ Access token refreshed successfully!")
    print(f"\nNew access token: {new_access_token[:50]}...")
    print(f"Token length: {len(new_access_token)} characters")
    print(f"\n✅ Updated: {env_file}")
    print(f"🔒 Permissions set to 600")
    print(f"\n🚀 You can now run the CLI without any changes!")

if __name__ == "__main__":
    asyncio.run(refresh_token())

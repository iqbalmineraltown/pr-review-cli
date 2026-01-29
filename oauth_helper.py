#!/usr/bin/env python3
"""
Bitbucket OAuth Authorization Helper for PR Review CLI
Helps you authorize and get your refresh token
"""

import httpx
import asyncio
import webbrowser
from urllib.parse import urlencode
from typing import Optional

class BitbucketOAuthHelper:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = "http://localhost:3000/callback"
        self.base_url = "https://bitbucket.org"

    def get_authorization_url(self) -> str:
        """Generate the authorization URL"""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "account pullrequest repository"  # Try without read: prefix
        }
        return f"{self.base_url}/site/oauth2/authorize?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for access and refresh tokens"""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
        }

        # Use Basic Auth for this step
        auth = httpx.BasicAuth(self.client_id, self.client_secret)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/site/oauth2/access_token",
                data=data,
                auth=auth,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token"""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        auth = httpx.BasicAuth(self.client_id, self.client_secret)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/site/oauth2/access_token",
                data=data,
                auth=auth,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()
            return response.json()


async def authorize_with_callback_server(client_id: str, client_secret: str, port: int = 3000):
    """
    Start a local server to handle OAuth callback
    """
    from aiohttp import web

    oauth_helper = BitbucketOAuthHelper(client_id, client_secret)
    auth_code = None

    async def handle_callback(request):
        nonlocal auth_code
        # Extract the authorization code from the callback
        code = request.query.get('code')
        if code:
            auth_code = code
            # Return a success page
            return web.Response(text="""
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Successful</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 40px;
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .success {
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 { margin: 0 0 20px; }
        p { font-size: 18px; line-height: 1.6; }
        .checkmark {
            font-size: 60px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="success">
        <div class="checkmark">✅</div>
        <h1>Authorization Successful!</h1>
        <p>You can close this window and return to the terminal.</p>
        <p>Your tokens are being retrieved...</p>
    </div>
</body>
</html>
            """)
        else:
            return web.Response(text="Authorization failed or was cancelled")

    app = web.Application()
    app.router.add_get('/callback', handle_callback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()

    print(f"\n✅ Callback server started on http://localhost:{port}")
    print(f"Waiting for authorization...\n")

    # Open browser for authorization
    auth_url = oauth_helper.get_authorization_url()
    print(f"🌐 Opening browser for authorization...")
    print(f"   If it doesn't open, visit this URL:\n")
    print(f"   {auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for callback (with timeout)
    timeout = 120  # 2 minutes
    for _ in range(timeout * 10):  # Check every 0.1 seconds
        await asyncio.sleep(0.1)
        if auth_code:
            break

    await runner.cleanup()

    if not auth_code:
        raise RuntimeError("Authorization timed out. Please try again.")

    print(f"✅ Authorization code received!")

    # Exchange code for tokens
    print(f"🔄 Exchanging code for tokens...")
    tokens = await oauth_helper.exchange_code_for_tokens(auth_code)

    return tokens


def main():
    import sys

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     Bitbucket OAuth Authorization Helper for PR Review CLI    ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    if len(sys.argv) < 3:
        print("Usage: python3 oauth_helper.py <CLIENT_ID> <CLIENT_SECRET>\n")
        print("You can find these in your Bitbucket OAuth Consumer settings:")
        print("  https://bitbucket.org/workspace/settings/api-tokens/\n")
        sys.exit(1)

    client_id = sys.argv[1]
    client_secret = sys.argv[2]

    async def run():
        try:
            tokens = await authorize_with_callback_server(client_id, client_secret)

            print(f"\n{'='*60}")
            print(f"✅ SUCCESS! Your OAuth tokens:")
            print(f"{'='*60}\n")

            print(f"Client ID: {client_id}")
            print(f"\nAccess Token (expires in ~2 hours):")
            print(f"  {tokens.get('access_token', 'N/A')[:50]}...")
            print(f"\nRefresh Token (long-lived):")
            print(f"  {tokens.get('refresh_token', 'N/A')}")
            print(f"\nScopes: {tokens.get('scopes', [])}")
            print(f"\nExpires in: {tokens.get('expires_in', 3600)} seconds\n")

            # Fetch user info to get UUID and username
            print(f"🔍 Fetching your user information...")
            import httpx
            user_info = None

            try:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(
                        "https://api.bitbucket.org/2.0/user",
                        headers={"Authorization": f"Bearer {tokens.get('access_token')}"}
                    )
                    if response.status_code == 200:
                        user_data = response.json()
                        user_uuid = user_data.get("uuid", "").replace("{", "").replace("}", "")
                        user_username = user_data.get("username", "")
                        user_display_name = user_data.get("display_name", "")

                        user_info = {
                            "uuid": user_uuid,
                            "username": user_username,
                            "display_name": user_display_name
                        }

                        print(f"✅ User info retrieved:")
                        print(f"   Username: {user_username}")
                        print(f"   Display Name: {user_display_name}")
                        print(f"   UUID: {user_uuid}\n")
                    else:
                        print(f"⚠️  Could not fetch user info (status: {response.status_code})")
                        print(f"   You may need to add UUID manually to .env file\n")
            except Exception as e:
                print(f"⚠️  Could not fetch user info: {e}")
                print(f"   You may need to add UUID manually to .env file\n")

            print(f"{'='*60}")
            print(f"💾 CREDENTIALS SAVED TO .env FILE")
            print(f"{'='*60}\n")

            # Save to .env file
            from pathlib import Path

            config_dir = Path.home() / ".pr-review-cli"
            config_dir.mkdir(parents=True, exist_ok=True)
            env_file = config_dir / ".env"

            # Try to read existing .env to preserve workspace
            existing_workspace = ""
            if env_file.exists():
                from dotenv import dotenv_values
                existing_env = dotenv_values(env_file)
                existing_workspace = existing_env.get("PR_REVIEWER_BITBUCKET_WORKSPACE", "")

            # Determine workspace (use username from user info as default)
            saved_workspace = existing_workspace if existing_workspace else (user_info["username"] if user_info else "YOUR_WORKSPACE")

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
PR_REVIEWER_BITBUCKET_WORKSPACE={saved_workspace}

# ────────────────────────────────────────────────────────────────────────
# AUTOMATIC TOKENS (DO NOT EDIT - Managed by oauth_helper.py and refresh_token.py)
# ────────────────────────────────────────────────────────────────────────

# [AUTO-POPULATED] Access token (expires in 2 hours, auto-refreshed)
PR_REVIEWER_BITBUCKET_ACCESS_TOKEN={tokens.get('access_token')}

# [AUTO-POPULATED] Refresh token (long-lived, used to get new access tokens)
PR_REVIEWER_BITBUCKET_REFRESH_TOKEN={tokens.get('refresh_token')}
"""

            # Add UUID if we have it
            if user_info and user_info["uuid"]:
                env_content += f"""
# [AUTO-POPULATED] User UUID (retrieved from Bitbucket API)
# Used for accurate participant matching in PR reviews
PR_REVIEWER_BITBUCKET_USER_UUID={user_info["uuid"]}
"""

            with open(env_file, 'w') as f:
                f.write(env_content)

            print(f"✅ Credentials saved to: {env_file}")
            print(f"   The CLI will automatically load these credentials.")
            print(f"   No environment variables needed!\n")

            # Set secure permissions
            import os
            os.chmod(env_file, 0o600)
            print(f"🔒 File permissions set to 600 (read/write for owner only)\n")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()

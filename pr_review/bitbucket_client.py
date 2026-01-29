import httpx
import asyncio
from typing import List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
import time
from .models import BitbucketPR, PRDiff, UserInfo
from .config import Config


class BitbucketClient:
    """Client for interacting with Bitbucket API with OAuth token refresh support"""

    def __init__(
        self,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None
    ):
        self.access_token = access_token
        self.username = username
        self.base_url = base_url or "https://api.bitbucket.org/2.0"

        # OAuth credentials
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

        # Token expiration tracking
        self.token_expires_at = None

        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the Bitbucket API with token refresh on 401"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(endpoint, params=params)

        # If we get a 401 and have OAuth credentials, try to refresh
        if response.status_code == 401 and self._can_refresh_token():
            await self._refresh_access_token()
            # Retry the request with new token
            response = await self._client.get(endpoint, params=params)

        response.raise_for_status()
        return response.json()

    async def _get_raw(self, endpoint: str, params: Optional[dict] = None) -> str:
        """Make a GET request that returns raw text (not JSON)"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(endpoint, params=params)

        # If we get a 401 and have OAuth credentials, try to refresh
        if response.status_code == 401 and self._can_refresh_token():
            await self._refresh_access_token()
            # Retry the request with new token
            response = await self._client.get(endpoint, params=params)

        response.raise_for_status()
        return response.text

    def _can_refresh_token(self) -> bool:
        """Check if we can refresh the access token"""
        return all([
            self.client_id,
            self.client_secret,
            self.refresh_token
        ])

    async def _refresh_access_token(self):
        """Refresh the access token using the refresh token"""
        if not self._can_refresh_token():
            raise RuntimeError("Cannot refresh token: OAuth credentials not configured")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
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
            tokens = response.json()

        # Update tokens
        self.access_token = tokens.get("access_token", self.access_token)
        self.refresh_token = tokens.get("refresh_token", self.refresh_token)

        # Update expiration
        expires_in = tokens.get("expires_in", 3600)
        self.token_expires_at = time.time() + expires_in

        # Update client headers
        self.headers["Authorization"] = f"Bearer {self.access_token}"
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {self.access_token}"

        # Save updated tokens to cache
        self._save_tokens_to_cache(tokens)

        print("  [dim]🔄 Token refreshed[/dim]")

    def _save_tokens_to_cache(self, tokens: dict):
        """Save updated tokens to .env file with proper formatting"""
        env_file = Path.home() / ".pr-review-cli" / ".env"

        try:
            # Read existing .env to preserve user settings
            existing_env = {}
            if env_file.exists():
                from dotenv import dotenv_values
                existing_env = dotenv_values(env_file)

            # Update token values
            new_access_token = tokens.get("access_token", self.access_token)
            new_refresh_token = self.refresh_token

            # Build new .env content (with clear sections and warnings)
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

"""

            # User configuration (preserve existing values)
            if self.client_id:
                env_content += f"PR_REVIEWER_BITBUCKET_CLIENT_ID={self.client_id}\n"
            elif existing_env.get("PR_REVIEWER_BITBUCKET_CLIENT_ID"):
                env_content += f"PR_REVIEWER_BITBUCKET_CLIENT_ID={existing_env.get('PR_REVIEWER_BITBUCKET_CLIENT_ID')}\n"

            if self.client_secret:
                env_content += f"PR_REVIEWER_BITBUCKET_CLIENT_SECRET={self.client_secret}\n"
            elif existing_env.get("PR_REVIEWER_BITBUCKET_CLIENT_SECRET"):
                env_content += f"PR_REVIEWER_BITBUCKET_CLIENT_SECRET={existing_env.get('PR_REVIEWER_BITBUCKET_CLIENT_SECRET')}\n"

            if self.username:
                env_content += f"PR_REVIEWER_BITBUCKET_USERNAME={self.username}\n"
            elif existing_env.get("PR_REVIEWER_BITBUCKET_USERNAME"):
                env_content += f"PR_REVIEWER_BITBUCKET_USERNAME={existing_env.get('PR_REVIEWER_BITBUCKET_USERNAME')}\n"

            if existing_env.get("PR_REVIEWER_BITBUCKET_WORKSPACE"):
                env_content += f"PR_REVIEWER_BITBUCKET_WORKSPACE={existing_env.get('PR_REVIEWER_BITBUCKET_WORKSPACE')}\n"

            # Automatic tokens section
            env_content += f"""
# ────────────────────────────────────────────────────────────────────────
# AUTOMATIC TOKENS (DO NOT EDIT - Managed by oauth_helper.py and refresh_token.py)
# ────────────────────────────────────────────────────────────────────────
# Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')} (auto-refreshed)

# [AUTO-POPULATED] Access token (expires in 2 hours, auto-refreshed)
PR_REVIEWER_BITBUCKET_ACCESS_TOKEN={new_access_token}

# [AUTO-POPULATED] Refresh token (long-lived, used to get new access tokens)
PR_REVIEWER_BITBUCKET_REFRESH_TOKEN={new_refresh_token}
"""

            # Add any other existing env vars (optional config)
            optional_vars = []
            for key, value in existing_env.items():
                if key not in [
                    "PR_REVIEWER_BITBUCKET_CLIENT_ID",
                    "PR_REVIEWER_BITBUCKET_CLIENT_SECRET",
                    "PR_REVIEWER_BITBUCKET_ACCESS_TOKEN",
                    "PR_REVIEWER_BITBUCKET_REFRESH_TOKEN",
                    "PR_REVIEWER_BITBUCKET_USERNAME",
                    "PR_REVIEWER_BITBUCKET_WORKSPACE"
                ]:
                    optional_vars.append(f"{key}={value}")

            if optional_vars:
                env_content += "\n# ═══════════════════════════════════════════════════════════════\n"
                env_content += "# OPTIONAL CONFIGURATION\n"
                env_content += "# ═══════════════════════════════════════════════════════════════\n\n"
                env_content += "\n".join(optional_vars) + "\n"

            # Write to .env file
            with open(env_file, 'w') as f:
                f.write(env_content)

            # Set secure permissions
            import os
            os.chmod(env_file, 0o600)

        except Exception as e:
            # Don't fail if we can't update .env
            pass

    async def get_current_user(self) -> UserInfo:
        """Get the currently authenticated user's info"""
        try:
            response = await self._client.get("/user")

            # Check for 401/403 - token may not have account:read scope
            if response.status_code in [401, 403]:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get('error', {}).get('message', '')

                if 'invalid' in error_msg.lower() or 'expired' in error_msg.lower():
                    raise RuntimeError(f"token_invalid_or_expired:{error_msg}")
                else:
                    raise RuntimeError("user_endpoint_not_accessible")

            response.raise_for_status()
            data = response.json()
            return UserInfo(
                uuid=data.get("uuid", "").replace("{", "").replace("}", ""),
                username=data.get("username", ""),
                display_name=data.get("display_name", "")
            )
        except RuntimeError as e:
            if "user_endpoint_not_accessible" in str(e):
                raise
            if "token_invalid_or_expired" in str(e):
                raise
            raise
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            if e.response.status_code == 401:
                raise RuntimeError("token_invalid_or_expired:Unauthorized")
            if e.response.status_code == 403:
                raise RuntimeError("user_endpoint_not_accessible")
            raise RuntimeError(f"HTTP error getting user info: {error_msg}")
        except Exception as e:
            raise RuntimeError(f"Failed to get user info: {e}")

    async def fetch_prs_assigned_to_me(
        self,
        workspace: str,
        repo_slug: Optional[str] = None,
        user_uuid: Optional[str] = None,
        user_username: Optional[str] = None,
        state: str = "OPEN"
    ) -> List[BitbucketPR]:
        """
        Fetch PRs where the current user is listed as a reviewer.

        Automatically filters out PRs where the user has already responded
        (approved or declined) to keep the review queue focused on pending work.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug/name (optional - if not specified, searches all repos in workspace)
            user_uuid: Current user's UUID (without braces) - preferred if available
            user_username: Current user's username - fallback if UUID not available
            state: PR state filter (default: OPEN)

        Returns:
            List of BitbucketPR objects that the user has NOT yet responded to
        """
        # Build query to filter by reviewer
        # Prefer UUID search, fallback to username
        if user_uuid:
            query = f'reviewers.uuid="{user_uuid}"'
        elif user_username:
            query = f'reviewers.username="{user_username}"'
        else:
            raise ValueError("Either user_uuid or user_username must be provided")

        # Build query parameters
        params = {"state": state, "q": query}

        # Add fields parameter to get participant data
        # Bitbucket API list endpoint doesn't include participants by default
        # We need to explicitly request them with the fields parameter
        params["fields"] = "values.*,values.participants.*"

        try:
            if repo_slug:
                # Search specific repository
                data = await self._get(
                    f"/repositories/{workspace}/{repo_slug}/pullrequests",
                    params=params
                )
            else:
                # Search all repositories in workspace
                # Note: Bitbucket API doesn't support workspace-wide PR search
                # So we need to fetch repositories first, then search each one
                all_prs = []

                # Get all repositories in workspace (paginated)
                repos_data = await self._get(f"/repositories/{workspace}")
                repositories = repos_data.get("values", [])

                # Search for PRs in each repository
                for repo in repositories:
                    repo_slug_from_api = repo.get("slug")
                    if not repo_slug_from_api:
                        continue

                    try:
                        repo_prs_data = await self._get(
                            f"/repositories/{workspace}/{repo_slug_from_api}/pullrequests",
                            params=params
                        )
                        repo_prs = repo_prs_data.get("values", [])

                        # Add repository info to each PR (API doesn't include it when fetching from repo endpoint)
                        for pr in repo_prs:
                            pr["repository"] = repo

                        all_prs.extend(repo_prs)
                    except httpx.HTTPStatusError as e:
                        # Skip repos we can't access (permissions, etc.)
                        if e.response.status_code != 403 and e.response.status_code != 404:
                            raise
                        continue

                # Return combined results in same format
                data = {"values": all_prs}

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                if repo_slug:
                    raise RuntimeError(
                        f"Repository not found: {workspace}/{repo_slug}\n"
                        "Please check the workspace and repository name."
                    )
                else:
                    raise RuntimeError(
                        f"Workspace not found: {workspace}\n"
                        "Please check the workspace name."
                    )
            elif e.response.status_code == 401:
                raise RuntimeError(
                    "Authentication failed. Please check your OAuth credentials.\n"
                    "Try running the oauth_helper.py again to get new tokens."
                )
            else:
                raise

        prs = []
        for pr_data in data.get("values", []):
            pr_id = pr_data.get("id", "")
            pr_state = pr_data.get("state", "")

            # Filter out PRs that are not open (declined, closed, merged)
            # Note: Even though we query state="OPEN", Bitbucket sometimes returns PRs in other states
            if pr_state.lower() not in ["open", "opened"]:
                print(f"\n[DEBUG] PR #{pr_id}: {pr_data.get('title', '')[:50]}")
                print(f"[DEBUG] PR state is '{pr_state}' - filtering out")
                continue

            # Check if user has already responded to this PR (approved or requested changes)
            participants = pr_data.get("participants", [])
            user_has_responded = False

            # Get user identifier for response check
            user_identifier = user_uuid if user_uuid else user_username

            # Debug: Log what we're looking for
            print(f"[DEBUG] Looking for user - UUID: {user_uuid}, Username: {user_username}")
            print(f"[DEBUG] Participants: {len(participants)} found")

            if user_identifier:
                for participant in participants:
                    # Check if this participant is the current user
                    participant_uuid = participant.get("user", {}).get("uuid", "").replace("{", "").replace("}", "")
                    participant_username = participant.get("user", {}).get("username", "")
                    participant_nickname = participant.get("user", {}).get("nickname", "")
                    participant_display_name = participant.get("user", {}).get("display_name", "")
                    participant_approved = participant.get("approved", False)
                    participant_status = participant.get("status", "")

                    # Debug: Show each participant
                    print(f"[DEBUG]   - Participant: username='{participant_username}' nickname='{participant_nickname}' (UUID: {participant_uuid[:8] if participant_uuid else 'None'}...) - Approved: {participant_approved}, Status: {participant_status}")

                    # Match by UUID or username
                    # Note: Bitbucket API sometimes returns empty username, so fallback to nickname
                    is_current_user = (
                        (user_uuid and participant_uuid == user_uuid) or
                        (user_username and participant_username == user_username) or
                        (user_username and not participant_username and participant_nickname == user_username)
                    )

                    if is_current_user:
                        print(f"[DEBUG]   ✓ MATCH FOUND for current user!")
                        # Check if user has approved
                        if participant_approved:
                            print(f"[DEBUG]   → User has APPROVED - filtering out")
                            user_has_responded = True
                            break

                        # Check for declined/changes requested status
                        # Bitbucket API: status can be "approved", "declined", "changes_requested", etc.
                        participant_status_lower = participant_status.lower()
                        if participant_status_lower in ["declined", "changes_requested"]:
                            print(f"[DEBUG]   → User has status '{participant_status}' - filtering out")
                            user_has_responded = True
                            break
                        else:
                            print(f"[DEBUG]   → User hasn't responded yet - keeping")

            # Skip PRs where user has already responded
            if user_has_responded:
                continue

            # PR passed all filters - log and include it
            print(f"\n[DEBUG] PR #{pr_id}: {pr_data.get('title', '')[:50]}")
            print(f"[DEBUG] PASSED all filters - including in review queue")

            author_data = pr_data.get("author", {})
            author = author_data.get("nickname", author_data.get("display_name", "Unknown"))

            links = pr_data.get("links", {})
            html_link = links.get("html", {}).get("href", "")

            # Extract repository information from the PR data
            # When searching across workspace, each PR includes repo info
            pr_repo_slug = pr_data.get("repository", {}).get("slug", repo_slug or "unknown")

            pr = BitbucketPR(
                id=str(pr_data.get("id", "")),
                title=pr_data.get("title", ""),
                description=pr_data.get("description", ""),
                author=author,
                source_branch=pr_data.get("source", {}).get("branch", {}).get("name", ""),
                destination_branch=pr_data.get("destination", {}).get("branch", {}).get("name", ""),
                created_on=datetime.fromisoformat(
                    pr_data.get("created_on", "").replace("Z", "+00:00")
                ),
                updated_on=datetime.fromisoformat(
                    pr_data.get("updated_on", "").replace("Z", "+00:00")
                ),
                link=html_link,
                state=pr_data.get("state", ""),
                workspace=workspace,
                repo_slug=pr_repo_slug
            )
            prs.append(pr)

        return prs

    async def get_single_pr(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: str
    ) -> BitbucketPR:
        """
        Fetch a single PR by ID.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug/name
            pr_id: Pull request ID

        Returns:
            BitbucketPR object
        """
        try:
            pr_data = await self._get(
                f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise RuntimeError(
                    f"PR not found: {workspace}/{repo_slug}/#{pr_id}\n"
                    "Please check the URL and verify the PR exists."
                )
            elif e.response.status_code == 401:
                raise RuntimeError(
                    "Authentication failed. Please check your OAuth credentials.\n"
                    "Try running the oauth_helper.py again to get new tokens."
                )
            else:
                raise RuntimeError(f"Failed to fetch PR: {e}")

        author_data = pr_data.get("author", {})
        author = author_data.get("nickname", author_data.get("display_name", "Unknown"))

        links = pr_data.get("links", {})
        html_link = links.get("html", {}).get("href", "")

        pr = BitbucketPR(
            id=str(pr_data.get("id", "")),
            title=pr_data.get("title", ""),
            description=pr_data.get("description", ""),
            author=author,
            source_branch=pr_data.get("source", {}).get("branch", {}).get("name", ""),
            destination_branch=pr_data.get("destination", {}).get("branch", {}).get("name", ""),
            created_on=datetime.fromisoformat(
                pr_data.get("created_on", "").replace("Z", "+00:00")
            ),
            updated_on=datetime.fromisoformat(
                pr_data.get("updated_on", "").replace("Z", "+00:00")
            ),
            link=html_link,
            state=pr_data.get("state", ""),
            workspace=workspace,
            repo_slug=repo_slug
        )

        return pr

    async def get_pr_diff(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: str
    ) -> PRDiff:
        """
        Get the diff for a specific PR.

        Returns:
            PRDiff object with diff content and statistics
        """
        try:
            diff_text = await self._get_raw(
                f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                # Diff too large, return partial info
                return PRDiff(
                    pr_id=pr_id,
                    files_changed=[],
                    additions=0,
                    deletions=0,
                    diff_content=""
                )
            raise

        # The API returns diff as raw text
        if isinstance(diff_text, str):
            diff_content = diff_text
        else:
            diff_content = str(diff_text)

        # Parse diff to extract statistics
        files_changed = []
        additions = 0
        deletions = 0

        lines = diff_content.split('\n')
        for line in lines:
            if line.startswith('diff --git'):
                # Extract file path
                parts = line.split()
                if len(parts) >= 4:
                    files_changed.append(parts[3].lstrip('b/'))
            elif line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1

        return PRDiff(
            pr_id=pr_id,
            files_changed=files_changed,
            additions=additions,
            deletions=deletions,
            diff_content=diff_content
        )

    async def fetch_prs_and_diffs(
        self,
        workspace: str,
        repo_slug: Optional[str],
        user_uuid: Optional[str] = None,
        user_username: Optional[str] = None
    ) -> Tuple[List[BitbucketPR], List[PRDiff]]:
        """
        Fetch both PRs and their diffs in parallel.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug/name (optional - if not specified, searches all repos)
            user_uuid: Current user's UUID (optional)
            user_username: Current user's username (optional, used as fallback)

        Returns:
            Tuple of (prs, diffs)
        """
        prs = await self.fetch_prs_assigned_to_me(workspace, repo_slug, user_uuid, user_username)

        if not prs:
            return [], []

        # Fetch diffs in parallel
        # Each PR may be from a different repo, so use the PR's repo_slug
        tasks = [
            self.get_pr_diff(pr.workspace, pr.repo_slug, pr.id)
            for pr in prs
        ]
        diffs = await asyncio.gather(*tasks)

        return prs, diffs

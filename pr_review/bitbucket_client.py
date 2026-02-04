import httpx
import asyncio
from typing import List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json
import time
from .models import BitbucketPR, PRDiff, UserInfo, InlineComment
from .config import Config


class BitbucketClient:
    """Client for interacting with Bitbucket API using API Token authentication"""

    def __init__(
        self,
        email: str,
        api_token: str,
        base_url: Optional[str] = None
    ):
        self.email = email
        self.api_token = api_token
        self.base_url = base_url or "https://api.bitbucket.org/2.0"

        # Set up Basic authentication headers
        import base64
        auth_string = f"{email}:{api_token}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {auth_b64}"
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
        """Make a GET request to the Bitbucket API"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()

    async def _get_raw(self, endpoint: str, params: Optional[dict] = None) -> str:
        """Make a GET request that returns raw text (not JSON)"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(endpoint, params=params)
        response.raise_for_status()
        return response.text

    async def _post(self, endpoint: str, data: dict) -> dict:
        """Make a POST request to the Bitbucket API"""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.post(endpoint, json=data)
        response.raise_for_status()
        return response.json()

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

                # Get all repositories in workspace (with proper pagination)
                repositories = []
                next_url = f"/repositories/{workspace}"
                page_count = 0

                while next_url:
                    page_count += 1
                    repos_data = await self._get(next_url)
                    page_values = repos_data.get("values", [])
                    repositories.extend(page_values)

                    # Bitbucket API uses page/pagelen/size for pagination
                    if "page" in repos_data:
                        page = repos_data.get("page")
                        pagelen = repos_data.get("pagelen")
                        size = repos_data.get("size")

                        if page and pagelen and size:
                            if page * pagelen < size:
                                # Calculate next page
                                next_page = page + 1
                                next_url = f"/repositories/{workspace}?page={next_page}&pagelen={pagelen}"
                            else:
                                # Last page reached
                                next_url = None
                        else:
                            # No more pages
                            next_url = None
                    else:
                        # Fallback: check for links.next (older API format)
                        if "next" in repos_data.get("links", {}):
                            next_link = repos_data["links"]["next"].get("href", "")
                            if next_link:
                                if next_link.startswith("http"):
                                    from urllib.parse import urlparse
                                    parsed = urlparse(next_link)
                                    next_url = parsed.path
                                    if parsed.query:
                                        next_url = f"{next_url}?{parsed.query}"
                                else:
                                    next_url = next_link
                            else:
                                next_url = None
                        else:
                            # No more pages
                            next_url = None

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
                    "Authentication failed. Please check your API Token credentials.\n"
                    "Verify PR_REVIEWER_BITBUCKET_EMAIL and PR_REVIEWER_BITBUCKET_API_TOKEN in ~/.pr-review-cli/.env"
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
                continue

            # Check if user has already responded to this PR (approved or requested changes)
            participants = pr_data.get("participants", [])
            user_has_responded = False

            # Get user identifier for response check
            user_identifier = user_uuid if user_uuid else user_username

            if user_identifier:
                for participant in participants:
                    # Check if this participant is the current user
                    participant_uuid = participant.get("user", {}).get("uuid", "").replace("{", "").replace("}", "")
                    participant_username = participant.get("user", {}).get("username", "")
                    participant_nickname = participant.get("user", {}).get("nickname", "")
                    participant_approved = participant.get("approved", False)
                    participant_status = participant.get("status", "")

                    # Match by UUID or username
                    # Note: Bitbucket API sometimes returns empty username, so fallback to nickname
                    is_current_user = (
                        (user_uuid and participant_uuid == user_uuid) or
                        (user_username and participant_username == user_username) or
                        (user_username and not participant_username and participant_nickname == user_username)
                    )

                    if is_current_user:
                        # Check if user has approved
                        if participant_approved:
                            user_has_responded = True
                            break

                        # Check for declined/changes requested status
                        # Bitbucket API: status can be "approved", "declined", "changes_requested", etc.
                        participant_status_lower = participant_status.lower()
                        if participant_status_lower in ["declined", "changes_requested"]:
                            user_has_responded = True
                            break

            # Skip PRs where user has already responded
            if user_has_responded:
                continue

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
                    "Authentication failed. Please check your API Token credentials.\n"
                    "Verify PR_REVIEWER_BITBUCKET_EMAIL and PR_REVIEWER_BITBUCKET_API_TOKEN in ~/.pr-review-cli/.env"
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

    async def post_pr_comment(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: str,
        content: str,
        max_retries: int = 3
    ) -> dict:
        """
        Post a markdown comment to a PR with retry logic.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug/name
            pr_id: Pull request ID
            content: Markdown content for the comment
            max_retries: Maximum number of retry attempts for transient errors

        Returns:
            Response data from Bitbucket API containing comment details

        Raises:
            RuntimeError: If posting fails after all retries
        """
        endpoint = f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
        payload = {
            "content": {
                "raw": content
            }
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                return await self._post(endpoint, payload)
            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code

                # Don't retry client errors (4xx)
                if 400 <= status < 500:
                    if status == 401:
                        raise RuntimeError(
                            "Authentication failed. Please check your API Token credentials.\n"
                            "Verify PR_REVIEWER_BITBUCKET_EMAIL and PR_REVIEWER_BITBUCKET_API_TOKEN in ~/.pr-review-cli/.env"
                        )
                    elif status == 403:
                        raise RuntimeError(
                            f"Permission denied posting comment to {workspace}/{repo_slug}/#{pr_id}.\n"
                            "Your API Token may not have write permissions."
                        )
                    elif status == 404:
                        raise RuntimeError(
                            f"PR not found: {workspace}/{repo_slug}/#{pr_id}\n"
                            "It may have been deleted or you don't have access."
                        )
                    else:
                        raise RuntimeError(f"Failed to post comment (HTTP {status}): {e}")

                # Retry server errors (5xx) with exponential backoff
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                # Retry network issues with exponential backoff
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        # All retries exhausted
        raise RuntimeError(f"Failed to post comment after {max_retries} attempts: {last_error}")

    async def post_inline_comment(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: str,
        content: str,
        file_path: str,
        line_number: int,
        max_retries: int = 3
    ) -> dict:
        """
        Post an inline comment to a specific line in a PR.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug/name
            pr_id: Pull request ID
            content: Comment content (markdown)
            file_path: Path to the file in the repo
            line_number: Line number in the NEW version (the "to" line)
            max_retries: Maximum number of retry attempts

        Returns:
            Response data from Bitbucket API containing comment details

        Raises:
            RuntimeError: If posting fails after all retries
        """
        endpoint = f"/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
        payload = {
            "content": {
                "raw": content
            },
            "inline": {
                "to": line_number,
                "path": file_path
            }
        }

        last_error = None
        for attempt in range(max_retries):
            try:
                return await self._post(endpoint, payload)
            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code

                # Don't retry client errors (4xx)
                if 400 <= status < 500:
                    if status == 401:
                        raise RuntimeError(
                            "Authentication failed. Please check your API Token credentials.\n"
                            "Verify PR_REVIEWER_BITBUCKET_EMAIL and PR_REVIEWER_BITBUCKET_API_TOKEN in ~/.pr-review-cli/.env"
                        )
                    elif status == 403:
                        raise RuntimeError(
                            f"Permission denied posting inline comment to {workspace}/{repo_slug}/#{pr_id}.\n"
                            "Your API Token may not have write permissions."
                        )
                    elif status == 404:
                        raise RuntimeError(
                            f"PR not found: {workspace}/{repo_slug}/#{pr_id}\n"
                            "It may have been deleted or you don't have access."
                        )
                    elif status == 400:
                        # Likely invalid line number or file path
                        raise RuntimeError(
                            f"Invalid inline comment parameters for {workspace}/{repo_slug}/#{pr_id}.\n"
                            f"File: {file_path}, Line: {line_number}\n"
                            f"The line may not exist in the diff."
                        )
                    else:
                        raise RuntimeError(f"Failed to post inline comment (HTTP {status}): {e}")

                # Retry server errors (5xx) with exponential backoff
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                # Retry network issues with exponential backoff
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        # All retries exhausted
        raise RuntimeError(f"Failed to post inline comment after {max_retries} attempts: {last_error}")

    async def post_inline_comments_batch(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: str,
        comments: list[InlineComment],
        delay_between: float = 0.5,
        max_comments: int = 50
    ) -> list[dict]:
        """
        Post multiple inline comments with rate limiting.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug/name
            pr_id: Pull request ID
            comments: List of InlineComment objects to post
            delay_between: Delay in seconds between comments (default: 0.5)
            max_comments: Maximum number of comments to post (default: 50)

        Returns:
            List of response data from Bitbucket API for each posted comment

        Raises:
            RuntimeError: If posting fails critically
        """
        # Enforce max comments limit
        comments_to_post = comments[:max_comments]
        results = []

        for comment in comments_to_post:
            try:
                result = await self.post_inline_comment(
                    workspace=workspace,
                    repo_slug=repo_slug,
                    pr_id=pr_id,
                    content=comment.message,
                    file_path=comment.file_path,
                    line_number=comment.line_number
                )
                results.append({
                    "success": True,
                    "comment": comment,
                    "response": result
                })

                # Rate limiting delay
                if delay_between > 0:
                    await asyncio.sleep(delay_between)

            except RuntimeError as e:
                # Log error but continue with other comments
                results.append({
                    "success": False,
                    "comment": comment,
                    "error": str(e)
                })

        return results

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

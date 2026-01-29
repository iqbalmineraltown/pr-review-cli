"""Local git diff manager with repository caching.

This module handles cloning and caching git repositories locally to generate
diffs without hitting API rate limits.
"""
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from .models import PRDiff
from .utils.git_operations import GitOperations, GitCommandError
from .utils.paths import get_git_cache_dir

logger = logging.getLogger(__name__)


class LocalGitDiffManager:
    """Manages local git repository caching and diff generation."""

    METADATA_FILE = "metadata.json"
    METADATA_VERSION = "1.0"

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        console=None,
        use_ssh: bool = True,
        max_age_days: int = 30,
        max_size_gb: float = 5.0,
        timeout_seconds: int = 300
    ):
        """
        Initialize the local git diff manager.

        Args:
            cache_dir: Base cache directory (defaults to ~/.pr-review-cli/cache/git_repos)
            console: Rich console for status messages (optional)
            use_ssh: If True, use SSH for git operations; otherwise HTTPS
            max_age_days: Maximum age of cached repos before cleanup (default: 30)
            max_size_gb: Maximum total cache size in GB (default: 5.0)
            timeout_seconds: Timeout for git operations (default: 300)
        """
        self.cache_dir = cache_dir or get_git_cache_dir()
        self.workspace_dir = self.cache_dir / "workspace"
        self.metadata_file = self.cache_dir / self.METADATA_FILE
        self.console = console
        self.use_ssh = use_ssh
        self.max_age_days = max_age_days
        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.timeout_seconds = timeout_seconds
        self.git_ops = GitOperations(timeout_seconds=timeout_seconds)

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metadata if it doesn't exist
        if not self.metadata_file.exists():
            self._save_metadata({
                "version": self.METADATA_VERSION,
                "last_cleanup": None,
                "repositories": {}
            })

    async def get_pr_diff_local(
        self,
        workspace: str,
        repo_slug: str,
        pr_id: str,
        source_branch: str,
        destination_branch: str
    ) -> PRDiff:
        """
        Get PR diff by cloning repository and generating diff locally.

        This is the main entry point for local diff generation. It handles
        repository cloning/caching, updating, and diff generation.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            pr_id: Pull request ID
            source_branch: Source branch name
            destination_branch: Destination branch name

        Returns:
            PRDiff object with diff content and statistics

        Raises:
            RuntimeError: If git operations fail
            GitCommandError: If git commands fail
        """
        repo_key = f"{workspace}/{repo_slug}"
        repo_path = self.workspace_dir / f"{repo_key}.git"

        try:
            # Ensure repository is cloned and up-to-date
            await self._ensure_repo_cloned(workspace, repo_slug)

            # Generate the diff
            diff_content, additions, deletions, files_changed = await self.git_ops.get_diff(
                repo_path=repo_path,
                source_branch=source_branch,
                destination_branch=destination_branch
            )

            # Update metadata (last_used timestamp)
            self._update_repo_metadata(repo_key)

            return PRDiff(
                pr_id=pr_id,
                files_changed=files_changed,
                additions=additions,
                deletions=deletions,
                diff_content=diff_content
            )

        except GitCommandError as e:
            # Git command failed - provide helpful error message
            if "Permission denied" in e.error or "could not read Username" in e.error:
                raise RuntimeError(
                    f"Git authentication failed for {repo_key}\n"
                    f"{'Use --use-https flag if you have issues with SSH.' if self.use_ssh else 'Ensure you have access to this repository.'}\n"
                    f"Error: {e.error}"
                )
            elif "could not find remote branch" in e.error.lower():
                raise RuntimeError(
                    f"Branch not found in {repo_key}\n"
                    f"Try running with --cleanup-git-cache to refresh the repository.\n"
                    f"Error: {e.error}"
                )
            else:
                raise RuntimeError(
                    f"Failed to generate diff for {repo_key}: {e.error}"
                )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Git operation timed out for {repo_key}\n"
                f"The repository might be very large. Consider increasing PR_REVIEWER_GIT_TIMEOUT."
            )
        except Exception as e:
            logger.exception(f"Unexpected error getting diff for {repo_key}")
            raise RuntimeError(f"Unexpected error: {str(e)}")

    async def _ensure_repo_cloned(self, workspace: str, repo_slug: str) -> None:
        """
        Ensure repository is cloned, updating if it already exists.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug

        Raises:
            GitCommandError: If clone or update fails
        """
        repo_key = f"{workspace}/{repo_slug}"
        repo_path = self.workspace_dir / f"{repo_key}.git"

        if repo_path.exists():
            # Repository exists - update it
            logger.debug(f"Updating cached repository: {repo_key}")
            await self._update_repository(repo_path, repo_key)
        else:
            # Repository doesn't exist - clone it
            logger.debug(f"Cloning repository: {repo_key}")

            if self.console:
                # Print a message that we're cloning
                pass  # The console status is shown by the caller

            remote_url = GitOperations.get_remote_url(
                workspace=workspace,
                repo_slug=repo_slug,
                use_ssh=self.use_ssh
            )

            await self.git_ops.clone_repo(
                remote_url=remote_url,
                target_path=repo_path,
                shallow=True  # Try shallow clone first
            )

            # Record in metadata
            self._update_repo_metadata(
                repo_key,
                cloned_at=datetime.utcnow().isoformat() + "Z",
                initial_clone=True
            )

    async def _update_repository(self, repo_path: Path, repo_key: str) -> None:
        """
        Fetch latest changes for an existing repository.

        Args:
            repo_path: Path to the repository
            repo_key: Repository key (e.g., "workspace/repo")

        Raises:
            GitCommandError: If fetch fails
        """
        try:
            await self.git_ops.fetch_branches(repo_path)

            # Update metadata
            self._update_repo_metadata(repo_key, last_fetched=datetime.utcnow().isoformat() + "Z")

        except GitCommandError as e:
            # Repository might be corrupted - try re-cloning
            logger.warning(f"Failed to update {repo_key}, re-cloning: {e.error}")

            # Remove corrupted repository
            import shutil
            shutil.rmtree(repo_path, ignore_errors=True)

            # Re-clone
            workspace, repo_slug = repo_key.split('/')
            remote_url = GitOperations.get_remote_url(
                workspace=workspace,
                repo_slug=repo_slug,
                use_ssh=self.use_ssh
            )

            await self.git_ops.clone_repo(
                remote_url=remote_url,
                target_path=repo_path,
                shallow=True
            )

            # Update metadata
            self._update_repo_metadata(
                repo_key,
                cloned_at=datetime.utcnow().isoformat() + "Z",
                last_fetched=datetime.utcnow().isoformat() + "Z"
            )

    def _update_repo_metadata(
        self,
        repo_key: str,
        cloned_at: Optional[str] = None,
        last_fetched: Optional[str] = None,
        initial_clone: bool = False
    ) -> None:
        """
        Update metadata for a repository.

        Args:
            repo_key: Repository key (e.g., "workspace/repo")
            cloned_at: ISO timestamp when repo was cloned
            last_fetched: ISO timestamp when repo was last fetched
            initial_clone: True if this is a new clone
        """
        metadata = self._load_metadata()

        if repo_key not in metadata["repositories"]:
            metadata["repositories"][repo_key] = {}

        repo_metadata = metadata["repositories"][repo_key]
        now = datetime.utcnow().isoformat() + "Z"

        # Update timestamps
        repo_metadata["last_used"] = now
        if cloned_at:
            repo_metadata["cloned_at"] = cloned_at
        if last_fetched:
            repo_metadata["last_fetched"] = last_fetched
        if initial_clone or "cloned_at" not in repo_metadata:
            repo_metadata["cloned_at"] = cloned_at or now

        # Update size
        repo_path = self.workspace_dir / f"{repo_key}.git"
        repo_metadata["size_bytes"] = GitOperations.get_repo_size(repo_path)

        self._save_metadata(metadata)

    def _load_metadata(self) -> Dict[str, Any]:
        """
        Load metadata from file.

        Returns:
            Metadata dictionary
        """
        if not self.metadata_file.exists():
            return {
                "version": self.METADATA_VERSION,
                "last_cleanup": None,
                "repositories": {}
            }

        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Metadata corrupted - return fresh structure
            logger.warning("Metadata file corrupted, creating new one")
            return {
                "version": self.METADATA_VERSION,
                "last_cleanup": None,
                "repositories": {}
            }

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Save metadata to file.

        Args:
            metadata: Metadata dictionary to save
        """
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

    async def cleanup_stale_repos(self) -> None:
        """
        Remove old or large repositories from cache.

        Cleanup criteria:
        1. Repositories older than max_age_days
        2. If total cache size exceeds max_size_bytes, remove oldest repos first

        This method updates the metadata file after cleanup.
        """
        metadata = self._load_metadata()
        repositories = metadata.get("repositories", {})

        if not repositories:
            logger.debug("No cached repositories to clean up")
            return

        now = datetime.utcnow()
        repos_to_remove = []
        total_size = sum(repo.get("size_bytes", 0) for repo in repositories.values())

        # 1. Remove repos older than max_age_days
        cutoff_date = now - timedelta(days=self.max_age_days)
        for repo_key, repo_meta in repositories.items():
            if "last_used" not in repo_meta:
                continue

            last_used = datetime.fromisoformat(repo_meta["last_used"].replace('Z', '+00:00'))
            if last_used < cutoff_date:
                repos_to_remove.append(repo_key)

        # 2. If still over size limit, remove oldest repos
        if total_size > self.max_size_bytes:
            # Sort repos by last_used date (oldest first)
            sorted_repos = sorted(
                repositories.items(),
                key=lambda x: datetime.fromisoformat(x[1].get("last_used", "").replace('Z', '+00:00'))
            )

            # Remove oldest repos until we're under the limit
            current_size = total_size
            for repo_key, repo_meta in sorted_repos:
                if current_size <= self.max_size_bytes:
                    break
                if repo_key not in repos_to_remove:
                    repos_to_remove.append(repo_key)
                    current_size -= repo_meta.get("size_bytes", 0)

        # Remove the repos
        import shutil
        removed_count = 0
        freed_space = 0

        for repo_key in repos_to_remove:
            repo_path = self.workspace_dir / f"{repo_key}.git"
            repo_meta = repositories.get(repo_key, {})

            if repo_path.exists():
                try:
                    shutil.rmtree(repo_path)
                    removed_count += 1
                    freed_space += repo_meta.get("size_bytes", 0)
                except Exception as e:
                    logger.error(f"Failed to remove {repo_key}: {e}")

            # Remove from metadata
            if repo_key in repositories:
                del repositories[repo_key]

        # Update metadata
        metadata["last_cleanup"] = now.isoformat() + "Z"
        metadata["repositories"] = repositories
        self._save_metadata(metadata)

        if self.console and removed_count > 0:
            freed_mb = freed_space / (1024 * 1024)
            self.console.print(f"[dim]  Removed {removed_count} old repo(s), freed {freed_mb:.1f} MB[/dim]")

        logger.info(f"Cleanup complete: removed {removed_count} repos, freed {freed_space} bytes")

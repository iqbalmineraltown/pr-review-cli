"""Git operations utility for local diff generation.

This module provides a clean interface to git commands for cloning repositories
and generating diffs locally, avoiding API rate limits.
"""
import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class GitCommandError(Exception):
    """Exception raised when a git command fails."""
    def __init__(self, command: str, exit_code: int, output: str, error: str):
        self.command = command
        self.exit_code = exit_code
        self.output = output
        self.error = error
        super().__init__(f"Git command failed: {command}\n{error}")


class GitOperations:
    """Wrapper for git operations with async subprocess handling."""

    def __init__(self, timeout_seconds: int = 300):
        """
        Initialize GitOperations.

        Args:
            timeout_seconds: Default timeout for git commands (default: 5 minutes)
        """
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def verify_git_available() -> bool:
        """
        Check if git is installed and accessible.

        Returns:
            True if git is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip().startswith("git version")
        except Exception:
            return False

    @staticmethod
    def get_remote_url(
        workspace: str,
        repo_slug: str,
        use_ssh: bool = True
    ) -> str:
        """
        Construct Bitbucket clone URL.

        Args:
            workspace: Bitbucket workspace name
            repo_slug: Repository slug
            use_ssh: If True, use SSH URL; otherwise use HTTPS

        Returns:
            Git remote URL string

        Examples:
            >>> get_remote_url("myworkspace", "myrepo", use_ssh=True)
            'git@bitbucket.org:myworkspace/myrepo.git'
            >>> get_remote_url("myworkspace", "myrepo", use_ssh=False)
            'https://bitbucket.org/myworkspace/myrepo.git'
        """
        if use_ssh:
            return f"git@bitbucket.org:{workspace}/{repo_slug}.git"
        else:
            return f"https://bitbucket.org/{workspace}/{repo_slug}.git"

    async def clone_repo(
        self,
        remote_url: str,
        target_path: Path,
        shallow: bool = True
    ) -> None:
        """
        Clone a repository to the specified path.

        Uses bare clone for minimal disk usage. Attempts shallow clone first
        (depth=1) for efficiency, with fallback to full clone if it fails.

        After cloning, fetches all branches to ensure complete branch history.

        Args:
            remote_url: Git remote URL to clone from
            target_path: Local path where repo should be cloned
            shallow: If True, attempt shallow clone (depth=1) first

        Raises:
            GitCommandError: If clone fails (both shallow and full)
        """
        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Try shallow clone first (faster, less disk space)
        if shallow:
            try:
                cmd = [
                    "git", "clone",
                    "--bare",
                    "--depth=1",
                    remote_url,
                    str(target_path)
                ]
                await self._run_command(cmd, timeout=self.timeout_seconds)
                logger.debug(f"Shallow clone successful: {target_path}")

                # Fetch all branches after shallow clone
                # This ensures we have refs to all branches, not just the default one
                try:
                    await self.fetch_branches(target_path)
                    logger.debug(f"Fetched all branches for: {target_path}")
                except GitCommandError as e:
                    # If fetch fails, it might be a single-branch repo or other issue
                    # Not critical, so log and continue
                    logger.debug(f"Branch fetch after shallow clone had issues: {e}")

                return
            except GitCommandError as e:
                # Some repositories don't support shallow clones
                # Fall back to full clone
                logger.debug(f"Shallow clone failed, trying full clone: {e}")

        # Full clone as fallback
        cmd = [
            "git", "clone",
            "--bare",
            remote_url,
            str(target_path)
        ]
        await self._run_command(cmd, timeout=self.timeout_seconds)
        logger.debug(f"Clone complete: {target_path}")

    async def fetch_branches(
        self,
        repo_path: Path
    ) -> None:
        """
        Fetch all branches from remote in a bare repository.

        Args:
            repo_path: Path to the bare git repository

        Raises:
            GitCommandError: If fetch fails
        """
        # In bare repositories, we need to explicitly fetch all branches
        # Store them in refs/remotes/origin/* to maintain standard git remote tracking
        cmd = [
            "git",
            "--git-dir", str(repo_path),
            "fetch",
            "--prune",
            "origin",
            "+refs/heads/*:refs/remotes/origin/*"
        ]
        await self._run_command(cmd, timeout=self.timeout_seconds)
        logger.debug(f"Fetched updates for: {repo_path}")

    async def get_diff(
        self,
        repo_path: Path,
        source_branch: str,
        destination_branch: str,
        context_lines: int = 3
    ) -> Tuple[str, int, int, List[str]]:
        """
        Generate unified diff between two branches.

        Args:
            repo_path: Path to the bare git repository
            source_branch: Source branch (e.g., "feature-branch")
            destination_branch: Destination branch (e.g., "main")
            context_lines: Number of context lines in diff (default: 3)

        Returns:
            Tuple of (diff_content, additions, deletions, files_changed)

        Raises:
            GitCommandError: If diff generation fails
        """
        # Try different revision range syntaxes
        # 1. First try triple-dot (merge base) for cleaner diffs
        # 2. Fall back to double-dot if merge base doesn't exist
        revision_ranges = [
            f"origin/{destination_branch}...origin/{source_branch}",  # Merge base (preferred)
            f"origin/{destination_branch}..origin/{source_branch}",    # Direct comparison (fallback)
            f"refs/heads/{destination_branch}...refs/heads/{source_branch}",  # Direct refs (fallback 2)
            f"refs/heads/{destination_branch}..refs/heads/{source_branch}",    # Direct refs direct (fallback 3)
        ]

        last_error = None
        for revision_range in revision_ranges:
            try:
                # Get the unified diff
                diff_cmd = [
                    "git",
                    "--git-dir", str(repo_path),
                    "diff",
                    f"--unified={context_lines}",
                    revision_range
                ]

                diff_output, _ = await self._run_command(diff_cmd, timeout=self.timeout_seconds)
                diff_content = diff_output

                # Get statistics using --numstat for accurate counts
                stat_cmd = [
                    "git",
                    "--git-dir", str(repo_path),
                    "diff",
                    "--numstat",
                    revision_range
                ]

                stat_output, _ = await self._run_command(stat_cmd, timeout=self.timeout_seconds)
                additions, deletions, files_changed = self._parse_diff_stats(stat_output)

                logger.debug(f"Successfully generated diff using: {revision_range}")
                return diff_content, additions, deletions, files_changed

            except GitCommandError as e:
                last_error = e
                logger.debug(f"Failed to generate diff with '{revision_range}': {e.error}")
                # Try next syntax
                continue

        # All syntaxes failed - raise the last error with helpful message
        error_msg = last_error.error if last_error else "Unknown error"
        raise GitCommandError(
            command="git diff",
            exit_code=last_error.exit_code if last_error else 1,
            output="",
            error=(
                f"Failed to generate diff between {destination_branch} and {source_branch}.\n"
                f"This could mean:\n"
                f"  • One or both branches don't exist in the repository\n"
                f"  • The branches have completely diverged with no common history\n"
                f"  • The repository wasn't fetched properly\n\n"
                f"Try running with --cleanup-git-cache to re-clone the repository.\n"
                f"Git error: {error_msg}"
            )
        )

    @staticmethod
    def _parse_diff_stats(numstat_output: str) -> Tuple[int, int, List[str]]:
        """
        Parse git diff --numstat output.

        Args:
            numstat_output: Output from 'git diff --numstat' command

        Returns:
            Tuple of (total_additions, total_deletions, list_of_files)

        Example numstat output:
            15    2    path/to/file.py
            3     0    another/file.ts
            -     -    binary_file.png
        """
        additions = 0
        deletions = 0
        files_changed = []

        for line in numstat_output.strip().split('\n'):
            if not line:
                continue

            parts = line.split('\t')
            if len(parts) < 3:
                continue

            add_str, del_str, filepath = parts[0], parts[1], parts[2]

            # Handle binary files (shown as "-" in numstat)
            if add_str == '-' or del_str == '-':
                # Binary file - count as 1 file but no line changes
                files_changed.append(filepath)
                continue

            try:
                add_count = int(add_str) if add_str else 0
                del_count = int(del_str) if del_str else 0
                additions += add_count
                deletions += del_count
                files_changed.append(filepath)
            except ValueError:
                # Skip malformed lines
                continue

        return additions, deletions, files_changed

    @staticmethod
    async def _run_command(
        command: List[str],
        timeout: int = 300,
        cwd: Optional[Path] = None
    ) -> Tuple[str, str]:
        """
        Run a command asynchronously and return output.

        Args:
            command: Command and arguments as a list
            timeout: Timeout in seconds
            cwd: Working directory for command

        Returns:
            Tuple of (stdout, stderr)

        Raises:
            GitCommandError: If command returns non-zero exit code
            asyncio.TimeoutError: If command times out
        """
        logger.debug(f"Running command: {' '.join(command)}")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')

            if process.returncode != 0:
                raise GitCommandError(
                    command=' '.join(command),
                    exit_code=process.returncode,
                    output=stdout_text,
                    error=stderr_text
                )

            return stdout_text, stderr_text

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise asyncio.TimeoutError(
                f"Command timed out after {timeout} seconds: {' '.join(command)}"
            )

    @staticmethod
    def get_repo_size(repo_path: Path) -> int:
        """
        Get the size of a repository in bytes.

        Args:
            repo_path: Path to the repository

        Returns:
            Size in bytes
        """
        if not repo_path.exists():
            return 0

        total_size = 0
        for dirpath, dirnames, filenames in os.walk(repo_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)

        return total_size

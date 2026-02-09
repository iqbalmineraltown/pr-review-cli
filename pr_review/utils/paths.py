"""Path management utilities for pr-review-cli"""
import os
from pathlib import Path


def get_config_dir() -> Path:
    """Get the user's config directory for pr-review-cli"""
    # Check environment variable first
    config_dir = os.environ.get("PR_REVIEWER_CONFIG_DIR")

    if config_dir:
        return Path(config_dir)

    # Default to ~/.pr-review-cli
    return Path.home() / ".pr-review-cli"


def get_cache_dir() -> Path:
    """Get the cache directory for pr-review-cli"""
    # Check environment variable first
    cache_dir = os.environ.get("CACHE_DIR")

    if cache_dir:
        return Path(cache_dir).expanduser()

    # Default to ~/.pr-review-cli/cache
    return get_config_dir() / "cache"


def get_env_file() -> Path:
    """Get the .env file location"""
    return get_config_dir() / ".env"


def ensure_directories() -> None:
    """Ensure required directories exist"""
    config_dir = get_config_dir()
    cache_dir = get_cache_dir()
    prompts_dir = get_config_dir() / "prompts"

    config_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)


def get_git_cache_dir() -> Path:
    """Get the git repository cache directory"""
    cache_dir = get_cache_dir()
    git_cache = cache_dir / "git_repos"
    return git_cache


def get_reviewers_dir() -> Path:
    """Get the reviewer personas directory for PR Defense Council"""
    return get_config_dir() / "reviewers"

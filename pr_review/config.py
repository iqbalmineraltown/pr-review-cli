import os
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
from .utils.paths import get_env_file, ensure_directories


class Config:
    """Configuration management using .env files"""

    def __init__(self):
        # Load .env from multiple locations (in priority order)
        # 1. Project directory (for development)
        # 2. Config directory (~/.pr-review-cli/.env)
        ensure_directories()

        env_file = get_env_file()

        # Load from config directory if it exists
        if env_file.exists():
            load_dotenv(env_file)
            # print(f"Loaded config from: {env_file}")  # Debug

        # Also load from current directory (for development/override)
        load_dotenv()

    @property
    def bitbucket_email(self) -> Optional[str]:
        """Get Bitbucket email for basic auth (API Token) from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_EMAIL")

    @property
    def bitbucket_api_token(self) -> Optional[str]:
        """Get Bitbucket API token for basic auth (API Token) from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_API_TOKEN")

    @property
    def bitbucket_workspace(self) -> Optional[str]:
        """Get default Bitbucket workspace from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_WORKSPACE")

    @property
    def bitbucket_user_uuid(self) -> Optional[str]:
        """Get Bitbucket user UUID from .env (cached for performance)"""
        return os.getenv("PR_REVIEWER_BITBUCKET_USER_UUID")

    @property
    def has_valid_credentials(self) -> bool:
        """Check if we have valid basic auth credentials"""
        return all([self.bitbucket_email, self.bitbucket_api_token])

    def _print_credentials_warning(self):
        """Print helpful warning message when credentials are missing"""
        env_file = get_env_file()

        print("\n" + "="*60)
        print("⚠️  MISSING BITBUCKET CREDENTIALS  ⚠️")
        print("="*60)
        print("\nTo use pr-review-cli, create a .env file:\n")

        if not env_file.exists():
            print(f"1. Create the .env file:")
            print(f"   mkdir -p ~/.pr-review-cli")
            print(f"   cp .env.example {env_file}")
            print(f"   nano {env_file}\n")
        else:
            print(f"✅ .env file exists at: {env_file}")
            print(f"   But it's missing required fields!\n")

        print("2. Create an API Token at:")
        print("   https://bitbucket.org/account/settings/api-tokens/\n")
        print("   Required permissions:")
        print("   ✅ Pull requests: Read")
        print("   ✅ Repositories: Read")
        print("   ✅ Account: Read (optional)\n")

        print("3. Add these fields to your .env file:")
        print(f"   PR_REVIEWER_BITBUCKET_EMAIL=your_email@example.com")
        print(f"   PR_REVIEWER_BITBUCKET_API_TOKEN=your_app_password")
        print(f"   PR_REVIEWER_BITBUCKET_WORKSPACE=your_workspace\n")

        print("="*60 + "\n")

    @property
    def bitbucket_base_url(self) -> str:
        return os.getenv("BITBUCKET_BASE_URL", "https://api.bitbucket.org/2.0")

    @property
    def claude_cli_path(self) -> str:
        return os.getenv("CLAUDE_CLI_PATH", "claude")

    @property
    def cache_dir(self) -> Path:
        from .utils.paths import get_cache_dir
        cache_dir_env = os.getenv("CACHE_DIR")
        if cache_dir_env:
            return Path(cache_dir_env).expanduser()
        return get_cache_dir()

    @property
    def config_dir(self) -> Path:
        from .utils.paths import get_config_dir
        return get_config_dir()

    @property
    def use_ssh_for_git(self) -> bool:
        return os.getenv("PR_REVIEWER_GIT_USE_SSH", "true").lower() == "true"

    @property
    def git_cache_max_age_days(self) -> int:
        return int(os.getenv("PR_REVIEWER_GIT_CACHE_MAX_AGE", "30"))

    @property
    def git_cache_max_size_gb(self) -> float:
        return float(os.getenv("PR_REVIEWER_GIT_CACHE_MAX_SIZE", "5.0"))

    @property
    def git_timeout_seconds(self) -> int:
        return int(os.getenv("PR_REVIEWER_GIT_TIMEOUT", "300"))

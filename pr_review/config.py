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
    def bitbucket_client_id(self) -> Optional[str]:
        """Get Bitbucket OAuth client ID from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_CLIENT_ID")

    @property
    def bitbucket_client_secret(self) -> Optional[str]:
        """Get Bitbucket OAuth client secret from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_CLIENT_SECRET")

    @property
    def bitbucket_access_token(self) -> Optional[str]:
        """Get Bitbucket OAuth access token from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_ACCESS_TOKEN")

    @property
    def bitbucket_refresh_token(self) -> Optional[str]:
        """Get Bitbucket OAuth refresh token from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_REFRESH_TOKEN")

    @property
    def bitbucket_username(self) -> Optional[str]:
        """Get Bitbucket username from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_USERNAME")

    @property
    def bitbucket_user_uuid(self) -> Optional[str]:
        """Get Bitbucket user UUID from .env (preferred over username for matching)"""
        return os.getenv("PR_REVIEWER_BITBUCKET_USER_UUID")

    @property
    def bitbucket_workspace(self) -> Optional[str]:
        """Get default Bitbucket workspace from .env"""
        return os.getenv("PR_REVIEWER_BITBUCKET_WORKSPACE")

    @property
    def is_using_oauth(self) -> bool:
        """Check if using OAuth (has all required OAuth credentials)"""
        return all([
            self.bitbucket_client_id,
            self.bitbucket_client_secret,
            self.bitbucket_refresh_token
        ])

    @property
    def has_valid_access_token(self) -> bool:
        """Check if we have a valid access token"""
        return bool(self.bitbucket_access_token)

    @property
    def bitbucket_token(self) -> Optional[str]:
        """
        Get Bitbucket access token (legacy property for backwards compatibility).
        """
        return self.bitbucket_access_token

    def _print_token_warning(self):
        """Print helpful warning message when token is missing"""
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

        print("2. Add these fields to your .env file:")
        print(f"   PR_REVIEWER_BITBUCKET_CLIENT_ID=your_client_id")
        print(f"   PR_REVIEWER_BITBUCKET_CLIENT_SECRET=your_client_secret")
        print(f"   PR_REVIEWER_BITBUCKET_REFRESH_TOKEN=your_refresh_token")
        print(f"   PR_REVIEWER_BITBUCKET_ACCESS_TOKEN=your_access_token")
        print(f"   PR_REVIEWER_BITBUCKET_USERNAME=your_username\n")

        print("3. Or run OAuth setup:")
        print("   python3 oauth_helper.py <CLIENT_ID> <CLIENT_SECRET>\n")

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

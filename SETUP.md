# 🚀 Quick Setup Guide

## One-Time Setup (2 Minutes)

### Step 1: Run OAuth Setup

```bash
cd ~/projects/pr-review-cli
python3 oauth_helper.py <CLIENT_ID> <CLIENT_SECRET>
```

This will:
- ✅ Open your browser for Bitbucket authorization
- ✅ Save credentials to `~/.pr-review-cli/.env`
- ✅ Set secure permissions (600)

### Step 2: You're Done!

No environment variables needed. Just run:

```bash
# With workspace argument
python3 -m pr_review.main review <workspace>

# OR without workspace (uses PR_REVIEWER_BITBUCKET_WORKSPACE from .env)
python3 -m pr_review.main review
```

**Pro Tip:** Set `PR_REVIEWER_BITBUCKET_WORKSPACE` in your `.env` file to avoid typing the workspace every time!

## Credentials Location

Credentials are stored in:
```
~/.pr-review-cli/.env
```

**Contents:**
```bash
# ────────────────────────────────────────────────
# USER CONFIGURATION (Fill these in yourself)
# ────────────────────────────────────────────────

PR_REVIEWER_BITBUCKET_CLIENT_ID=your_client_id
PR_REVIEWER_BITBUCKET_CLIENT_SECRET=your_client_secret
PR_REVIEWER_BITBUCKET_USERNAME=your_username
PR_REVIEWER_BITBUCKET_WORKSPACE=your_workspace    # ← Default workspace!

# ────────────────────────────────────────────────
# AUTOMATIC TOKENS (DO NOT EDIT - Auto-managed)
# ────────────────────────────────────────────────

PR_REVIEWER_BITBUCKET_ACCESS_TOKEN=your_access_token      # [AUTO-POPULATED]
PR_REVIEWER_BITBUCKET_REFRESH_TOKEN=your_refresh_token    # [AUTO-POPULATED]
```

## Refresh Token

When your access token expires (2 hours):

```bash
python3 refresh_token.py
```

This automatically updates `~/.pr-review-cli/.env`!

## File Locations

```
~/.pr-review-cli/              # Config directory (auto-created)
├── .env                       # Your credentials ⚠️ NEVER commit
├── cache/                     # Cached data
└── prompts/                   # Custom analysis prompts

~/projects/pr-review-cli/      # Project directory
├── .env.example               # Example template
├── .gitignore                 # Ignores .env files ✅
├── oauth_helper.py            # OAuth setup tool
└── refresh_token.py           # Token refresh tool
```

## Security

- `.env` file has permissions `600` (owner read/write only)
- `.gitignore` prevents committing credentials
- Stored in home directory, not project directory

## Priority Order

The CLI loads credentials from:

1. **`~/.pr-review-cli/.env`** ← Primary (recommended)
2. `.env` (current directory) ← For development/override
3. Environment variables ← Legacy support

## Troubleshooting

### Credentials not found?

```bash
# Check .env exists
ls -la ~/.pr-review-cli/.env

# Re-run OAuth setup
python3 oauth_helper.py <CLIENT_ID> <CLIENT_SECRET>
```

### Invalid token?

```bash
# Refresh token
python3 refresh_token.py
```

### Verify configuration

```python
python3 -c "
from pr_review.config import Config
config = Config()
print('Has access token:', config.has_valid_access_token)
print('Using OAuth:', config.is_using_oauth)
print('Username:', config.bitbucket_username)
"
```

## Git Safety

`.gitignore` is configured to ignore:
- ✅ `.env` files
- ✅ `credentials.json`
- ✅ `bitbucket_oauth_tokens.json`

**Your credentials will NEVER be committed!**

---

**Need help?** See `.env.example` for template

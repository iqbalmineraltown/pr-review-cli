# PR Review CLI

AI-powered pull request review assistant for Bitbucket.

## Features

- 🤖 **AI-Powered Analysis**: Uses Claude to analyze PR diffs and extract insights
- 🎯 **Smart Prioritization**: Automatically ranks PRs by risk and importance
- 📊 **Interactive TUI**: Beautiful terminal UI for navigating PRs
- 💬 **Inline Comments**: Per-line code comments with severity levels (critical/high/medium/low)
- 📝 **Post Comments**: One-click posting of summary and inline comments to PRs
- ⚡ **Parallel Processing**: Analyzes multiple PRs concurrently
- 🔍 **Large PR Handling**: Intelligently handles PRs too large for AI analysis
- 🔐 **API Token Authentication**: Secure authentication using Bitbucket API Tokens
- 🌐 **Workspace-Wide Search**: Search all repos in your workspace at once
- ⏰ **Age-Based Prioritization**: Older PRs get higher priority to prevent bottlenecks
- 💾 **Local Git Diff Mode**: Clone repos locally to bypass API limits and analyze PRs of any size

## Prerequisites

- **Claude Code CLI**: This tool requires [Claude Code CLI](https://claude.ai/code) to be installed and configured. Install it with:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```

## Installation

### Option 1: Install from PyPI (Recommended)

```bash
pip install pr-review-cli
```

### Option 2: Install from Source

```bash
cd ~/projects/pr-review-cli
poetry install
```

## Quick Setup (2 Minutes)

### Step 1: Create Bitbucket API Token

1. Go to: https://bitbucket.org/account/settings/api-tokens/
2. Click "Create API Token"
3. Give it a name (e.g., "pr-review-cli")
4. Select these permissions:
   - ✅ **Pull requests**: Read
   - ✅ **Repositories**: Read
   - ✅ **Account**: Read (optional, for displaying your name)
5. Click "Create" and copy the generated password

> **⚠️ Important**: The `Repositories: Read` permission is essential for workspace-wide search. Without it, you can only review specific repositories by specifying the repo slug explicitly.

### Step 2: Configure Environment Variables

```bash
# Create config directory
mkdir -p ~/.pr-review-cli

# Copy example env file
cp .env.example ~/.pr-review-cli/.env

# Edit the file
nano ~/.pr-review-cli/.env
```

Add your credentials:

```bash
PR_REVIEWER_BITBUCKET_EMAIL=your_email@example.com
PR_REVIEWER_BITBUCKET_API_TOKEN=your_app_password_here
PR_REVIEWER_BITBUCKET_WORKSPACE=your_workspace_here  # Optional but recommended
```

### Step 3: You're Done!

```bash
# Search all repos in your workspace
pr-review review myworkspace

# OR search a specific repo
pr-review review myworkspace myrepo

# If you set PR_REVIEWER_BITBUCKET_WORKSPACE, just run:
pr-review review
```

## Configuration

Credentials are stored in:
```
~/.pr-review-cli/.env
```

**Required Variables:**
```bash
PR_REVIEWER_BITBUCKET_EMAIL=your_email@example.com
PR_REVIEWER_BITBUCKET_API_TOKEN=your_app_password
PR_REVIEWER_BITBUCKET_WORKSPACE=your_workspace  # Optional but recommended
```

**Optional Variables:**
```bash
# Claude CLI command (default: "claude")
CLAUDE_CLI_COMMAND=claude

# Claude CLI flags for JSON output
# Default: "-p --output-format json"
# CLAUDE_CLI_FLAGS=-p --output-format json

# Bitbucket API base URL (default: https://api.bitbucket.org/2.0)
BITBUCKET_BASE_URL=https://api.bitbucket.org/2.0

# Cache directory (default: ~/.pr-review-cli/cache)
CACHE_DIR=/custom/cache/directory

# Git Operations (for --local-diff mode)
# Use SSH for git operations (default: true)
PR_REVIEWER_GIT_USE_SSH=true

# Git cache maximum age in days before cleanup (default: 30)
PR_REVIEWER_GIT_CACHE_MAX_AGE=30

# Git cache maximum size in GB before cleanup (default: 5.0)
PR_REVIEWER_GIT_CACHE_MAX_SIZE=5.0

# Git command timeout in seconds (default: 300)
PR_REVIEWER_GIT_TIMEOUT=300
```

### AI CLI Configuration

This tool uses the [Claude Code CLI](https://claude.ai/code) for AI analysis. You can configure it to use either the official Anthropic API or a compatible proxy (like GLM).

#### Option 1: Official Anthropic Claude API (Default)

Uses the official Anthropic API directly. No special configuration needed:

```bash
# ~/.pr-review-cli/.env
CLAUDE_CLI_COMMAND=claude
CLAUDE_CLI_FLAGS=-p --output-format json
```

**Requirements:**
- Valid Anthropic API key in `~/.claude/settings.json`
- Default `ANTHROPIC_BASE_URL` pointing to `https://api.anthropic.com`

#### Option 2: GLM API Proxy

If you're using a GLM proxy (like `https://api.z.ai/api/anthropic`), you must specify the model:

```bash
# ~/.pr-review-cli/.env
CLAUDE_CLI_COMMAND=claude
CLAUDE_CLI_FLAGS=--model opus -p --output-format json
```

**Why `--model opus` is required for GLM:**
- GLM API expects model aliases like `opus`, `sonnet`
- Without this flag, Claude CLI uses full model IDs (e.g., `claude-sonnet-4-5-20250929`) which GLM doesn't recognize
- This causes "Unknown Model" errors

**Your Claude Code settings** (`~/.claude/settings.json`) with GLM proxy:
```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "your-glm-api-key",
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"
  }
}
```

#### Testing Your Configuration

Verify your AI CLI setup works:

```bash
# Test without PR Review CLI
echo "test" | claude -p --output-format json
```

Expected output (success):
```json
{"type":"result","result":"...","session_id":"..."}
```

Expected output (error - means model is wrong):
```json
{"type":"result","result":"API Error: 400 {\"error\":{\"code\":\"1211\",\"message\":\"Unknown Model\"}..."}
```

#### Quick Reference

| Setup | CLAUDE_CLI_FLAGS |
|-------|------------------|
| **Official Anthropic API** | `-p --output-format json` |
| **GLM Proxy** | `--model opus -p --output-format json` |

## Usage

### Single PR Analysis

Analyze a specific PR using its Bitbucket URL:

```bash
# Analyze a single PR from URL (automatically non-interactive)
pr-review review --pr-url https://bitbucket.org/workspace/repo/pull-requests/123

# Combine with local diff mode for large PRs
pr-review review --pr-url https://bitbucket.org/workspace/repo/pull-requests/123 --local-diff
```

### Skip AI Analysis

Quickly view PR summary without AI analysis (faster, no API costs):

```bash
# Skip AI analysis for all PRs
pr-review review myworkspace --skip-analyze

# Skip AI and export to markdown
pr-review review myworkspace --skip-analyze --no-interactive --export markdown

# Useful for quick PR overview before detailed review
pr-review review myworkspace myrepo --skip-analyze -m 20
```

### Interactive Review (Default)

```bash
# Search all repos in your workspace
pr-review review myworkspace

# Search a specific repository
pr-review review myworkspace myrepo
```

### Non-Interactive with Export

```bash
# Generate markdown report
pr-review review myworkspace -I -e markdown -o daily_report

# Generate JSON report (short flags)
pr-review review myworkspace -I -e json -o pr_data.json

# Terminal output only
pr-review review myworkspace --no-interactive --export terminal

# Export format aliases
pr-review review myworkspace -I -e markdown  # -e is short for --export
```

### Limit PRs

```bash
# Limit to 10 PRs (default is 30)
pr-review review myworkspace -m 10

# Process up to 50 PRs
pr-review review myworkspace --max-prs 50

# Short flag works too
pr-review review myworkspace -m 5
```

### Local Git Diff Mode (Analyze Large PRs)

By default, the tool uses the Bitbucket API to fetch diffs, which skips PRs larger than 50,000 characters. With `--local-diff`, repositories are cloned locally and diffs are generated using git, allowing analysis of PRs of **any size**.

```bash
# Use local git to generate diffs (bypasses size limits)
pr-review review myworkspace --local-diff

# Clean stale cached repositories before running
pr-review review myworkspace --local-diff --cleanup-git-cache

# Use HTTPS instead of SSH for git operations
pr-review review myworkspace --local-diff --use-https

# Analyze massive PRs that would be skipped in API mode
pr-review review myworkspace myrepo --local-diff -m 50
```

**When to use `--local-diff`:**
- 🔓 Analyzing PRs larger than 50K characters (automatically skipped in API mode)
- 📊 Bulk analysis of many large PRs
- ✈️ Offline analysis (after initial clone)
- 🔄 Frequent reviews of the same repositories (cached repos speed up subsequent runs)

**When to use API mode (default):**
- ⚡ Quick reviews of small/medium PRs
- 💾 Limited disk space
- 🚫 No git installation available

### View Cache Statistics

```bash
pr-review cache-stats
```

### Customizing the AI Prompt

To customize the AI analysis prompt, edit this file:

```bash
~/.pr-review-cli/prompts/default.md
```

On first run, this file is auto-created from built-in prompts in the project. The project includes several prompt templates:

- `default.md` - Inline comments focused (recommended)
- `quick-scan.md` - Fast reviews without inline comments
- `security-focused.md` - Security vulnerability focused
- `performance-review.md` - Performance and optimization focused

**Supported placeholders:**
- `{{{title}}}` - PR title (use triple braces for Jinja2-style escaping)
- `{{{author}}}` - PR author
- `{{{source}}}` - Source branch
- `{{{destination}}}` - Destination branch
- `{{{diff}}}` - Diff content

**Example `default.md`:**
```markdown
---
name: "Security Focused Review"
description: "Focuses on security vulnerabilities"
version: "1.0"
---

Analyze this pull request with a security focus:

PR Title: {{{title}}}
Author: {{{author}}}
Branch: {{{source}}} → {{{destination}}}

Diff:
{{{diff}}}

Please identify security vulnerabilities, sensitive data exposure,
and authorization issues. Respond with valid JSON:
{
  "good_points": ["..."],
  "attention_required": ["..."],
  "risk_factors": ["..."],
  "overall_quality_score": 85,
  "estimated_review_time": "15min",
  "line_comments": [
    {
      "file_path": "src/auth.py",
      "line_number": 42,
      "severity": "critical",
      "message": "SQL injection vulnerability"
    }
  ]
}
```

**Expected JSON Response:**
```json
{
  "good_points": ["Well-implemented pattern"],
  "attention_required": ["Bug found"],
  "risk_factors": ["Breaking change"],
  "overall_quality_score": 85,
  "estimated_review_time": "30 minutes",
  "line_comments": [
    {
      "file_path": "src/file.py",
      "line_number": 123,
      "severity": "high",
      "message": "Missing error handling"
    }
  ]
}
```

After saving, restart the CLI - your changes take effect immediately.

## Interactive TUI Shortcuts

- `↑/↓` or `j/k`: Navigate PRs
- `Enter`: View full details
- `o`: Open PR in browser
- `p`: Post comments (summary + inline comments) to PR
- `q`: Quit

### Posting Comments

When you press `p` to post comments, the tool:

1. **Exits TUI** and shows a terminal UI
2. **Posts a summary comment** with:
   - Priority score and quality score
   - Good points, attention items, risk factors
   - Formatted as markdown

3. **Posts inline comments** (if available) with:
   - File path and line number
   - Severity level (critical/high/medium/low)
   - Brief message describing the issue

4. **Auto-resumes** the TUI after 5 seconds

The summary comment is formatted as:
```markdown
## 🤖 AI PR Review: {PR Title}

**Priority Score:** 85/100
**Quality Score:** 75/100
**Est. Review Time:** 30-45 min

### ✅ Good Points
- Well-implemented pattern

### ⚠️ Attention Required
- Bug found in line 42

### 🔍 Risk Factors
- Breaking change

---
*Posted by PR Review CLI*
```

Inline comments are posted separately and appear on specific lines in the diff view.

## Priority Levels

The system calculates a priority score (0-100) for each PR based on 7 factors:

| Priority Score | Risk Level | Color | Action |
|---------------|------------|-------|--------|
| **70-100** | CRITICAL | 🔴 Red | Review immediately |
| **50-69** | HIGH | 🟠 Orange | Review soon |
| **30-49** | MEDIUM | 🟡 Yellow | Review when possible |
| **0-29** | LOW | 🟢 Green | Review at leisure |

### Scoring Factors

1. **Size** (0-25 pts): Larger PRs score higher
2. **Age** (0-25 pts): Older PRs score higher (max 5 days considered)
3. **File Type Risk** (0-20 pts): Database, config, or security files
4. **Author Experience** (0-15 pts): New contributors score higher
5. **AI Quality Assessment** (0-40 pts): Lower quality = higher priority
6. **Attention Required** (0-20 pts): More issues = higher priority
7. **Risk Factors** (0-10 pts): More risks = higher priority

### Special Case: Large PRs

**In API mode (default):**
PRs too large for AI analysis (>50K characters) automatically get:
- **Score 90-100** (maximum priority)
- Marked as "MANUAL REVIEW REQUIRED"
- Diff size logged for reference

**In local diff mode (`--local-diff`):**
- **ALL PRs are analyzed regardless of size** - no 50K character limit!
- Larger PRs may take longer to analyze but will receive full AI insights
- Recommended for analyzing massive refactors or migrations

## Examples

### Morning Review Routine

```bash
# Generate daily report
pr-review review acme-corp \
  --no-interactive \
  --export markdown \
  --output daily_review_$(date +%Y%m%d)
```

### Team-Specific Review

```bash
# Check backend team repos only
pr-review review backend-team

# Or specific repo
pr-review review acme-corp payment-service
```

### Single PR Quick Review

```bash
# Analyze a specific PR without AI (fastest)
pr-review review --pr-url https://bitbucket.org/acme-corp/payment-service/pull-requests/42 --skip-analyze

# Large PR analysis with local git
pr-review review --pr-url https://bitbucket.org/acme-corp/payment-service/pull-requests/42 --local-diff
```

## Troubleshooting

### Permission denied or "credentials lack required scopes"?

If you see errors like:
```
Your credentials lack one or more required privilege scopes.
Required: ["repository:read"]
```

This means your API Token is missing required permissions:

1. Go to: https://bitbucket.org/account/settings/api-tokens/
2. Create a new API Token with these permissions:
   - ✅ Pull requests: Read
   - ✅ Repositories: Read
   - ✅ Account: Read (optional)
3. Update your `~/.pr-review-cli/.env` with the new password

### Credentials not found?

```bash
# Check .env exists
ls -la ~/.pr-review-cli/.env

# Verify contents
cat ~/.pr-review-cli/.env
```

### Verify configuration

```bash
python3 -c "
from pr_review.config import Config
config = Config()
print('Has credentials:', config.has_valid_credentials)
print('Email:', config.bitbucket_email)
print('Workspace:', config.bitbucket_workspace)
"
```

### Claude CLI not found?

```bash
# Specify custom command
export CLAUDE_CLI_COMMAND=claude
# or use a different AI CLI
export CLAUDE_CLI_COMMAND=openai
```

### "Unknown Model" or "AI analysis failed" errors?

If you see errors like:
```
API Error: 400 {"error":{"code":"1211","message":"Unknown Model, please check the model code."}}
```

Or:
```
Failed to parse GLM response content
```

This means your AI CLI is configured to use a model that your API provider doesn't recognize.

**If using GLM proxy:**
1. Check your `~/.claude/settings.json` for `ANTHROPIC_BASE_URL`
2. If it points to a proxy (like `https://api.z.ai/api/anthropic`), add the model flag:
   ```bash
   # In ~/.pr-review-cli/.env
   CLAUDE_CLI_FLAGS=--model opus -p --output-format json
   ```

**If using official Anthropic API:**
1. Ensure `ANTHROPIC_BASE_URL` is `https://api.anthropic.com` in `~/.claude/settings.json`
2. Remove any custom model flags from `CLAUDE_CLI_FLAGS`:
   ```bash
   # In ~/.pr-review-cli/.env
   CLAUDE_CLI_FLAGS=-p --output-format json
   ```

**Test your configuration:**
```bash
echo "test" | claude -p --output-format json
```

If this returns a JSON object (not an error), your setup is correct.

## Known Limitations

### Bitbucket API Bug: Missing Pull Requests

**Issue**: Due to a confirmed bug in Bitbucket Cloud's API, the tool may occasionally miss pull requests where you are listed as a reviewer.

**Technical Details**:
- The Bitbucket API query parameter `reviewers.uuid="YOUR_UUID"` is documented but **does not work reliably**
- Some PRs are mysteriously absent from query results even though:
  - The PR exists and is OPEN
  - You ARE in the reviewers array with the exact UUID
  - The PR can be fetched directly by ID
- This is a **known Bitbucket Cloud API bug** affecting multiple tools

**Evidence**:
- [BCLOUD-20706](https://jira.atlassian.com/browse/BCLOUD-20706) - Official Atlassian JIRA bug for UUID-related API issues
- [Community Discussion](https://community.developer.atlassian.com/t/how-to-find-all-pull-requests-on-which-i-am-a-reviewer/34704) - Users confirm reviewer filters return incomplete results
- [Renovate Bot Issues](https://github.com/renovatebot/renovate/issues/14716) - Popular dependency bot struggles with same bug

**Impact**:
- Most users will not notice this issue
- When it occurs, 1-2 PRs may be missing from results
- The issue is **intermittent** and PR-specific

**Workaround**:
If you suspect missing PRs, you can verify manually:
```bash
# Compare with Bitbucket web UI
# 1. Go to: https://bitbucket.org/<workspace>/<repo>/pull-requests
# 2. Filter by "Reviewer: Me"
# 3. Check if any PRs are missing from CLI output
```

**Future Fix**:
We are monitoring for Bitbucket API fixes and will implement a fallback mechanism (fetching all PRs and filtering client-side) once the issue is resolved or if community demand increases.

**Status**: documented, monitoring for API fixes

## Requirements

- Python 3.11+
- Bitbucket API Token
- Claude CLI installation
- Active internet connection

## Authentication

This tool uses Bitbucket API Tokens for authentication:

1. **Create API Token** at: https://bitbucket.org/account/settings/app-passwords/
2. **Required Permissions**:
   - ✅ Pull requests: Read
   - ✅ Repositories: Read
   - ✅ Account: Read (optional)
3. **Configure** your `.env` file with the email and API Token

API Tokens are:
- **Secure**: Works over HTTPS with proper authentication
- **Simple**: No token expiration or refresh needed
- **Recommended**: Bitbucket's official recommendation for script/API access

## File Locations

```
~/.pr-review-cli/              # Config directory (auto-created)
├── .env                       # Your credentials ⚠️ NEVER commit
├── prompts/                   # Custom AI prompts
│   └── default.md            # Edit this to customize analysis
├── cache/                     # Cached data
│   ├── git_repos/            # Cloned repos for --local-diff mode
│   │   └── workspace/        # Bare git repositories
│   └── author_history.json   # Author PR tracking

~/projects/pr-review-cli/      # Project directory (if installed from source)
├── .env.example               # Example template
└── .gitignore                 # Ignores .env files ✅
```

## Security

- `.env` file has permissions `600` (owner read/write only)
- `.gitignore` prevents committing credentials
- Stored in home directory, not project directory
- API Tokens are secure and recommended by Bitbucket

## Advanced Features

### Local Git Diff Mode vs API Mode

The tool supports two modes for fetching PR diffs:

| Feature | API Mode (Default) | Local Git Mode (`--local-diff`) |
|---------|-------------------|--------------------------------|
| **Setup time** | ~1 second | 10 seconds - 5 minutes (first clone) |
| **Diff size limit** | 50K characters (larger PRs skipped) | ♾️ No limit - analyze PRs of any size |
| **Rate limits** | Yes (Bitbucket API limits) | No (after cloning) |
| **Disk usage** | ~0 MB | 100 MB - 10 GB (cached repos) |
| **Offline capable** | No (requires internet) | Yes (after initial clone) |
| **Best for** | Quick daily reviews, small PRs | Large PRs, bulk analysis, offline work |
| **Network usage** | Low (diffs only) | High (full clone first time) |

#### API Mode (Default)

```bash
pr-review review workspace repo
```

**Pros:**
- ⚡ Faster for small/medium PRs (< 50K chars)
- 💾 No disk usage (doesn't cache repos)
- 🌐 Works with read-only API access
- 🔁 Can fetch multiple PRs in parallel via API

**Cons:**
- 🚫 Skips PRs larger than 50K characters
- ⏱️ Subject to API rate limits
- 📡 Requires internet connection

#### Local Git Mode

```bash
pr-review review workspace repo --local-diff
```

**Pros:**
- 🔓 **Analyze PRs of ANY size** - no 50K character limit!
- 🚫 No API rate limits for diffs
- ✈️ Works offline after initial clone
- 💨 Faster for repeated reviews (cached repos)
- 📊 Full repository context available

**Cons:**
- 🐌 Slower initial setup (must clone repo)
- 💾 Uses disk space for cached repos
- 🔧 Requires git installation
- 🔑 Needs SSH/HTTPS access to repos

#### Cache Management

Local git repositories are cached in `~/.pr-review-cli/cache/`:

```bash
# Clean stale cached repositories before running
pr-review review workspace --local-diff --cleanup-git-cache

# Manually view cache size
du -sh ~/.pr-review-cli/cache/

# Manually clear all cached repos (start fresh)
rm -rf ~/.pr-review-cli/cache/*
```

The cache includes:
- Cloned repositories (one per repo you've reviewed)
- Author PR history (for scoring)
- Automatic cleanup of repos older than 30 days

### Workspace-Wide Search

Search ALL repositories in your workspace at once:

```bash
pr-review review myworkspace
```

This finds every PR where you're listed as a reviewer across all repos in the workspace.

### Smart Response Filtering

Only shows PRs you have **NOT yet responded to**. Automatically filters out PRs where you've clicked "Approve" or "Decline".

### Author Tracking

The system tracks author PR history locally to identify experienced contributors over time, improving scoring accuracy.

### Parallel Processing

Analyzes multiple PRs concurrently (3 at a time) for faster results.

## Development

### Running from Source

```bash
cd ~/projects/pr-review-cli
poetry install
poetry run pr-review review workspace repo
```

### Running Tests

```bash
poetry run pytest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the [AGENTS.md](AGENTS.md) file for technical details
3. Open an issue on GitHub

---

**Streamline your code review workflow with AI-powered insights!** 🚀

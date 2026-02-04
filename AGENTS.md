# PR Review CLI - Developer & Agent Knowledge

This document contains comprehensive knowledge for AI agents and developers working on the pr-review-cli codebase.

## Project Overview

PR Review CLI is a sophisticated CLI tool that:
- Fetches Bitbucket PRs where the user is a reviewer
- Analyzes PR diffs using Claude AI
- Prioritizes PRs by risk and importance
- Presents results in interactive TUI or static reports

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    pr-review-cli                         │
├─────────────────────────────────────────────────────────┤
│  Bitbucket Client → Claude Analyzer → Priority Scorer   │
│       ↓                    ↓                  ↓          │
│  Fetch PRs          AI Analysis      Risk Calculation   │
│                                         ↓                │
│                           Presenters (TUI + Reports)     │
└─────────────────────────────────────────────────────────┘
```

## File Structure

```
~/projects/pr-review-cli/
├── pr_review/
│   ├── __init__.py
│   ├── main.py                    # Entry point, CLI parsing
│   ├── config.py                  # Configuration management
│   ├── models.py                  # Data models - Pydantic
│   ├── bitbucket_client.py        # Bitbucket API integration (Basic Auth)
│   ├── claude_analyzer.py         # Claude CLI integration
│   ├── priority_scorer.py         # Risk scoring logic
│   ├── git_diff_manager.py        # Local git diff management
│   ├── presenters/
│   │   ├── __init__.py
│   │   ├── interactive_tui.py     # Textual TUI interface
│   │   └── report_generator.py    # Static report generation
│   └── utils/
│       ├── __init__.py
│       ├── paths.py               # Path management utilities
│       └── git_operations.py      # Git command wrappers
├── tests/
│   ├── __init__.py
│   └── test_priority_scorer.py
├── pyproject.toml                 # Dependencies & Poetry config
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore patterns
├── README.md                      # User documentation
└── AGENTS.md                      # This file
```

~/.pr-review-cli/                  # User config directory (auto-created)
├── .env                           # API Token credentials (gitignored)
├── prompts/                       # AI prompt templates
│   └── default.md                # Edit to customize AI analysis
└── cache/                         # Cached data
    ├── git_repos/                # Cloned repositories (for --local-diff mode)
    │   └── workspace/            # Bare git repositories
    └── author_history.json       # Author PR history cache
```

## Core Components

### 1. BitbucketClient (`bitbucket_client.py`)

**Purpose:** Async HTTP client for Bitbucket API using API Token authentication

**Key Features:**
- Basic authentication using API Tokens
- Supports workspace-wide PR search
- Supports repository-specific PR search
- Fetches PR diffs with statistics
- Handles rate limiting and errors

**API Endpoints Used:**
```
# Workspace-wide search
GET /repositories/{workspace}/pullrequests?q=reviewers.uuid="{uuid}"

# Repository-specific search
GET /repositories/{workspace}/{repo_slug}/pullrequests?q=reviewers.uuid="{uuid}"

# Get PR diff
GET /repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff

# Get single PR by ID
GET /repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}

# Get user info
GET /user
```

**Key Methods:**
- `fetch_prs_assigned_to_me(workspace, repo_slug, user_uuid, user_username)` - Fetch PRs (workspace-wide or repo-specific)
- `get_pr_diff(workspace, repo_slug, pr_id)` - Get PR diff with stats
- `get_single_pr(workspace, repo_slug, pr_id)` - Fetch a single PR by ID
- `get_current_user()` - Auto-detect current user
- `fetch_prs_and_diffs(...)` - Fetch PRs and diffs together (parallel)

**Smart Response Filtering:**
- Only fetches PRs where user has NOT responded (no Approve/Decline)
- Query parameter: `state="OPEN"` + filters on response status

### 2. ClaudeAnalyzer (`claude_analyzer.py`)

**Purpose:** Analyzes PR diffs using existing Claude CLI installation

**Key Features:**
- Integrates with Claude CLI via subprocess
- Handles large PRs (>50K chars) intelligently
- Parallel processing with semaphore (3 concurrent)
- Robust error handling and timeouts

**Key Methods:**
- `analyze_pr(pr, diff_content)` - Analyze single PR
- `analyze_prs_parallel(prs_with_diffs)` - Batch analysis
- `_load_default_prompt()` - Load prompt from `~/.pr-review-cli/prompts/default.md`

**Large PR Handling:**
- PRs > 50,000 characters skip AI analysis
- Returns special result: `{"skipped": True, "reason": "diff_too_large"}`
- These PRs get automatic high priority (90-100 points)

**Prompt Configuration:**
- Loads prompt from `~/.pr-review-cli/prompts/default.md`
- If file doesn't exist, creates it with built-in default prompt
- Supports optional YAML frontmatter (name, description, version)
- Edit the file to customize the AI analysis prompt
- No CLI options needed - changes take effect on next run

**Prompt Template Placeholders:**
- `{title}` - PR title
- `{author}` - PR author
- `{source}` - Source branch
- `{destination}` - Destination branch
- `{diff}` - Diff content

**Expected JSON Response:**
```json
{
  "good_points": ["Well-implemented pattern"],
  "attention_required": ["Bug found"],
  "risk_factors": ["Breaking change"],
  "overall_quality_score": 85,
  "estimated_review_time": "30 minutes"
}
```

### 3. PriorityScorer (`priority_scorer.py`)

**Purpose:** Calculates risk scores (0-100) for PRs

**Scoring Factors (Total: 155 points possible, capped at 100):**

1. **Size Factor** (0-25 points)
   - > 1000 lines: 25 pts
   - > 500 lines: 15 pts
   - > 100 lines: 5 pts
   - ≤ 100 lines: 0 pts

2. **PR Age Factor** (0-25 points)
   - Formula: `(min(days, 5) / 5) × 25`
   - Max age considered: 5 days (prevents extreme bias)
   - Prevents bottlenecks where old PRs are neglected

3. **File Type Risk** (0-20 points)
   - Database files (`.sql`, `migration`, `schema`): 5 pts each
   - Config files (`config`, `.env`, `credentials`): 5 pts each
   - Security files (`auth`, `permission`, `role`): 5 pts each
   - Max 20 points

4. **Author Experience** (0-15 points)
   - < 10 PRs: 15 pts (new contributor)
   - < 50 PRs: 8 pts
   - ≥ 50 PRs: 0 pts (experienced)

5. **AI Quality Assessment** (0-40 points)
   - Formula: `(100 - quality_score) × 0.4`
   - Lower quality = higher priority

6. **Attention Required Items** (0-20 points)
   - 4 points per item (max 20 for 5+ items)

7. **Risk Factors** (0-10 points)
   - 2 points per risk factor (max 10 for 5+ factors)

**Special Case: Large PRs (AI skipped)**
- Base score: 90 points
- > 100k characters: 100 points (maximum)
- Marked as "MANUAL REVIEW REQUIRED"

**Risk Level Classification:**
- **CRITICAL** (70-100): Review immediately
- **HIGH** (50-69): Review soon
- **MEDIUM** (30-49): Review when possible
- **LOW** (0-29): Review at leisure

**Caching:**
- Author history cached in `~/.pr-review-cli/cache/author_history.json`
- Updated after each review run
- Helps identify experienced contributors over time

### 4. LocalGitDiffManager (`git_diff_manager.py`)

**Purpose:** Manages local git repository caching and diff generation

**Key Features:**
- Clones and caches Bitbucket repositories locally
- Generates diffs using git (bypasses API rate limits)
- Handles both SSH and HTTPS authentication
- Automatic cleanup of stale repositories
- Metadata tracking for cache management

**Key Methods:**
- `get_pr_diff_local(workspace, repo_slug, pr_id, source_branch, destination_branch)` - Generate diff from local repo
- `cleanup_stale_repos()` - Remove old or oversized cached repos
- `_ensure_repo_cloned(workspace, repo_slug)` - Ensure repo is cloned and up-to-date

**Cache Location:** `~/.pr-review-cli/cache/git_repos/workspace/`

### 5. GitOperations (`utils/git_operations.py`)

**Purpose:** Async subprocess wrapper for git commands

**Key Features:**
- Async git command execution with timeout handling
- Shallow clone support with fallback to full clone
- Multiple diff syntax fallbacks for complex histories
- Bare repository management

**Key Methods:**
- `clone_repo(remote_url, target_path, shallow=True)` - Clone repository
- `fetch_branches(repo_path)` - Fetch all branches in bare repo
- `get_diff(repo_path, source_branch, destination_branch)` - Generate unified diff
- `verify_git_available()` - Check if git is installed

### 6. Config (`config.py`)

**Purpose:** Configuration management with environment variable validation

**Priority Order (highest to lowest):**
1. `~/.pr-review-cli/.env` (Primary - recommended)
2. `.env` (current directory - for development/override)
3. Environment variables (Legacy support)

**Required Variables:**
- `PR_REVIEWER_BITBUCKET_EMAIL` - Bitbucket email for authentication
- `PR_REVIEWER_BITBUCKET_API_TOKEN` - API Token for authentication
- `PR_REVIEWER_BITBUCKET_WORKSPACE` - Default workspace (optional but recommended)

**Optional Variables:**
- `PR_REVIEWER_BITBUCKET_USER_UUID` - Cached user UUID (auto-populated)
- `CLAUDE_CLI_COMMAND` - Command to invoke Claude CLI (default: "claude")
- `CLAUDE_CLI_FLAGS` - Flags for JSON output (default: "-p --output-format json")
- `BITBUCKET_BASE_URL` - API base URL
- `CACHE_DIR` - Cache directory path
- `PR_REVIEWER_GIT_USE_SSH` - Use SSH for git operations (default: "true")
- `PR_REVIEWER_GIT_CACHE_MAX_AGE` - Git cache max age in days before cleanup (default: "30")
- `PR_REVIEWER_GIT_CACHE_MAX_SIZE` - Git cache max size in GB before cleanup (default: "5.0")
- `PR_REVIEWER_GIT_TIMEOUT` - Git command timeout in seconds (default: "300")

**Note:** This app assumes you're using Claude Code CLI (https://claude.ai/code). The flags `-p --output-format json` are automatically added to the command.

**Key Methods:**
- `has_valid_credentials` - Check if valid credentials exist
- `_print_credentials_warning()` - Print helpful setup message

### 7. Models (`models.py`)

**Pydantic Models:**
- `BitbucketPR` - Raw PR data from Bitbucket API
- `PRDiff` - PR diff with statistics
- `PRAnalysis` - AI analysis results
  - `_skipped_reason` - Optional: Reason for skipping analysis ("diff_too_large", "timeout", "user_requested")
  - `_diff_size` - Optional: Character count of diff (for logging/tracking)
- `PRWithPriority` - PR with priority score and risk level
- `UserInfo` - User information from Bitbucket

### 8. InteractiveTUI (`presenters/interactive_tui.py`)

**Purpose:** Textual-based interactive terminal UI

**Key Features:**
- Split-panel layout (PR list + details)
- Color-coded risk levels
- Keyboard shortcuts (j/k, Enter, o, q)
- Quick browser open
- Repository column (for workspace-wide search)

**Keyboard Shortcuts:**
- `↑/↓` or `j/k`: Navigate PRs
- `Enter`: View full details
- `o`: Open PR in browser
- `q`: Quit

### 9. ReportGenerator (`presenters/report_generator.py`)

**Purpose:** Generate static reports in multiple formats

**Output Formats:**
- Terminal (Rich panels with color coding)
- Markdown (formatted with sections)
- JSON (structured data export)

**Features:**
- Risk-level grouping
- Repository information (for workspace-wide search)
- Priority score display
- Statistical summary

### 10. Main CLI (`main.py`)

**Purpose:** Entry point and CLI orchestration

**Commands:**
- `review [workspace] [repo]` - Fetch and analyze PRs
- `cache-stats` - Show author history statistics

**CLI Options:**
- `--pr-url URL` - Analyze a single PR from its Bitbucket URL (auto non-interactive)
- `--skip-analyze` - Skip AI analysis and show PR summary only (faster, no API costs)
- `--interactive/--no-interactive, -i/-I` - Enable/disable TUI mode (default: enabled)
- `--export {terminal,markdown,json}, -e` - Export format
- `--output FILE, -o` - Output filename (for markdown/json)
- `--max-prs N, -m` - Limit number of PRs (default: 30)
- `--local-diff/--api-diff` - Use local git cloning vs API for diffs
- `--cleanup-git-cache` - Clean stale cached repositories before running (requires --local-diff)
- `--use-https` - Use HTTPS instead of SSH for git operations (requires --local-diff)

**Workflow:**
1. Validate configuration
2. Fetch PRs (workspace-wide or repo-specific)
3. Fetch diffs in parallel
4. Analyze with Claude (3 concurrent)
5. Calculate priority scores
6. Present results (TUI or report)

## Authentication

This tool uses Bitbucket API Tokens for authentication.

### Setup

1. **Create API Token**
   - Go to: https://bitbucket.org/account/settings/api-tokens/
   - Create a new API Token
   - Select permissions:
     - Pull requests: Read
     - Repositories: Read
     - Account: Read (optional)

2. **Configure `.env`**
   - Add email and API Token to `~/.pr-review-cli/.env`
   - No helper scripts needed

### Security

- `.env` file has permissions `600` (owner read/write only)
- `.gitignore` prevents committing credentials
- Stored in home directory, not project directory
- API Tokens are officially recommended by Bitbucket for script/API access

## Workspace-Wide Search Feature

**Feature:** Search ALL repos in workspace for PRs assigned to you

**Usage:**
```bash
# Search all repos
pr-review review myworkspace

# Search specific repo
pr-review review myworkspace myrepo
```

**Implementation:**
- When `repo_slug` is `None`, uses workspace-wide endpoint
- Extracts repository info from each PR response
- Displays repository column in TUI and reports

**Benefits:**
- See entire review workload at once
- Prioritize across all projects
- No need to check each repo individually

## Performance Optimizations

- ✅ Parallel PR fetching (asyncio)
- ✅ Concurrent diff retrieval (asyncio)
- ✅ Parallel Claude analysis (3 concurrent via semaphore)
- ✅ Smart diff truncation for large PRs
- ✅ Local caching for author history
- ✅ Rate limiting and retry logic

## Error Handling

- ✅ Missing credentials with helpful setup instructions
- ✅ Repository not found errors
- ✅ Authentication failures (with API Token verification guidance)
- ✅ Timeout handling (Claude analysis, HTTP requests)
- ✅ JSON parsing failures with fallback
- ✅ Claude CLI not found detection
- ✅ Large PR handling (skips gracefully)

## Dependencies

**Core:**
- `httpx` - Async HTTP client
- `pydantic` - Data validation
- `python-dotenv` - Environment variables
- `rich` - Terminal formatting
- `textual` - TUI framework
- `typer` - CLI framework
- `python-frontmatter` - Markdown parsing

**Development:**
- `pytest` - Testing
- `pytest-asyncio` - Async test support
- `poetry` - Dependency management

## Publishing to PyPI

### Prerequisites

1. PyPI account and API token
2. Poetry configured with token

### Workflow

```bash
# 1. Update version in pyproject.toml
poetry version patch  # or minor, or major

# 2. Build the package
poetry build

# 3. Test on TestPyPI (optional)
poetry publish --repository testpypi

# 4. Publish to PyPI
poetry publish

# 5. Verify
pip install pr-review-cli
```

### Important Notes

- Version numbers must increment
- Once published, cannot delete (only yank)
- Check package name availability first
- Use TestPyPI for testing first

## Development Workflow

### Local Development

```bash
# Install dependencies
poetry install

# Run CLI
poetry run pr-review review workspace repo

# Run tests
poetry run pytest

# Check formatting
poetry run black --check pr_review/
poetry run flake8 pr_review/
```

### Adding New Features

1. Update relevant module in `pr_review/`
2. Add tests to `tests/`
3. Update documentation
4. **Test with `./run.sh review --skip-analyze -I` before asking user to verify**
5. Commit with conventional commit message

**Important:** Always test using `--skip-analyze -I` flags to:
- Skip AI analysis (faster iteration)
- Use non-interactive mode (easier to verify output)
- Quickly validate functionality before involving the user

### Debugging

**IMPORTANT - Always use these flags for fast development iteration:**
- `--skip-analyze` - Skip AI analysis (default for ALL debugging)
- `--no-interactive` / `-I` - Use terminal output instead of TUI

**Why these flags?**
- AI analysis is slow and costs API credits - skip unless debugging the analyzer
- TUI prevents seeing terminal output and makes it harder to spot errors
- Non-interactive mode shows structured output that's easy to verify

```bash
# QUICK DEBUGGING (Recommended for 95% of development)
# Skip AI, use terminal output - fastest iteration
poetry run pr-review review workspace repo --skip-analyze -I

# Or use the helper script if available
./run.sh review --skip-analyze -I

# DEBUGGING AI ANALYZER ONLY (use only when testing Claude integration)
# Remove --skip-analyze to test AI analysis
poetry run pr-review review workspace repo -I

# DEBUGGING WITH LOGS
# Enable debug logging for verbose output
export PR_REVIEW_DEBUG=1
poetry run pr-review review workspace repo --skip-analyze -I

# DEBUGGING SPECIFIC MODULES
# Test single PR from URL (no workspace/repo args needed)
poetry run pr-review review --pr-url https://bitbucket.org/workspace/repo/pull-requests/123 --skip-analyze -I

# Test local diff mode (git cloning)
poetry run pr-review review workspace repo --local-diff --skip-analyze -I

# Limit PRs for faster testing
poetry run pr-review review workspace repo -m 5 --skip-analyze -I

# DEBUGGING CLI OUTPUT
# Test export formats
poetry run pr-review review workspace repo --skip-analyze -I --export markdown
poetry run pr-review review workspace repo --skip-analyze -I --export json
```

**Debugging Checklist:**
1. **Most changes**: Use `--skip-analyze -I` - validates API calls, scoring, presenters
2. **Analyzer changes only**: Remove `--skip-analyze`, keep `-I`
3. **TUI changes only**: Remove `-I`, keep `--skip-analyze`
4. **Full integration**: Remove both flags (slowest, use sparingly)

## Testing

### Quick Workflow Testing
**Before asking the user to verify changes, always run:**
```bash
# Fastest iteration (recommended for 95% of changes)
./run.sh review --skip-analyze -I

# Or using poetry directly
poetry run pr-review review workspace repo --skip-analyze -I
```

This command:
- ✅ Skips AI analysis (fast iteration)
- ✅ Uses non-interactive mode (easy to verify)
- ✅ Shows actual output (can verify functionality)
- ✅ Tests real API calls (validates integration)
- ✅ Tests scoring, filtering, and report generation

**When to use AI analysis in testing:**
```bash
# Only when debugging ClaudeAnalyzer changes specifically
poetry run pr-review review workspace repo -I

# For single PR AI testing
poetry run pr-review review --pr-url https://bitbucket.org/workspace/repo/pull-requests/123 -I
```

**When to use TUI in testing:**
```bash
# Only when debugging InteractiveTUI changes specifically
poetry run pr-review review workspace repo --skip-analyze
```

### Unit Tests
Current test coverage:
- `tests/test_priority_scorer.py` - Priority scoring logic

Recommended additions:
- Test BitbucketClient with mock API
- Test Config validation
- Test ClaudeAnalyzer with mock Claude CLI
- Integration test for full workflow

## Troubleshooting

### Common Issues

**Credentials not found:**
```bash
# Check .env exists
ls -la ~/.pr-review-cli/.env

# Verify contents
cat ~/.pr-review-cli/.env
```

**Permission denied:**
- Check API Token has required permissions
- Create new API Token with: Pull requests (Read), Repositories (Read)

**Claude CLI not found:**
```bash
# Specify custom path
export CLAUDE_CLI_COMMAND=/path/to/claude
```

**Large PRs timing out:**
- These are automatically handled with high priority
- Consider increasing timeout in `claude_analyzer.py`

### Verification

```python
# Check configuration
python3 -c "
from pr_review.config import Config
config = Config()
print('Has credentials:', config.has_valid_credentials)
print('Email:', config.bitbucket_email)
print('Workspace:', config.bitbucket_workspace)
"
```

## Key Design Decisions

1. **API Token Authentication** - Simple, secure, recommended by Bitbucket for scripts
2. **Claude CLI Integration** - No separate API keys needed, uses existing setup
3. **Workspace-Wide Search** - More convenient than per-repo commands
4. **Parallel Processing** - Significantly faster analysis
5. **Local Caching** - Improves author history tracking over time
6. **Large PR Handling** - Graceful degradation instead of failure
7. **Multiple Output Formats** - Flexibility for different workflows

## Future Enhancements

Potential improvements:
- [ ] Add GitHub support (currently Bitbucket-only)
- [ ] GitLab integration
- [ ] PR filtering by label/milestone
- [ ] PR comments integration
- [ ] Web dashboard
- [ ] PR summarization (TL;DR)
- [ ] Code snippet extraction for issues
- [ ] Team statistics and metrics
- [ ] Slack/Teams integration
- [ ] Auto-approve low-risk PRs (with safeguards)

## Maintenance

### Regular Tasks

- Update dependencies: `poetry update`
- Review and merge PRs
- Monitor for deprecated API usage
- Update documentation as features change

### Security Considerations

- Rotate API Tokens periodically
- Keep dependencies updated
- Monitor Bitbucket API changes
- Never commit `.env` files
- Use `.gitignore` to protect credentials

---

**This knowledge base should help any agent or developer understand and work on the pr-review-cli codebase effectively!**

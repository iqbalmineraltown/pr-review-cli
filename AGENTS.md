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
│   ├── prompt_loader.py           # Custom prompt/skills loader
│   ├── presenters/
│   │   ├── __init__.py
│   │   ├── interactive_tui.py     # Textual TUI interface
│   │   └── report_generator.py    # Static report generation
│   └── utils/
│       ├── __init__.py
│       └── paths.py               # Path management utilities
├── tests/
│   ├── __init__.py
│   └── test_priority_scorer.py
├── pyproject.toml                 # Dependencies & Poetry config
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore patterns
└── README.md                      # User documentation
```

~/.pr-review-cli/                  # User config directory (auto-created)
├── .env                           # API Token credentials (gitignored)
├── prompts/                       # Custom analysis prompts
│   ├── default.md                 # Auto-created
│   ├── security-focused.md
│   ├── performance-review.md
│   └── quick-scan.md
└── cache/                         # Cached data
    └── author_history.json        # Author PR history cache
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore patterns
├── README.md                      # User documentation
└── AGENTS.md                      # This file

~/.pr-review-cli/                  # User config directory (auto-created)
├── .env                           # API Token credentials (gitignored)
├── prompts/                       # Custom analysis prompts
│   ├── default.md                 # Auto-created
│   ├── security-focused.md
│   ├── performance-review.md
│   └── quick-scan.md
└── cache/                         # Cached data
    └── author_history.json        # Author PR history cache
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

# Get user info
GET /user
```

**Key Methods:**
- `fetch_prs_assigned_to_me(workspace, repo_slug=None)` - Fetch PRs (workspace-wide or repo-specific)
- `get_pr_diff(workspace, repo_slug, pr_id)` - Get PR diff with stats
- `get_authenticated_user()` - Auto-detect current user

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
- `analyze_pr(pr, diff_content, prompt_template)` - Analyze single PR
- `analyze_prs_parallel(prs_with_diffs, prompt_template)` - Batch analysis

**Large PR Handling:**
- PRs > 50,000 characters skip AI analysis
- Returns special result: `{"skipped": True, "reason": "diff_too_large"}`
- These PRs get automatic high priority (90-100 points)

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

### 4. PromptLoader (`prompt_loader.py`)

**Purpose:** Loads and manages custom analysis prompts

**Key Features:**
- Loads prompts from `~/.pr-review-cli/prompts/`
- Auto-creates default prompt if missing
- Supports frontmatter metadata
- Validates prompt placeholders

**Frontmatter Format:**
```yaml
---
name: "Security Focused Review"
description: "Focuses on security vulnerabilities and best practices"
version: "1.0"
---

Prompt content here...
```

**Key Methods:**
- `load_prompt(prompt_name)` - Load specific prompt
- `list_prompts()` - List all available prompts
- `_create_default_prompt()` - Auto-create default prompt

### 5. Config (`config.py`)

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
- `CLAUDE_CLI_PATH` - Path to Claude CLI (default: "claude")
- `BITBUCKET_BASE_URL` - API base URL
- `CACHE_DIR` - Cache directory path

**Key Methods:**
- `has_valid_credentials` - Check if valid credentials exist
- `_print_credentials_warning()` - Print helpful setup message

### 6. Models (`models.py`)

**Pydantic Models:**
- `BitbucketPR` - Raw PR data from Bitbucket API
- `PRDiff` - PR diff with statistics
- `PRAnalysis` - AI analysis results
- `PRWithPriority` - PR with priority score and risk level
- `UserInfo` - User information from Bitbucket

### 7. InteractiveTUI (`presenters/interactive_tui.py`)

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

### 8. ReportGenerator (`presenters/report_generator.py`)

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

### 9. Main CLI (`main.py`)

**Purpose:** Entry point and CLI orchestration

**Commands:**
- `review [workspace] [repo]` - Fetch and analyze PRs
- `prompts --list` - List available custom prompts
- `cache-stats` - Show author history statistics

**CLI Options:**
- `--no-interactive` - Disable TUI, use static report
- `--export {terminal,markdown,json}` - Export format
- `--output FILE` - Output filename (for markdown/json)
- `--prompt NAME` - Use custom prompt
- `-m, --max-count N` - Limit number of PRs

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

 Work

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

```bash
# Enable debug logging
export PR_REVIEW_DEBUG=1

# Run with verbose output
poetry run pr-review review workspace repo --verbose
```

## Testing

### Quick Workflow Testing
**Before asking the user to verify changes, always run:**
```bash
./run.sh review --skip-analyze -I
```

This command:
- ✅ Skips AI analysis (fast iteration)
- ✅ Uses non-interactive mode (easy to verify)
- ✅ Shows actual output (can verify functionality)
- ✅ Tests real API calls (validates integration)

### Unit Tests
Current test coverage:
- `tests/test_priority_scorer.py` - Priority scoring logic

Recommended additions:
- Test BitbucketClient with mock API
- Test PromptLoader with various prompts
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
export CLAUDE_CLI_PATH=/path/to/claude
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
8. **Custom Prompts** - Adaptability to team-specific needs

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

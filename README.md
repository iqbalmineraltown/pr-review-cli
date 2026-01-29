# PR Review CLI

AI-powered pull request review assistant for Bitbucket.

## Features

- 🤖 **AI-Powered Analysis**: Uses Claude to analyze PR diffs and extract insights
- 🎯 **Smart Prioritization**: Automatically ranks PRs by risk and importance
- 📊 **Interactive TUI**: Beautiful terminal UI for navigating PRs
- 📝 **Multiple Export Formats**: Terminal, Markdown, and JSON reports
- ⚡ **Parallel Processing**: Analyzes multiple PRs concurrently
- 🎨 **Custom Prompts**: Create your own analysis prompts
- 🔍 **Large PR Handling**: Intelligently handles PRs too large for AI analysis

## Installation

```bash
cd ~/projects/pr-review-cli
poetry install
```

## Configuration

Set up your Bitbucket API token:

```bash
export PR_REVIEWER_BITBUCKET_ACCESS_TOKEN=your_api_token_here
export PR_REVIEWER_BITBUCKET_USERNAME=your_username  # Optional but recommended
```

To create a Bitbucket API Token:
1. Go to: https://bitbucket.org/account/settings/api-tokens/
2. Create a new OAuth consumer with these scopes:
   - `pullrequest:read` (required)
   - `account:read` (optional - for displaying your name)
3. Copy the token immediately
4. Set the environment variable

For persistence, add to your `~/.bashrc` or `~/.zshrc`:

```bash
echo 'export PR_REVIEWER_BITBUCKET_ACCESS_TOKEN=your_token' >> ~/.bashrc
echo 'export PR_REVIEWER_BITBUCKET_USERNAME=your_username' >> ~/.bashrc
```

## Usage

### Interactive Review (Default)

```bash
pr-review review myworkspace myrepo
```

### Non-Interactive with Export

```bash
pr-review review myworkspace myrepo --no-interactive --export markdown --output daily_report
```

### Limit PRs

```bash
pr-review review myworkspace myrepo -m 10
```

### Use Custom Prompt

```bash
pr-review review myworkspace myrepo --prompt security-focused
```

## Commands

- `pr-review review <workspace> <repo>`: Fetch and analyze PRs
- `pr-review prompts --list`: List available custom prompts
- `pr-review cache-stats`: Show author history statistics

## Custom Prompts

Create custom analysis prompts by adding markdown files to `~/.pr-review-cli/prompts/`:

```bash
~/.pr-review-cli/prompts/
├── default.md
├── security-focused.md
├── performance-review.md
└── quick-scan.md
```

Each prompt file should use these placeholders:
- `{title}`: PR title
- `{author}`: PR author
- `{source}`: Source branch
- `{destination}`: Destination branch
- `{diff}`: Diff content

Response must be valid JSON with these fields:
- `good_points`: Array of well-implemented aspects
- `attention_required`: Array of issues needing review
- `risk_factors`: Array of potential problems
- `overall_quality_score`: Score from 0-100
- `estimated_review_time`: Time estimate string

## Priority Levels

- **CRITICAL** (70+): Breaking changes, security issues, large refactorings
- **HIGH** (50-69): Core logic changes, database migrations
- **MEDIUM** (30-49): Feature additions, bug fixes
- **LOW** (0-29): Documentation, tests, minor tweaks

## Interactive TUI Shortcuts

- `↑/↓` or `j/k`: Navigate PRs
- `Enter`: View details
- `o`: Open PR in browser
- `q`: Quit

## Requirements

- Python 3.11+
- Bitbucket App Password
- Claude CLI installation
- Active internet connection

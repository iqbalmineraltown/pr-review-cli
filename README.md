# PR Review CLI

AI-powered pull request review assistant for Bitbucket.

## Features

- 🤖 **AI-Powered Analysis**: Uses Claude to analyze PR diffs and extract insights
- 🎯 **Smart Prioritization**: Automatically ranks PRs by risk and importance
- 📊 **Interactive TUI**: Beautiful terminal UI for navigating PRs
- 🌐 **Web Interface**: Modern Vue.js browser interface with real-time updates
- 📝 **Multiple Export Formats**: Terminal, Markdown, and JSON reports
- ⚡ **Parallel Processing**: Analyzes multiple PRs concurrently
- 🎨 **Custom Prompts**: Create your own analysis prompts
- 🔍 **Large PR Handling**: Intelligently handles PRs too large for AI analysis
- 🔐 **API Token Authentication**: Secure authentication using Bitbucket API Tokens
- 🌐 **Workspace-Wide Search**: Search all repos in your workspace at once
- ⏰ **Age-Based Prioritization**: Older PRs get higher priority to prevent bottlenecks
- 🔄 **Real-Time Progress**: Watch analysis progress via WebSocket
- 🎨 **Syntax Highlighting**: Code diffs with Prism.js highlighting

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

1. Go to: https://bitbucket.org/account/settings/app-passwords/
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
# Path to Claude CLI (default: "claude")
CLAUDE_CLI_PATH=/custom/path/to/claude

# Bitbucket API base URL (default: https://api.bitbucket.org/2.0)
BITBUCKET_BASE_URL=https://api.bitbucket.org/2.0

# Cache directory (default: ~/.pr-review-cli/cache)
CACHE_DIR=/custom/cache/directory
```

## Usage

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
pr-review review myworkspace --no-interactive --export markdown --output daily_report

# Generate JSON report
pr-review review myworkspace --no-interactive --export json --output pr_data.json

# Terminal output only
pr-review review myworkspace --no-interactive --export terminal
```

### Limit PRs

```bash
pr-review review myworkspace -m 10
```

### Use Custom Prompt

```bash
pr-review review myworkspace --prompt security-focused
```

### List Available Prompts

```bash
pr-review prompts --list
```

### View Cache Statistics

```bash
pr-review cache-stats
```

## Web Interface

The PR Review CLI now includes a modern web interface for interactive PR review through your browser!

### Starting the Web Server

```bash
# Start with default settings (http://localhost:8000)
pr-review serve

# Start on custom port
pr-review serve --port 3000

# Disable auto-reload (for production)
pr-review serve --no-reload

# Custom host and port
pr-review serve --host 0.0.0.0 --port 8080
```

The web interface provides:
- 🌐 **Modern Vue.js UI**: Beautiful, responsive interface
- 📊 **Real-Time Progress**: Watch AI analysis progress live via WebSocket
- 🔍 **Interactive Diff Viewer**: View code diffs with syntax highlighting
- 🎯 **Same Features**: All CLI features available in the browser
- ⚡ **Fast API**: RESTful API for programmatic access

### Development Workflow

**Backend (Python):**
```bash
# Terminal 1: Start FastAPI server with auto-reload
pr-review serve --reload
```

**Frontend (Vue.js):**
```bash
# Terminal 2: Start Vite dev server
cd pr-review-web && npm install && npm run dev
```

Access at: http://localhost:5173 (Vite dev server with API proxy)

**Production Build:**
```bash
# Build Vue frontend
cd pr-review-web && npm run build

# Start server (serves built Vue app)
pr-review serve --port 8000
```

### Web Interface Features

1. **Dashboard**: View all PRs with priority scores and risk levels
2. **Real-Time Analysis**: Watch Claude analyze PRs in real-time
3. **Expandable Details**: Click any PR to see full analysis and code diff
4. **Syntax Highlighting**: Diffs are highlighted with Prism.js
5. **Color-Coded Risks**: Visual risk indicators (Critical/High/Medium/Low)
6. **Bitbucket Integration**: One-click to open PRs in Bitbucket

### API Endpoints

When the web server is running, you can also use the REST API directly:

```bash
# List PRs
curl http://localhost:8000/api/prs?workspace=myworkspace

# Get PR details with diff
curl http://localhost:8000/api/prs/123?workspace=myworkspace&repo=myrepo

# Trigger analysis
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"workspace": "myworkspace", "prompt": "default"}'

# Get configuration
curl http://localhost:8000/api/config
```

### WebSocket Endpoint

Connect to the WebSocket for real-time analysis progress:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/analyze')

// Subscribe to analysis updates
ws.send(JSON.stringify({
  action: 'subscribe',
  analysis_id: 'uuid-from-analyze-endpoint'
}))

// Receive progress updates
ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  if (message.type === 'progress') {
    console.log(`${message.current}/${message.total}: ${message.status}`)
  } else if (message.type === 'complete') {
    console.log('Results:', message.results)
  }
}
```

### Web Server Configuration

Add to your `~/.pr-review-cli/.env`:

```bash
# Web server host (default: 127.0.0.1)
PR_REVIEW_WEB_HOST=127.0.0.1

# Web server port (default: 8000)
PR_REVIEW_WEB_PORT=8000

# Enable auto-reload for development (default: true)
PR_REVIEW_WEB_RELOAD=true
```

## Interactive TUI Shortcuts

- `↑/↓` or `j/k`: Navigate PRs
- `Enter`: View full details
- `o`: Open PR in browser
- `q`: Quit

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

PRs too large for AI analysis (>50K characters) automatically get:
- **Score 90-100** (maximum priority)
- Marked as "MANUAL REVIEW REQUIRED"
- Diff size logged for reference

## Custom Prompts

Create custom analysis prompts by adding markdown files to `~/.pr-review-cli/prompts/`:

```bash
~/.pr-review-cli/prompts/
├── default.md                 # Auto-created
├── security-focused.md        # Security-focused review
├── performance-review.md      # Performance analysis
└── quick-scan.md             # Fast overview
```

### Prompt Format

Each prompt file should use these placeholders:
- `{title}`: PR title
- `{author}`: PR author
- `{source}`: Source branch
- `{destination}`: Destination branch
- `{diff}`: Diff content

Example (`security-focused.md`):
```markdown
---
name: "Security Focused Review"
description: "Focuses on security vulnerabilities and best practices"
version: "1.0"
---

Analyze this pull request with a focus on security:

**PR Title**: {title}
**Author**: {author}
**Branch**: {source} → {destination}

**Diff**:
{diff}

Please identify:
1. Security vulnerabilities (SQL injection, XSS, authentication issues)
2. Sensitive data exposure (API keys, passwords, tokens)
3. Authorization issues (access control bypass)
4. Cryptographic issues (weak algorithms, hardcoded keys)
5. Dependency vulnerabilities

Respond with valid JSON:
{
  "good_points": ["Well-implemented security pattern..."],
  "attention_required": ["SQL injection vulnerability in..."],
  "risk_factors": ["Uses hardcoded credentials..."],
  "overall_quality_score": 85,
  "estimated_review_time": "45 minutes"
}
```

## Examples

### Morning Review Routine

```bash
# Check all PRs across all projects
pr-review review acme-corp --prompt quick-scan

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

### Security-Focused Review

```bash
# Security audit across all repositories
pr-review review acme-corp --prompt security-focused -m 50
```

### Performance Review

```bash
# Analyze performance implications
pr-review review acme-corp --prompt performance-review
```

## Troubleshooting

### Permission denied or "credentials lack required scopes"?

If you see errors like:
```
Your credentials lack one or more required privilege scopes.
Required: ["repository:read"]
```

This means your API Token is missing required permissions:

1. Go to: https://bitbucket.org/account/settings/app-passwords/
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
# Specify custom path
export CLAUDE_CLI_PATH=/path/to/claude
```

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
├── cache/                     # Cached data
└── prompts/                   # Custom analysis prompts

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

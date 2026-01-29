# Workspace-Wide PR Search - Feature Update

## What's New! 🎉

The PR Review CLI now supports **workspace-wide PR searches**! You can fetch ALL PRs assigned to you across ALL repositories in a workspace - no need to specify individual repositories anymore.

## Usage

### Search All Repositories in Workspace

```bash
# Fetch PRs from ALL repositories in your workspace
python3 -m pr_review.main review myworkspace

# Example
python3 -m pr_review.main review acme-corp
```

This will search across all repositories in `acme-corp` workspace and find every PR where you're listed as a reviewer.

### Search Specific Repository

```bash
# Still works! Fetch PRs from a specific repository
python3 -m pr_review.main review myworkspace myrepo

# Example
python3 -m pr_review.main review acme-corp backend-api
```

## What Changed

### 1. BitbucketClient (`bitbucket_client.py`)
- `fetch_prs_assigned_to_me()` now accepts optional `repo_slug` parameter
- When `repo_slug` is `None`, uses workspace-wide endpoint:
  - `/repositories/{workspace}/pullrequests?q=reviewers.uuid="{uuid}"`
- When `repo_slug` is specified, uses repository-specific endpoint:
  - `/repositories/{workspace}/{repo_slug}/pullrequests?q=reviewers.uuid="{uuid}"`
- Extracts repository information from each PR when searching workspace-wide
- Correctly fetches diffs from each PR's respective repository

### 2. CLI Interface (`main.py`)
- `repo` parameter is now **optional** (shown as `[REPO]` in help)
- Updated help text: "Repository name (optional - if not specified, searches all repos in workspace)"
- Dynamic status messages showing search scope

### 3. Interactive TUI (`interactive_tui.py`)
- Added "Repository" column to the PR list
- Shows repository name in detail panel
- Helpful when viewing PRs from multiple repos

### 4. Report Generator (`report_generator.py`)
- Terminal reports show repository information
- Markdown exports include repository field
- JSON exports include repository data

## Benefits

### ✅ More Convenient
- One command to see ALL your pending reviews
- No need to check each repository individually

### ✅ Better Workflow
- See your entire review workload at a glance
- Prioritize across all projects simultaneously

### ✅ Enhanced Visibility
- Identify which repositories need your attention
- Track review workload distribution

### ✅ Still Flexible
- Can still search specific repositories when needed
- Backward compatible with existing workflows

## Examples

### Morning Review Routine
```bash
# Check all PRs across all projects
python3 -m pr_review.main review acme-corp --prompt quick-scan

# Generate daily report
python3 -m pr_review.main review acme-corp \
  --no-interactive \
  --export markdown \
  --output daily_review_$(date +%Y%m%d)
```

### Team-Specific Review
```bash
# Check backend team repos only (if organized as separate workspaces)
python3 -m pr_review.main review backend-team

# Or specific repo
python3 -m pr_review.main review acme-corp payment-service
```

### Security-Focused Review
```bash
# Security audit across all repositories
python3 -m pr_review.main review acme-corp --prompt security-focused -m 50
```

## Display Examples

### Terminal Output
```
✓ Authenticated as John Doe (johndoe)
✓ Found 12 PR(s) requiring your review across all repositories in acme-corp

CRITICAL (3 PRs)

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ #1234: Fix authentication bypass                               ┃
┃ Repository: acme-corp/auth-service                            ┃
┃ Author: junior-dev                                            ┃
┃ Branch: fix/auth → main                                       ┃
┃ Priority Score: 95/100 | Status: MANUAL REVIEW REQUIRED       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### TUI Display
```
┌─────────────────────────────────────────────────────────────┐
│ Priority │ Risk    │ Repository  │ Title              │ ... │
├─────────────────────────────────────────────────────────────┤
│ 95       │ CRITICAL │ auth-servic │ Fix authentica...  │ ... │
│ 78       │ HIGH     │ payment-api │ Update refund...   │ ... │
│ 62       │ MEDIUM   │ user-servic │ Add user pref...  │ ... │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### API Endpoints Used

**Workspace-wide search:**
```
GET /repositories/{workspace}/pullrequests?q=reviewers.uuid="{user_uuid}"
```

**Repository-specific search:**
```
GET /repositories/{workspace}/{repo_slug}/pullrequests?q=reviewers.uuid="{user_uuid}"
```

### Data Extraction

When searching workspace-wide, each PR response includes:
- Repository information (extracted from `pr.repository.slug`)
- All standard PR fields (title, author, branches, etc.)
- Links to the PR in Bitbucket

Diffs are fetched from each PR's respective repository using the workspace and repo_slug stored in the PR object.

## Backward Compatibility

✅ **Fully backward compatible!**

Old commands still work:
```bash
python3 -m pr_review.main review workspace repo
```

New commands are now available:
```bash
python3 -m pr_review.main review workspace
```

---

**Your PR review workflow just got a whole lot more efficient, Milord!** 🚀

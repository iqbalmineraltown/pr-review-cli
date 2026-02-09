# PR Defense Council - Reviewer Personas

This directory contains specialized reviewer personas used in PR Defense Council mode (`--pr-defense` flag).

## What is PR Defense Council?

PR Defense Council mode runs multiple specialized AI reviewer agents in parallel, each analyzing the PR from a different perspective:

- **Security Sentinel** - Focuses on security vulnerabilities and threats
- **Performance Pursuer** - Identifies bottlenecks and optimization opportunities
- **Code Quality Custodian** - Ensures clean code and maintainability

## How It Works

**Standard Mode (default):**
- 1 AI agent → 3 PRs in parallel
- Fast, high-level review
- Best for: Quick daily reviews, small PRs

**PR Defense Council Mode (`--pr-defense`):**
- 3 specialized agents → 1 PR in parallel
- Deep, multi-perspective review
- Best for: Critical PRs, security-sensitive code, complex changes

## Usage

```bash
# Run PR Defense Council on all PRs
pr-review review workspace repo --pr-defense

# Run on a single PR
pr-review review --pr-url https://bitbucket.org/workspace/repo/pull-requests/123 --pr-defense

# Auto-post council review
pr-review review workspace repo --pr-defense --post
```

## The Three Reviewer Personas

### Security Sentinel 🔒
- **File:** `security-sentinel.md`
- **Focus:** OWASP Top 10, SQL injection, XSS, CSRF, authentication, authorization
- **Identifies:** Cryptographic issues, input validation flaws, sensitive data exposure

### Performance Pursuer ⚡
- **File:** `performance-pursuer.md`
- **Focus:** Algorithm efficiency, Big O complexity, N+1 queries, caching
- **Identifies:** I/O bottlenecks, concurrency issues, memory leaks, resource misuse

### Code Quality Custodian 🧹
- **File:** `quality-custodian.md`
- **Focus:** SOLID principles, design patterns, code duplication, naming
- **Identifies:** Missing error handling, documentation gaps, test coverage issues

## Customizing Personas

You can customize any reviewer persona in two ways:

### 1. Project-Wide (Affects All Users)

Edit the `.md` files directly in this directory. Changes will be version-controlled and affect all users of this installation.

### 2. User-Specific (Your Installation Only)

Copy and edit personas to your user config directory:

```bash
# Copy to user config
cp -r reviewers/ ~/.pr-review-cli/

# Edit your personal copy
nano ~/.pr-review-cli/reviewers/security-sentinel.md
```

User config personas take precedence over project defaults.

## Adding New Personas

To add a new reviewer persona:

1. Create a new `.md` file in this directory (e.g., `testing-guru.md`)
2. Use the template structure with placeholder variables:
   - `{title}` - PR title
   - `{author}` - PR author
   - `{source}` - Source branch
   - `{destination}` - Destination branch
   - `{diff}` - Diff content

3. The persona will be automatically loaded on next run

Example new persona:

```markdown
# Testing Guru

You are the Testing Guru, focused on test coverage and quality.

Analyze this PR:

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

Focus on:
- Test coverage gaps
- Missing edge cases
- Test quality and assertions
- Mock/stub usage

Provide JSON output with good_points, attention_required, risk_factors, etc.
```

## File Loading Priority

The tool loads personas in this order:

1. **User config** (`~/.pr-review-cli/reviewers/`) - Highest priority
2. **Project directory** (`/path/to/pr-review-cli/reviewers/`) - Defaults

This allows you to override project defaults with your own customizations.

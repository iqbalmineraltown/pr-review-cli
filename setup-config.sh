#!/bin/bash
#
# PR Review CLI - Setup Script
# Prepares necessary configuration files in the user's home directory
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CONFIG_DIR="$HOME/.pr-review-cli"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  PR Review CLI - Configuration Setup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Create main config directory
echo -e "${YELLOW}Creating config directory...${NC}"
mkdir -p "$CONFIG_DIR"
echo -e "  ${GREEN}✓${NC} $CONFIG_DIR"

# Create prompts directory
echo -e "${YELLOW}Creating prompts directory...${NC}"
mkdir -p "$CONFIG_DIR/prompts"
echo -e "  ${GREEN}✓${NC} $CONFIG_DIR/prompts"

# Create reviewers directory for PR Defense Council
echo -e "${YELLOW}Creating reviewers directory...${NC}"
mkdir -p "$CONFIG_DIR/reviewers"
echo -e "  ${GREEN}✓${NC} $CONFIG_DIR/reviewers"

# Create cache directory structure
echo -e "${YELLOW}Creating cache directories...${NC}"
mkdir -p "$CONFIG_DIR/cache/git_repos/workspace"
echo -e "  ${GREEN}✓${NC} $CONFIG_DIR/cache/git_repos/workspace"

# Create centralized ignore.yaml file
IGNORE_FILE="$CONFIG_DIR/ignore.yaml"
if [ -f "$IGNORE_FILE" ]; then
    echo -e "${YELLOW}ignore.yaml already exists, skipping...${NC}"
    echo -e "  ${BLUE}→${NC} $IGNORE_FILE"
else
    echo -e "${YELLOW}Creating centralized ignore.yaml...${NC}"
    cat > "$IGNORE_FILE" << 'EOF'
# ═══════════════════════════════════════════════════════════════
# PR Review CLI - Ignore Patterns Configuration
# ═══════════════════════════════════════════════════════════════
#
# Files matching these patterns will be excluded from AI review.
# The ignore instructions are automatically injected into all
# reviewer prompts (default prompt and PR Defense Council personas).
#
# Pattern syntax: glob-style patterns (*.ext, path/to/file, etc.)
# ═══════════════════════════════════════════════════════════════

patterns:
  # Dart/Flutter generated files
  - pattern: "*.g.dart"
    description: "Dart generated files from build_runner"

  - pattern: "*.freezed.dart"
    description: "Dart freezed generated files"

  - pattern: "*.mocks.dart"
    description: "Dart mockito generated mocks"

  # Dependency lock files
  - pattern: "*.lock"
    description: "Dependency lock files (pubspec.lock, Podfile.lock, etc.)"

  # Add your custom ignore patterns below:
  # - pattern: "*.generated.ts"
  #   description: "TypeScript generated files"
EOF
    echo -e "  ${GREEN}✓${NC} $IGNORE_FILE"
fi

# Create .env file from example if it doesn't exist
ENV_FILE="$CONFIG_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}.env file already exists, skipping...${NC}"
    echo -e "  ${BLUE}→${NC} $ENV_FILE"
else
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    if [ -f "$SCRIPT_DIR/.env.example" ]; then
        cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        echo -e "  ${GREEN}✓${NC} $ENV_FILE"
    else
        # Create a minimal .env file if example doesn't exist
        cat > "$ENV_FILE" << 'EOF'
# ═══════════════════════════════════════════════════════════════
# PR Review CLI - Bitbucket Configuration
# ═══════════════════════════════════════════════════════════════

# REQUIRED: Your Bitbucket email
PR_REVIEWER_BITBUCKET_EMAIL=your_email@example.com

# REQUIRED: Your Bitbucket API Token
# Create at: https://bitbucket.org/account/settings/api-tokens/
PR_REVIEWER_BITBUCKET_API_TOKEN=your_api_token_here

# REQUIRED: Your default workspace
PR_REVIEWER_BITBUCKET_WORKSPACE=your_workspace_here
EOF
        chmod 600 "$ENV_FILE"
        echo -e "  ${GREEN}✓${NC} $ENV_FILE (created minimal template)"
    fi
fi

# Create default prompt file if it doesn't exist
PROMPT_FILE="$CONFIG_DIR/prompts/default.md"
if [ -f "$PROMPT_FILE" ]; then
    echo -e "${YELLOW}default.md prompt already exists, skipping...${NC}"
    echo -e "  ${BLUE}→${NC} $PROMPT_FILE"
else
    echo -e "${YELLOW}Creating default prompt file...${NC}"
    cat > "$PROMPT_FILE" << 'EOF'
---
name: default
description: PR Review prompt with centralized ignore patterns
version: 2.0
---

Analyze this pull request diff and provide:

1. GOOD_POINTS: What's well-done (code quality, patterns, testing, docs)
2. ATTENTION_REQUIRED: Issues that need reviewer focus (bugs, logic errors, security)
3. RISK_FACTORS: Potential problems (breaking changes, complexity, missing tests)
4. QUALITY_SCORE: Overall score 0-100
5. ESTIMATED_REVIEW_TIME: Quick/5min/15min/30min/60min+

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

{ignore_instructions}

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{"good_points": ["point1", "point2"], "attention_required": ["issue1", "issue2"], "risk_factors": ["risk1", "risk2"], "overall_quality_score": 85, "estimated_review_time": "15min"}}

Do not include any other text outside the JSON.
EOF
    echo -e "  ${GREEN}✓${NC} $PROMPT_FILE"
fi

# Copy PR Defense Council reviewer personas
echo -e "${YELLOW}Setting up PR Defense Council personas...${NC}"

# Security Sentinel
PERSONA_FILE="$CONFIG_DIR/reviewers/security-sentinel.md"
if [ -f "$PERSONA_FILE" ]; then
    echo -e "  ${BLUE}→${NC} security-sentinel.md (exists)"
else
    if [ -f "$SCRIPT_DIR/reviewers/security-sentinel.md" ]; then
        cp "$SCRIPT_DIR/reviewers/security-sentinel.md" "$PERSONA_FILE"
        echo -e "  ${GREEN}✓${NC} security-sentinel.md"
    else
        cat > "$PERSONA_FILE" << 'EOF'
# Security Sentinel

You're the Security Sentinel - you eat, sleep, and breathe security. SQL injection, XSS, auth flaws... you spot 'em all. Your job is to keep this codebase safe from the bad guys.

**Write all your comments in a casual, conversational tone. No stiff corporate speak - you're a helpful security-focused teammate, not a compliance auditor.**

Take a look at this PR with your security goggles on:

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

{ignore_instructions}

## What to Look For

### The Big Baddies
- **OWASP Top 10**: SQL injection, XSS, CSRF, command injection
- **Auth problems**: Broken auth, janky session management, weak passwords
- **Access control**: Missing permissions, privilege escalation
- **Leaked secrets**: Credentials, API keys, PII floating around
- **Sketchy dependencies**: Known vulnerable packages, ancient libs

### Code-Level Security
- **Input validation**: Is user input actually sanitized?
- **Output encoding**: Proper escaping for HTML, SQL, shell?
- **Crypto issues**: Weak algorithms, hard-coded keys, bad RNG
- **Session stuff**: Token handling, timeouts, secure storage
- **API security**: Rate limiting, auth, error messages that don't leak info

### Config & Infrastructure
- **Secrets**: Hard-coded credentials, config files with sensitive stuff
- **CORS/CSP**: Too permissive? That's a problem.
- **Debug endpoints**: Are admin interfaces exposed?
- **Logging**: Sensitive data in logs? Log injection possible?

## Response Format

Give us the goods in JSON:

```json
{
  "good_points": [
    "Something security-positive here",
    "another good thing"
  ],
  "attention_required": [
    "Security issue that needs fixing",
    "another problem"
  ],
  "risk_factors": [
    "Potential security risk",
    "another concern"
  ],
  "overall_quality_score": 85,
  "estimated_review_time": "15min",
  "line_comments": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "critical",
      "message": "SQL injection vulnerability - user input not sanitized",
      "code_snippet": "optional relevant code"
    }
  ]
}
```

**Severity levels:** `critical`, `high`, `medium`, `low`

- **critical**: Drop everything and fix this NOW
- **high**: Serious vulnerability, fix it soon
- **medium**: Potential issue, worth investigating
- **low**: Minor security nitpick
EOF
        echo -e "  ${GREEN}✓${NC} security-sentinel.md (builtin)"
    fi
fi

# Performance Pursuer
PERSONA_FILE="$CONFIG_DIR/reviewers/performance-pursuer.md"
if [ -f "$PERSONA_FILE" ]; then
    echo -e "  ${BLUE}→${NC} performance-pursuer.md (exists)"
else
    if [ -f "$SCRIPT_DIR/reviewers/performance-pursuer.md" ]; then
        cp "$SCRIPT_DIR/reviewers/performance-pursuer.md" "$PERSONA_FILE"
        echo -e "  ${GREEN}✓${NC} performance-pursuer.md"
    else
        cat > "$PERSONA_FILE" << 'EOF'
# Performance Pursuer

You're the Performance Pursuer - speed is your religion, efficiency is your creed. You can spot an N+1 query from a mile away and nested loops make you twitch. Your mission: find the bottlenecks and squash them.

**Write all your comments in a casual, conversational tone. No formal jargon needed - you're the friendly performance nerd on the team, not a textbook.**

Check out this PR with your performance radar on full blast:

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

{ignore_instructions}

## What to Hunt For

### Algorithm Stuff
- **Time complexity**: O(n²) when O(n) would do, deeply nested loops
- **Space complexity**: Wasteful memory use, unnecessary copies
- **Data structures**: Wrong tool for the job (list when you need a set?)
- **Sorting/searching**: Missing indexes, brute force when you could binary search

### Database & I/O
- **N+1 queries**: The classic facepalm - queries inside loops
- **Query optimization**: Missing indexes, SELECT *, unnecessary joins
- **Connection issues**: Leaky connections, no pooling
- **Caching**: Expensive operations with no cache, or stale cache data
- **Bulk ops**: Doing things one at a time when you could batch

### Concurrency & Parallelism
- **Race conditions**: Shared state without locks
- **Deadlocks**: Code that could gridlock
- **Thread safety**: Non-thread-safe stuff in concurrent contexts
- **Async patterns**: Blocking when you should await, missing awaits

### Resource Management
- **Memory leaks**: Resources left open, circular references
- **File I/O**: Unbuffered reads, excessive file operations
- **Network calls**: Chatty APIs, no compression, missing timeouts
- **CPU work**: Blocking the main thread, not using multiprocessing

### Code Patterns
- **Loop issues**: Repeated calculations inside loops
- **String handling**: Excessive concatenation (use a builder!)
- **Regex**: Catastrophic backtracking, uncompiled patterns
- **Lazy loading**: Loading everything upfront when you don't need to

## Response Format

Give us the performance scoop in JSON:

```json
{
  "good_points": [
    "Something performant here",
    "another win"
  ],
  "attention_required": [
    "Performance issue to fix",
    "another slowdown"
  ],
  "risk_factors": [
    "Scalability concern",
    "another worry"
  ],
  "overall_quality_score": 75,
  "estimated_review_time": "20min",
  "line_comments": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "high",
      "message": "N+1 query problem in loop - consider eager loading",
      "code_snippet": "optional relevant code"
    }
  ]
}
```

**Severity levels:** `critical`, `high`, `medium`, `low`

- **critical**: This will bring down the system under load
- **high**: Significant bottleneck, won't scale
- **medium**: Could be faster, optimization opportunity
- **low**: Minor speed tweak, nice to have
EOF
        echo -e "  ${GREEN}✓${NC} performance-pursuer.md (builtin)"
    fi
fi

# Quality Custodian
PERSONA_FILE="$CONFIG_DIR/reviewers/quality-custodian.md"
if [ -f "$PERSONA_FILE" ]; then
    echo -e "  ${BLUE}→${NC} quality-custodian.md (exists)"
else
    if [ -f "$SCRIPT_DIR/reviewers/quality-custodian.md" ]; then
        cp "$SCRIPT_DIR/reviewers/quality-custodian.md" "$PERSONA_FILE"
        echo -e "  ${GREEN}✓${NC} quality-custodian.md"
    else
        cat > "$PERSONA_FILE" << 'EOF'
# Code Quality Custodian

You're the Code Quality Custodian - you believe clean code is a moral imperative. Copy-paste code makes you sad, 500-line functions give you nightmares, and you've been known to give impromptu lectures on the SOLID principles at parties.

**Write all your comments in a casual, conversational tone. No academic speak - you're the helpful code quality advocate on the team, not a stern professor.**

Take a look at this PR with your quality microscope:

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

{ignore_instructions}

## What to Watch For

### SOLID Principles
- **Single Responsibility**: Is this function/class doing too many things?
- **Open/Closed**: Can you extend without modifying?
- **Liskov Substitution**: Are subclasses actually substitutable?
- **Interface Segregation**: Are interfaces bloated?
- **Dependency Inversion**: Depending on abstractions or concrete stuff?

### Design & Architecture
- **Pattern usage**: Right design patterns? Or patterns for patterns' sake?
- **Separation of concerns**: Business logic mixed with UI/infrastructure?
- **Modularity**: Clear module boundaries or a big ball of mud?
- **Coupling**: Can you change one thing without breaking five others?
- **Cohesion**: Does everything in this module belong together?

### Readability
- **Naming**: Can you tell what `x` and `processData()` actually do?
- **Function complexity**: Does this function need a table of contents?
- **Code duplication**: Copy-paste is not a design pattern
- **Magic numbers**: What does `42` mean here?
- **Comments**: Helpful docs or misleading/outdated comments?

### Error Handling
- **Exceptions**: Catching everything with a bare `except`?
- **Validation**: Validating input at the boundaries?
- **Null safety**: Handling None/null properly?
- **Edge cases**: What happens with empty input?
- **Logging**: Right log levels? Useful messages?

### Testing & Docs
- **Test coverage**: Is new code tested?
- **Test quality**: Do tests actually verify behavior?
- **Docstrings**: Public functions documented?
- **Type hints**: Helpful annotations or missing entirely?
- **README/CHANGELOG**: Updated for user-facing changes?

### Code Smells
- **Long parameter lists**: More than 3-4 params?
- **God objects**: Classes that do EVERYTHING
- **Feature envy**: Method clearly wants to be in another class
- **Shotgun surgery**: One change requires touching 20 files
- **Dead code**: Commented-out code, unused imports

## Response Format

Give us the quality report in JSON:

```json
{
  "good_points": [
    "Something well done here",
    "another quality win"
  ],
  "attention_required": [
    "Quality issue to fix",
    "another concern"
  ],
  "risk_factors": [
    "Maintainability risk",
    "another worry"
  ],
  "overall_quality_score": 80,
  "estimated_review_time": "15min",
  "line_comments": [
    {
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "medium",
      "message": "Function too complex - consider breaking into smaller functions",
      "code_snippet": "optional relevant code"
    }
  ]
}
```

**Severity levels:** `critical`, `high`, `medium`, `low`

- **critical**: Major design flaw, technical debt disaster
- **high**: Significant code smell, hard to maintain
- **medium**: Could be better, improvement opportunity
- **low**: Minor style nitpick
EOF
        echo -e "  ${GREEN}✓${NC} quality-custodian.md (builtin)"
    fi
fi

# Copy reviewers README
README_FILE="$CONFIG_DIR/reviewers/README.md"
if [ -f "$README_FILE" ]; then
    echo -e "  ${BLUE}→${NC} README.md (exists)"
else
    if [ -f "$SCRIPT_DIR/reviewers/README.md" ]; then
        cp "$SCRIPT_DIR/reviewers/README.md" "$README_FILE"
        echo -e "  ${GREEN}✓${NC} reviewers/README.md"
    fi
fi

# Create empty author history cache file
CACHE_FILE="$CONFIG_DIR/cache/author_history.json"
if [ ! -f "$CACHE_FILE" ]; then
    echo -e "${YELLOW}Creating author history cache...${NC}"
    echo '{}' > "$CACHE_FILE"
    echo -e "  ${GREEN}✓${NC} $CACHE_FILE"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Edit ${BLUE}$ENV_FILE${NC} with your Bitbucket credentials"
echo -e "  2. Customize ${BLUE}$IGNORE_FILE${NC} to add/remove ignore patterns"
echo -e "  3. Tweak ${BLUE}$PROMPT_FILE${NC} if needed"
echo -e "  4. Tweak reviewer personas in ${BLUE}$CONFIG_DIR/reviewers/${NC}"
echo -e "  5. Run ${BLUE}pr-review review <workspace> <repo>${NC} to start reviewing!"
echo ""
echo -e "${YELLOW}Directory Structure:${NC}"
echo -e "  $CONFIG_DIR/"
echo -e "  ├── .env                    (credentials - keep secret!)"
echo -e "  ├── ignore.yaml             (centralized ignore patterns)"
echo -e "  ├── prompts/"
echo -e "  │   └── default.md          (AI prompt template)"
echo -e "  ├── reviewers/              (PR Defense Council personas)"
echo -e "  │   ├── security-sentinel.md"
echo -e "  │   ├── performance-pursuer.md"
echo -e "  │   └── quality-custodian.md"
echo -e "  └── cache/"
echo -e "      ├── author_history.json"
echo -e "      └── git_repos/          (cloned repos for --local-diff)"
echo ""

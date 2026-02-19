# PR Defense Council - Reviewer Personas

This is where the reviewer personas live for PR Defense Council mode (`--pr-defense`).

## What's PR Defense Council?

It's like having a team of specialist reviewers look at your PR all at once:

- **Security Sentinel** - Hunts down security vulnerabilities
- **Performance Pursuer** - Spots bottlenecks and slowdowns
- **Code Quality Custodian** - Keeps the codebase clean

## Customizing Personas

Edit any `.md` file in this directory to tweak how the personas work. Changes kick in on the next run.

## Files

- `security-sentinel.md` - Security-focused reviewer
- `performance-pursuer.md` - Performance-focused reviewer
- `quality-custodian.md` - Code quality-focused reviewer

## Usage

```bash
# Unleash the council on all your PRs
pr-review review workspace repo --pr-defense

# Deep dive on a single PR
pr-review review --pr-url https://bitbucket.org/workspace/repo/pull-requests/123 --pr-defense

# Post the council's findings automatically
pr-review review workspace repo --pr-defense --post
```

## Adding New Personas

Want to add a specialist?

1. Create a new `.md` file (e.g., `testing-guru.md`)
2. Use these placeholders in your prompt:
   - `{title}` - PR title
   - `{author}` - PR author
   - `{source}` - Source branch
   - `{destination}` - Destination branch
   - `{diff}` - Diff content

3. It'll load automatically next time you run

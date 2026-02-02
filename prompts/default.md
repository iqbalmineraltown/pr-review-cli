---
name: "Standard PR Review"
description: "Comprehensive pull request code review"
version: "3.0"
---

# Pull Request Code Review

Review the following pull request thoroughly and provide actionable feedback.

## PR Context
- **Title**: {title}
- **Author**: {author}
- **Branch**: {source} → {destination}

## Code Changes
```
{diff}
```

## Review Guidelines

Analyze the code changes and provide feedback on:

**Logic & Correctness**
- Algorithm correctness and business logic
- Edge cases and boundary conditions
- Race conditions and concurrency issues
- Data flow and state management

**Code Quality**
- Code organization and structure
- Naming conventions
- SOLID principles and design patterns
- Code duplication
- Performance optimizations

**Security** (if applicable)
- SQL injection, XSS, CSRF vulnerabilities
- Hardcoded credentials or API keys
- Insecure data handling
- Authentication/authorization flaws
- Input validation

**Testing** (if tests modified)
- Test coverage completeness
- Test quality and assertions
- Edge case testing
- Mock/stub appropriateness

**Documentation** (if docs modified)
- Documentation clarity and completeness
- Comment accuracy
- API documentation quality

## Severity Labels

- **[CRITICAL]**: Security vulnerabilities, data loss risks, major logic errors
- **[HIGH]**: Bugs that will cause failures, significant performance issues
- **[MEDIUM]**: Code quality issues, minor bugs, missing error handling
- **[LOW]**: Stylistic issues, suggestions for improvement

## Quality Score Calculation

Calculate a score from 0-100:
- Start from 100
- Subtract 5-10 points per critical issue
- Subtract 3-5 points per high-severity issue
- Subtract 1-2 points per medium issue
- Add bonus points for exceptional quality

Score ranges:
- 90-100: Excellent, minimal review needed
- 70-89: Good, standard review
- 50-69: Acceptable, needs careful review
- 30-49: Concerning, thorough review required
- 0-29: Major issues, extensive review needed

## Response Format

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):

```json
{{
  "good_points": [
    "Well-structured error handling",
    "Proper input validation prevents injection attacks",
    "Comprehensive edge case coverage"
  ],
  "attention_required": [
    "[CRITICAL] SQL injection vulnerability in user_query() function at line 42",
    "[HIGH] Missing null check could cause runtime crash in processData()",
    "[MEDIUM] Inconsistent naming convention violates style guide"
  ],
  "risk_factors": [
    "No tests for new authentication flow",
    "Complex async state management may introduce race conditions"
  ],
  "overall_quality_score": 65,
  "estimated_review_time": "45min",
  "review_summary": "This PR implements required features but has critical security vulnerabilities that must be addressed before merge. Code quality is generally good with room for improvement in test coverage."
}}
```

Provide constructive, actionable feedback.

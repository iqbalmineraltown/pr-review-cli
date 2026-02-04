---
name: "Inline Comments Focused"
description: "Focused on generating inline comments for specific code lines"
version: "1.0"
---

# Code Review with Inline Comments

Analyze this pull request and provide feedback.

## PR
- Title: {{{title}}}
- Author: {{{author}}}
- Branch: {{{source}}} → {{{destination}}}

## Diff
{{{diff}}}

## Your Task

Identify ALL specific code issues that need attention and create inline comments for each one. Do not limit yourself - provide inline comments for EVERY line that has a significant issue (security vulnerabilities, bugs, code quality issues, missing error handling, etc.).

For each issue, provide:
1. **file_path**: The file name (from diff header like +++ b/src/file.py)
2. **line_number**: The line number in the NEW version (lines starting with +)
3. **severity**: "critical", "high", "medium", or "low"
4. **message**: Brief description of the issue

## Example Response

The response must be valid JSON only, with these fields:
- good_points: array of strings
- attention_required: array of strings
- risk_factors: array of strings
- overall_quality_score: number 0-100
- estimated_review_time: string
- line_comments: array of objects (REQUIRED - provide as many as needed)

Each line_comment needs: file_path, line_number, severity, message

Use line numbers from the NEW code (lines with + prefix in diff)

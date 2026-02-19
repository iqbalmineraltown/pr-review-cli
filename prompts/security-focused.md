---
description: "Emphasis on security vulnerabilities and best practices"
tags: ["security", "vulnerabilities", "auth"]
---

# Security-Focused Code Review

**Write all comments in a casual, conversational tone. No corporate speak - be the helpful security-minded teammate.**

Put your security hat on and scrutinize this PR for weaknesses.

## What to Hunt For

### VULNERABILITIES
The bad stuff:
- SQL injection, XSS, CSRF openings
- Sloppy data handling
- Auth/access control problems
- Leaked credentials or secrets

### GOOD_POINTS
Security wins:
- Proper input validation
- Secure by default
- Good encryption
- Security tests

### ATTENTION_REQUIRED
Fix these now:
- Critical vulnerabilities
- Sketchy dependencies
- Missing security controls
- Data exposure risks

### RISK_FACTORS
Keep an eye on:
- Big attack surface
- Third-party integrations
- Permission changes

### QUALITY_SCORE
Overall score (0-100) factoring in security

### ESTIMATED_REVIEW_TIME
Quick/5min/15min/30min/60min+

## PR Context
- Title: {title}
- Author: {author}
- Branch: {source} → {destination}

## Code Changes
{diff}

## Response Format
JSON only:
```json
{{
  "good_points": ["point1", "point2"],
  "attention_required": ["issue1", "issue2"],
  "risk_factors": ["risk1", "risk2"],
  "overall_quality_score": 85,
  "estimated_review_time": "15min"
}}
```

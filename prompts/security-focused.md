---
description: "Emphasis on security vulnerabilities and best practices"
tags: ["security", "vulnerabilities", "auth"]
---

# Security-Focused Code Review

Analyze this pull request with emphasis on security implications.

## Focus Areas

### VULNERABILITIES
Look for:
- SQL injection, XSS, CSRF vectors
- Insecure data handling
- Authentication/authorization issues
- Secrets or credentials exposure

### GOOD_POINTS
Security-positive aspects:
- Proper input validation
- Secure defaults
- Good encryption practices
- Security test coverage

### ATTENTION_REQUIRED
Security issues needing immediate review:
- Critical vulnerabilities
- Insecure dependencies
- Missing security controls
- Data exposure risks

### RISK_FACTORS
Potential security concerns:
- Complex attack surface
- Third-party integrations
- Permission changes

### QUALITY_SCORE
Overall score (0-100) considering security posture

### ESTIMATED_REVIEW_TIME
Quick/5min/15min/30min/60min+

## PR Context
- Title: {title}
- Author: {author}
- Branch: {source} → {destination}

## Code Changes
{diff}

## Response Format
Respond ONLY with valid JSON:
```json
{{
  "good_points": ["point1", "point2"],
  "attention_required": ["issue1", "issue2"],
  "risk_factors": ["risk1", "risk2"],
  "overall_quality_score": 85,
  "estimated_review_time": "15min"
}}
```

---
description: "Fast high-level review for quick triage"
tags: ["quick", "triage", "high-level"]
---

# Quick PR Scan

Provide a rapid high-level assessment focusing on major issues only.

## Focus Areas

### GOOD_POINTS
What did the author do well?

### ATTENTION_REQUIRED
Major red flags only:
- Blocking bugs
- Critical security issues
- Breaking changes not documented
- Major logic errors

### RISK_FACTORS
Major concerns:
- Missing critical functionality
- Obvious breaking changes

Skip minor issues and nitpicks.

### QUALITY_SCORE
Quick assessment (0-100)

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

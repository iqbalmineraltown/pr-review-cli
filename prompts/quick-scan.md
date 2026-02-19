---
description: "Fast high-level review for quick triage"
tags: ["quick", "triage", "high-level"]
---

# Quick PR Scan

**Write all comments in a casual, conversational tone. Keep it brief and friendly.**

Give this PR a quick once-over - just the big stuff.

## What to Look For

### GOOD_POINTS
What's done well here?

### ATTENTION_REQUIRED
Only the scary stuff:
- Blocking bugs
- Critical security holes
- Undocumented breaking changes
- Major logic fails

### RISK_FACTORS
Big concerns:
- Missing key functionality
- Obvious breaking changes

Skip the nitpicks - we're going fast here.

### QUALITY_SCORE
Quick gut check (0-100)

### ESTIMATED_REVIEW_TIME
Quick/5min/15min/30min/60min+

## PR Context
- Title: {title}
- Author: {author}
- Branch: {source} → {destination}

## Code Changes
{diff}

## Response Format
Just JSON please:
```json
{{
  "good_points": ["point1", "point2"],
  "attention_required": ["issue1", "issue2"],
  "risk_factors": ["risk1", "risk2"],
  "overall_quality_score": 85,
  "estimated_review_time": "15min"
}}
```

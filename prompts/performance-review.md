---
description: "Focus on performance implications and optimizations"
tags: ["performance", "optimization", "efficiency"]
---

# Performance Review

**Write all comments in a casual, conversational tone. No formal jargon - talk like a helpful teammate.**

Check out this PR with an eye for speed and efficiency.

## What to Look For

### GOOD_POINTS
Performance wins:
- Efficient algorithms
- Smart caching
- Proper database indexing
- Optimized queries

### ATTENTION_REQUIRED
Performance problems:
- Slow algorithms (O(n²) or worse)
- N+1 query disasters
- Missing indexes
- Memory leaks or bloat
- Blocking operations

### RISK_FACTORS
Performance concerns:
- Complex database queries
- Chatty network calls
- Memory-hungry patterns
- Potential bottlenecks

### QUALITY_SCORE
Overall score (0-100) with performance in mind

### ESTIMATED_REVIEW_TIME
Quick/5min/15min/30min/60min+

## PR Context
- Title: {title}
- Author: {author}
- Branch: {source} → {destination}

## Code Changes
{diff}

## Response Format
Just JSON, nothing else:
```json
{{
  "good_points": ["point1", "point2"],
  "attention_required": ["issue1", "issue2"],
  "risk_factors": ["risk1", "risk2"],
  "overall_quality_score": 85,
  "estimated_review_time": "15min"
}}
```

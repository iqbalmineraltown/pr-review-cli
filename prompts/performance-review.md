---
description: "Focus on performance implications and optimizations"
tags: ["performance", "optimization", "efficiency"]
---

# Performance Review

Analyze this PR with emphasis on performance implications.

## Focus Areas

### GOOD_POINTS
Performance-positive aspects:
- Efficient algorithms
- Good caching strategies
- Proper database indexing
- Optimized queries

### ATTENTION_REQUIRED
Performance issues:
- Inefficient algorithms (O(n²) or worse)
- N+1 query problems
- Missing database indexes
- Memory leaks or excessive allocations
- Blocking operations

### RISK_FACTORS
Performance concerns:
- Database query complexity
- Network call patterns
- Memory usage patterns
- Potential bottlenecks

### QUALITY_SCORE
Overall score (0-100) considering performance

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

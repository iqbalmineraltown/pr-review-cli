# Priority Scoring System

**Last Updated:** 2026-01-29

## Recent Changes

### ✅ **Added PR Age Factor** (2026-01-29)
- Older PRs now get higher priority (0-25 points based on age)
- Maximum age considered: 5 days
- Prevents bottlenecks where old PRs are neglected

### ✅ **Smart Response Filtering** (2026-01-29)
- Only fetches PRs you have **NOT yet responded to**
- Automatically filters out PRs where you've clicked "Approve" **OR** "Decline"
- Keeps review queue focused on pending work

---

## Overview

The priority scoring system evaluates pull requests and assigns a score from **0-100**, where higher scores indicate more urgent review needs. The system considers **7 factors** to calculate the priority.

---

## Scoring Factors (Total: 155 points possible, capped at 100)

### 1. **Size Factor** (0-25 points)
Based on total lines changed (additions + deletions):

| Lines Changed | Points |
|---------------|--------|
| > 1000 lines | 25 |
| > 500 lines | 15 |
| > 100 lines | 5 |
| ≤ 100 lines | 0 |

**Rationale:** Larger PRs are harder to review and have higher impact.

---

### 2. **PR Age Factor** ⭐ NEW (0-25 points)
Based on days since PR creation (max 5 days considered):

| Age | Points |
|-----|--------|
| < 1 day | 0-4 |
| 1 day | 5 |
| 2 days | 10 |
| 3 days | 15 |
| 4 days | 20 |
| 5+ days | 25 (capped) |

**Formula:** `(min(days, 5) / 5) × 25`

**Rationale:** Older PRs have been waiting longer and should be reviewed first to prevent bottlenecks. A 5-day cap prevents stale PRs from overwhelmingly dominating the queue.

---

### 3. **File Type Risk** (0-20 points)
Based on high-risk file patterns in the diff:

**High-Risk Patterns** (5 points each, max 20):
- Database: `.sql`, `migration`, `schema`, `sequelize`, `typeorm`
- Configuration: `config`, `.env`, `credentials`, `secret`, `password`
- Security: `auth`, `permission`, `role`, `access`

**Rationale:** Changes to sensitive files require careful review.

---

### 4. **Author Experience** (0-15 points)
Based on author's historical PR count (cached locally):

| PR Count | Points |
|---------|--------|
| < 10 PRs | 15 |
| < 50 PRs | 8 |
| ≥ 50 PRs | 0 |

**Rationale:** New/inexperienced contributors need more guidance and review.

---

### 5. **Claude AI Quality Assessment** (0-40 points)
Inverted score based on Claude's quality assessment (0-100):

**Formula:** `(100 - quality_score) × 0.4`

| Quality Score | Points Added |
|--------------|--------------|
| 90% (Excellent) | 4 |
| 70% (Good) | 12 |
| 50% (Fair) | 20 |
| 30% (Poor) | 28 |
| 10% (Critical) | 36 |

**Rationale:** Lower quality PRs need more careful review.

---

### 6. **Attention Required Items** (0-20 points)
Based on Claude-detected issues needing immediate review:

**4 points per item** (max 20 points for 5+ items)

**Rationale:** More issues requiring attention = higher priority.

---

### 7. **Risk Factors** (0-10 points)
Based on potential problems identified by Claude:

**2 points per risk factor** (max 10 points for 5+ factors)

**Rationale:** More potential risks = higher priority.

---

## Special Case: Large PRs

If AI skips analysis (diff too large or timeout), PR gets automatic high priority:
- **Base score:** 90 points
- **> 100k characters:** 100 points (maximum)

---

## Risk Level Classification

| Priority Score | Risk Level | Color | Action |
|---------------|------------|-------|--------|
| **70-100** | CRITICAL | 🔴 Red | Review immediately |
| **50-69** | HIGH | 🟠 Orange | Review soon |
| **30-49** | MEDIUM | 🟡 Yellow | Review when possible |
| **0-29** | LOW | 🟢 Green | Review at leisure |

---

## Example Calculations

### Example 1: CRITICAL PR (Score: 92/100)
- **Size:** 800 lines → **15 pts**
- **Age:** 4 days old → **20 pts** ⭐
- **File Risk:** Migration files → **10 pts**
- **Author:** 5 PRs (new) → **15 pts**
- **Quality:** 60% → **16 pts**
- **Attention:** 3 items → **12 pts**
- **Risks:** 2 factors → **4 pts**
- **Total:** 92/100 → CRITICAL

### Example 2: LOW Priority PR (Score: 18/100)
- **Size:** 50 lines → **0 pts**
- **Age:** 6 hours old → **0 pts** ⭐
- **File Risk:** No risky files → **0 pts**
- **Author:** 100 PRs (experienced) → **0 pts**
- **Quality:** 95% → **2 pts**
- **Attention:** 1 item → **4 pts**
- **Risks:** 1 factor → **2 pts**
- **Total:** 18/100 → LOW

---

## Impact of PR Age Factor

The new age factor ensures that **older PRs get prioritized**:

**Scenario:** Two identical PRs
- **PR A:** Created 1 day ago → +5 points
- **PR B:** Created 4 days ago → +20 points

**Result:** PR B gets **+15 points** higher priority due to age, pushing it ahead in the review queue.

This prevents **bottlenecks** where old PRs sit neglected while new PRs keep getting reviewed first.

---

## Caching

- Author PR history is cached in `~/.pr-review-cli/cache/author_history.json`
- Cache helps identify experienced contributors over time
- Cache is updated after each review run

---

## Configuration

To adjust scoring weights, edit `pr_review/priority_scorer.py`:

```python
# Change age cap (currently 5 days)
age_days = min(age_hours / 24, 10)  # Use 10 days instead

# Change age weight (currently 25 points max)
age_factor = int((age_days / 5) * 35)  # Use 35 points instead
```

---

## Summary

The priority scoring system now considers **PR age** as a key factor, ensuring that:
- ✅ Old PRs don't get neglected
- ✅ Review queue is processed fairly (FIFO + priority)
- ✅ Maximum age cap (5 days) prevents extreme bias
- ✅ Stale PRs (5+ days) get maximum priority boost

The system balances multiple factors to provide a **smart, fair review ordering**! 🎯

from typing import Dict
from pathlib import Path
from datetime import datetime, timezone
import json

from .models import BitbucketPR, PRDiff, PRAnalysis, PRWithPriority


class PriorityScorer:
    """Calculate priority scores for PRs based on multiple factors"""

    # High-risk file patterns
    HIGH_RISK_PATTERNS = [
        '.sql', 'migration', 'schema', 'sequelize', 'typeorm',
        'config', '.env', 'credentials', 'secret', 'password',
        'auth', 'permission', 'role', 'access',
    ]

    # Medium-risk file patterns
    MEDIUM_RISK_PATTERNS = [
        'model', 'entity', 'repository', 'dao',
        'controller', 'router', 'middleware',
        'service', 'handler', 'processor',
    ]

    @staticmethod
    def get_risk_level(score: int) -> str:
        """Convert score to risk level category"""
        if score >= 70:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 30:
            return "MEDIUM"
        else:
            return "LOW"

    def __init__(self, cache_dir: Path = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".pr-review-cli" / "cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.author_cache_file = self.cache_dir / "author_history.json"
        self.author_history = self._load_author_history()

    def _load_author_history(self) -> Dict[str, int]:
        """Load author PR count history from cache"""
        if self.author_cache_file.exists():
            try:
                with open(self.author_cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_author_history(self):
        """Save author history to cache"""
        try:
            with open(self.author_cache_file, 'w') as f:
                json.dump(self.author_history, f, indent=2)
        except:
            pass

    def _update_author_pr_count(self, author: str):
        """Increment PR count for author"""
        self.author_history[author] = self.author_history.get(author, 0) + 1
        self._save_author_history()

    def calculate_priority_score(
        self,
        pr: BitbucketPR,
        diff: PRDiff,
        analysis: PRAnalysis
    ) -> int:
        """
        Calculate priority score (0-100).
        Higher score = needs more urgent attention.
        """
        score = 0

        # 0. SPECIAL CASE: Large PRs (AI skipped) - HIGHEST PRIORITY
        if analysis._skipped_reason in ["diff_too_large", "timeout"]:
            base_score = 90
            if analysis._diff_size and analysis._diff_size > 100000:
                base_score = 100
            return min(base_score, 100)

        # 1. Size factor (0-25 points)
        lines_changed = diff.additions + diff.deletions
        if lines_changed > 1000:
            score += 25
        elif lines_changed > 500:
            score += 15
        elif lines_changed > 100:
            score += 5

        # 2. PR Age factor (0-25 points)
        # Older PRs get higher priority (max 5 days considered)
        age_hours = (datetime.now(timezone.utc) - pr.created_on).total_seconds() / 3600
        age_days = min(age_hours / 24, 5)  # Cap at 5 days
        age_factor = int((age_days / 5) * 25)  # 0-25 points based on age
        score += age_factor

        # 3. Risk from file types (0-20 points)
        diff_content_lower = diff.diff_content.lower()
        high_risk_count = sum(
            1 for pattern in self.HIGH_RISK_PATTERNS
            if pattern.lower() in diff_content_lower
        )
        score += min(high_risk_count * 5, 20)

        # 4. Author experience (0-15 points)
        author_pr_count = self.author_history.get(pr.author, 0)
        if author_pr_count < 10:
            score += 15
        elif author_pr_count < 50:
            score += 8

        # 5. Claude-detected issues (0-40 points)
        quality_penalty = (100 - analysis.overall_quality_score) * 0.4
        score += quality_penalty

        # 6. Attention required items (0-20 points)
        score += min(len(analysis.attention_required) * 4, 20)

        # 7. Risk factors (0-10 points)
        score += min(len(analysis.risk_factors) * 2, 10)

        return min(int(score), 100)

    def score_pr(
        self,
        pr: BitbucketPR,
        analysis: PRAnalysis,
        diff: PRDiff
    ) -> PRWithPriority:
        """Calculate priority and return PRWithPriority object"""
        priority_score = self.calculate_priority_score(pr, diff, analysis)

        # Update author history
        self._update_author_pr_count(pr.author)

        return PRWithPriority(
            pr=pr,
            analysis=analysis,
            priority_score=priority_score
        )

    def score_prs(
        self,
        prs: list,
        analyses: list,
        diffs: list
    ) -> list[PRWithPriority]:
        """Score multiple PRs and return sorted list"""
        results = []

        for pr, analysis, diff in zip(prs, analyses, diffs):
            result = self.score_pr(pr, analysis, diff)
            results.append(result)

        # Sort by priority (highest first)
        results.sort(key=lambda x: x.priority_score, reverse=True)

        return results

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class BitbucketPR(BaseModel):
    """Bitbucket Pull Request model"""
    id: str
    title: str
    description: str
    author: str
    source_branch: str
    destination_branch: str
    created_on: datetime
    updated_on: datetime
    link: str
    state: str
    workspace: str
    repo_slug: str


class PRDiff(BaseModel):
    """Pull Request diff model"""
    pr_id: str
    files_changed: List[str]
    additions: int
    deletions: int
    diff_content: str


class PRAnalysis(BaseModel):
    """AI analysis results for a PR"""
    pr_id: str
    good_points: List[str]
    attention_required: List[str]
    risk_factors: List[str]
    overall_quality_score: int  # 0-100
    estimated_review_time: str  # "5-10 min"
    _skipped_reason: Optional[str] = None  # "diff_too_large", "timeout", etc.
    _diff_size: Optional[int] = None  # Character count of diff


class PRWithPriority(BaseModel):
    """PR with priority score for sorting"""
    pr: BitbucketPR
    analysis: PRAnalysis
    priority_score: int  # 0-100, higher = more urgent


class UserInfo(BaseModel):
    """Information about the authenticated user"""
    uuid: str
    username: str
    display_name: str

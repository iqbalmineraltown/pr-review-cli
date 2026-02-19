from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime


class BitbucketPR(BaseModel):
    """A Bitbucket Pull Request"""
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
    """A PR diff with stats"""
    pr_id: str
    files_changed: List[str]
    additions: int
    deletions: int
    diff_content: str


class InlineComment(BaseModel):
    """A comment on a specific line of code"""
    file_path: str
    line_number: int  # Line number in NEW version (the "to" line)
    severity: str  # "critical", "high", "medium", "low"
    message: str
    code_snippet: Optional[str] = None


class PRAnalysis(BaseModel):
    """What the AI thinks about a PR"""
    pr_id: str
    good_points: List[str]
    attention_required: List[str]
    risk_factors: List[str]
    overall_quality_score: int  # 0-100
    estimated_review_time: str  # "5-10 min"
    _skipped_reason: Optional[str] = None  # "diff_too_large", "timeout", etc.
    _diff_size: Optional[int] = None  # Character count of diff
    line_comments: List[InlineComment] = []  # Per-line inline comments


class PRWithPriority(BaseModel):
    """A PR bundled with its priority score"""
    pr: BitbucketPR
    analysis: PRAnalysis
    priority_score: int  # 0-100, higher = more urgent


class UserInfo(BaseModel):
    """Who you are on Bitbucket"""
    uuid: str
    username: str
    display_name: str


class ReviewerPersona(BaseModel):
    """A reviewer persona (used in PR Defense Council mode)"""
    name: str  # e.g., "Security Sentinel"
    slug: str  # e.g., "security-sentinel"
    description: str  # e.g., "Focuses on security vulnerabilities..."
    prompt: str  # The full prompt template for this persona

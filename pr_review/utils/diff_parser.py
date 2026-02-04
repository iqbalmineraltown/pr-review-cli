"""Unified diff parser for mapping issues to specific line numbers in PRs.

This module provides functionality to parse unified diff format and extract
hunk information needed to place inline comments on the correct lines.
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pr_review.models import InlineComment


@dataclass
class DiffHunk:
    """Represents a single hunk in a unified diff.

    A hunk represents a section of changes in a file, containing information
    about the line numbers in both the old and new versions.
    """
    file_path: str
    old_start: int  # Starting line in old version
    old_lines: int  # Number of lines in old version
    new_start: int  # Starting line in new version (the "to" line we need!)
    new_lines: int  # Number of lines in new version
    lines: List[str]  # The actual diff lines (including +, -, and context)

    def get_new_line_number(self, hunk_line_index: int) -> Optional[int]:
        """Get the line number in the new version for a given hunk line index.

        Args:
            hunk_line_index: Index within self.lines

        Returns:
            Line number in the NEW version, or None if not an addition line
        """
        if hunk_line_index < 0 or hunk_line_index >= len(self.lines):
            return None

        line = self.lines[hunk_line_index]
        if not line.startswith("+"):
            return None  # Not an addition line

        # Count addition lines before this one to get the offset
        addition_offset = 0
        for i in range(hunk_line_index):
            if self.lines[i].startswith("+"):
                addition_offset += 1

        return self.new_start + addition_offset


def parse_unified_diff(diff_content: str) -> Dict[str, List[DiffHunk]]:
    """Parse unified diff format and extract hunks by file path.

    Args:
        diff_content: The unified diff content string

    Returns:
        Dictionary mapping file paths to lists of DiffHunk objects

    Example:
        >>> diff = '''diff --git a/src/file.py b/src/file.py
        ... index 123..456 789
        ... --- a/src/file.py
        ... +++ b/src/file.py
        ... @@ -10,4 +10,5 @@
        ...  context line
        ... -removed line
        ... +added line
        ...  another context'''
        >>> hunks = parse_unified_diff(diff)
        >>> assert 'src/file.py' in hunks
    """
    hunks_by_file: Dict[str, List[DiffHunk]] = {}

    lines = diff_content.split('\n')
    i = 0
    current_file = None

    # Regex patterns
    file_header_pattern = re.compile(r'^\+\+\+ b/(.+)$')
    hunk_header_pattern = re.compile(r'^@@ -(\d+),?(\d+)? \+(\d+),?(\d+)? @@')

    while i < len(lines):
        line = lines[i]

        # Check for new file header
        file_match = file_header_pattern.match(line)
        if file_match:
            current_file = file_match.group(1)
            if current_file not in hunks_by_file:
                hunks_by_file[current_file] = []
            i += 1
            continue

        # Check for hunk header
        hunk_match = hunk_header_pattern.match(line)
        if hunk_match and current_file:
            old_start = int(hunk_match.group(1))
            old_lines = int(hunk_match.group(2) or 1)
            new_start = int(hunk_match.group(3))
            new_lines = int(hunk_match.group(4) or 1)

            # Collect hunk lines until next hunk or file
            hunk_lines = []
            i += 1
            while i < len(lines):
                next_line = lines[i]
                # Stop at next hunk or file
                if next_line.startswith('@@ ') or next_line.startswith('diff --git'):
                    break
                # Only include lines that are part of the diff (start with space, +, -, or \)
                if next_line.startswith((' ', '+', '-', '\\')):
                    hunk_lines.append(next_line)
                i += 1

            hunk = DiffHunk(
                file_path=current_file,
                old_start=old_start,
                old_lines=old_lines,
                new_start=new_start,
                new_lines=new_lines,
                lines=hunk_lines
            )
            hunks_by_file[current_file].append(hunk)
            continue

        i += 1

    return hunks_by_file


def find_line_in_hunk(
    issue: str,
    file_path: str,
    hunks_by_file: Dict[str, List[DiffHunk]],
    context_lines: int = 3
) -> Optional[Tuple[int, str]]:
    """Find the most likely line number for an issue by searching in diff hunks.

    Args:
        issue: The issue description to search for
        file_path: The file path to search in
        hunks_by_file: Dictionary of file paths to hunks
        context_lines: Number of context lines to include in search

    Returns:
        Tuple of (line_number, code_snippet) or None if not found
    """
    if file_path not in hunks_by_file:
        return None

    # Normalize the issue for searching
    search_terms = [
        term.lower().strip()
        for term in issue.split()
        if len(term) > 3  # Skip very short terms
    ]

    if not search_terms:
        return None

    best_match = None
    best_score = 0

    for hunk in hunks_by_file[file_path]:
        for idx, line in enumerate(hunk.lines):
            if not line.startswith(('+', ' ')):
                continue  # Skip deletions and diff markers

            # Get the line content without the prefix
            line_content = line[1:].strip()
            if not line_content:
                continue

            # Calculate match score
            score = 0
            for term in search_terms:
                if term in line_content.lower():
                    score += 1

            if score > best_score:
                # Get the line number for this line
                if line.startswith('+'):
                    line_num = hunk.new_start + sum(
                        1 for l in hunk.lines[:idx] if l.startswith('+')
                    )
                    # Get code snippet with context
                    snippet_start = max(0, idx - context_lines)
                    snippet_end = min(len(hunk.lines), idx + context_lines + 1)
                    snippet_lines = hunk.lines[snippet_start:snippet_end]
                    snippet = '\n'.join(l[1:] if l.startswith((' ', '+', '-')) else l for l in snippet_lines)

                    best_match = (line_num, snippet)
                    best_score = score

    return best_match


def create_inline_comment(
    issue: str,
    severity: str = "medium",
    file_path: Optional[str] = None,
    line_number: Optional[int] = None,
    code_snippet: Optional[str] = None
) -> Optional[InlineComment]:
    """Create an InlineComment object with validation.

    Args:
        issue: The issue message
        severity: Severity level (critical, high, medium, low)
        file_path: File path (optional, will try to extract from issue)
        line_number: Line number (optional, will try to find from diff)
        code_snippet: Relevant code snippet (optional)

    Returns:
        InlineComment object or None if required fields missing
    """
    if not line_number or not file_path:
        return None

    # Normalize severity
    valid_severities = ["critical", "high", "medium", "low"]
    if severity.lower() not in valid_severities:
        severity = "medium"

    return InlineComment(
        file_path=file_path,
        line_number=line_number,
        severity=severity.lower(),
        message=issue,
        code_snippet=code_snippet
    )


def map_issues_to_inline_comments(
    issues: List[str],
    diff_content: str,
    default_severity: str = "medium"
) -> List[InlineComment]:
    """Map a list of issue descriptions to inline comments using diff parsing.

    Args:
        issues: List of issue descriptions from AI analysis
        diff_content: The unified diff content
        default_severity: Default severity level for comments

    Returns:
        List of InlineComment objects
    """
    inline_comments: List[InlineComment] = []

    # Parse the diff to get hunks
    hunks_by_file = parse_unified_diff(diff_content)

    # Try to extract file path from issue if mentioned
    file_path_pattern = re.compile(r'[\w/]+\.(?:py|js|ts|tsx|jsx|java|go|rs|cpp|c|h|cs|php|rb|scala|kt|swift)')

    for issue in issues:
        # Try to extract file path from issue
        file_match = file_path_pattern.search(issue)
        file_path = file_match.group(0) if file_match else None

        # Find the best matching line
        result = None
        if file_path:
            result = find_line_in_hunk(issue, file_path, hunks_by_file)

        # Create inline comment if we found a match
        if result:
            line_num, snippet = result
            inline_comments.append(create_inline_comment(
                issue=issue,
                severity=default_severity,
                file_path=file_path,
                line_number=line_num,
                code_snippet=snippet
            ))

    return inline_comments

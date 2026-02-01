import subprocess
import json
import tempfile
import os
from typing import List
import asyncio
from pathlib import Path

from .models import BitbucketPR, PRAnalysis
from .config import Config


class ClaudeAnalyzer:
    """
    Analyzes PRs using the existing Claude CLI installation.
    Communicates via subprocess calls to the 'claude' command.
    """

    DEFAULT_PROMPT = '''Analyze this pull request diff and provide:

1. GOOD_POINTS: What's well-done (code quality, patterns, testing, docs)
2. ATTENTION_REQUIRED: Issues that need reviewer focus (bugs, logic errors, security)
3. RISK_FACTORS: Potential problems (breaking changes, complexity, missing tests)
4. QUALITY_SCORE: Overall score 0-100
5. ESTIMATED_REVIEW_TIME: Quick/5min/15min/30min/60min+

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{
  "good_points": ["point1", "point2"],
  "attention_required": ["issue1", "issue2"],
  "risk_factors": ["risk1", "risk2"],
  "overall_quality_score": 85,
  "estimated_review_time": "15min"
}}

Do not include any other text outside the JSON.'''

    def __init__(self, claude_cli_path: str = None, prompt_template: str = None):
        config = Config()
        self.claude_cli_path = claude_cli_path or config.claude_cli_path
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT
        self._verify_claude_cli()

    def _verify_claude_cli(self):
        """Verify Claude CLI is available and configured"""
        try:
            result = subprocess.run(
                [self.claude_cli_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError("Claude CLI not found or not configured")
        except FileNotFoundError:
            raise RuntimeError(
                f"Claude CLI not found at '{self.claude_cli_path}'.\n"
                "Please install Claude CLI or ensure it's in your PATH."
            )

    async def analyze_pr(
        self,
        pr: BitbucketPR,
        diff: str,
        max_diff_size: int = 50000,
        skip_large: bool = True
    ) -> PRAnalysis:
        """
        Analyze a PR using Claude CLI via subprocess.

        Args:
            pr: The PR to analyze
            diff: The diff content
            max_diff_size: Maximum size before skipping (only used if skip_large=True)
            skip_large: If False, analyze all PRs regardless of size (e.g., for local diffs)
        """
        # Check if PR is too large for AI analysis (only if skip_large=True)
        if skip_large and len(diff) > max_diff_size:
            return PRAnalysis(
                pr_id=pr.id,
                good_points=["Large PR requiring detailed manual review"],
                attention_required=[
                    f"PR too large for AI analysis ({len(diff):,} characters)",
                    "Requires your expert review - highest priority",
                    "Consider breaking into smaller PRs in the future"
                ],
                risk_factors=[
                    "Large changes are harder to review thoroughly",
                    "Higher risk of unintended side effects",
                    "Testing may not cover all edge cases"
                ],
                overall_quality_score=50,
                estimated_review_time="60min+",
                _skipped_reason="diff_too_large",
                _diff_size=len(diff)
            )

        # Truncate diff if it's moderately large but still analyzable
        diff_to_analyze = diff
        if len(diff) > 30000:
            # Take first and last parts
            mid = len(diff) // 2
            diff_to_analyze = diff[:15000] + "\n\n[... diff truncated ...]\n\n" + diff[-15000:]

        prompt = self.prompt_template.format(
            title=pr.title,
            author=pr.author,
            source=pr.source_branch,
            destination=pr.destination_branch,
            diff=diff_to_analyze
        )

        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Try using claude CLI with various command patterns
            result = await self._run_claude_analysis(prompt, prompt_file)

            # Parse output
            output = result.strip()

            # Extract JSON from output (handle potential extra text)
            json_start = output.find('{')
            json_end = output.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in Claude output")

            json_str = output[json_start:json_end]
            analysis_data = json.loads(json_str)

            return PRAnalysis(
                pr_id=pr.id,
                good_points=analysis_data.get("good_points", []),
                attention_required=analysis_data.get("attention_required", []),
                risk_factors=analysis_data.get("risk_factors", []),
                overall_quality_score=analysis_data.get("overall_quality_score", 50),
                estimated_review_time=analysis_data.get("estimated_review_time", "15min"),
                _diff_size=len(diff)
            )

        except asyncio.TimeoutError:
            return PRAnalysis(
                pr_id=pr.id,
                good_points=[],
                attention_required=[
                    "AI analysis timed out - PR is very complex",
                    "Requires your immediate expert review"
                ],
                risk_factors=["Complexity exceeded analysis time limit"],
                overall_quality_score=50,
                estimated_review_time="60min+",
                _skipped_reason="timeout",
                _diff_size=len(diff)
            )
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback analysis if parsing fails
            return PRAnalysis(
                pr_id=pr.id,
                good_points=["Unable to parse AI response"],
                attention_required=[
                    "AI analysis failed - please review manually",
                    f"Error: {str(e)[:100]}"
                ],
                risk_factors=["Analysis parsing error"],
                overall_quality_score=50,
                estimated_review_time="30min",
                _skipped_reason="parse_error",
                _diff_size=len(diff)
            )
        finally:
            # Cleanup temp file
            try:
                os.unlink(prompt_file)
            except:
                pass

    async def _run_claude_analysis(self, prompt: str, prompt_file: str) -> str:
        """Run Claude CLI analysis with retry logic"""
        loop = asyncio.get_event_loop()

        # Try multiple command patterns
        commands = [
            # Pattern 1: claude ask (if available)
            [self.claude_cli_path, "ask", "--file", prompt_file, "--non-interactive"],
            # Pattern 2: claude with stdin
            None,  # Will use stdin
        ]

        for cmd in commands:
            try:
                if cmd:
                    result = await loop.run_in_executor(
                        None,
                        lambda: subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            check=False
                        )
                    )
                    if result.stdout.strip():
                        return result.stdout
                else:
                    # Fallback: use stdin
                    result = await loop.run_in_executor(
                        None,
                        lambda: subprocess.run(
                            [self.claude_cli_path],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            input=prompt,
                            check=False
                        )
                    )
                    if result.stdout.strip():
                        return result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
            except Exception:
                continue

        # If all patterns fail, raise error
        raise RuntimeError("Failed to invoke Claude CLI")

    async def analyze_prs_parallel(
        self,
        prs: List[BitbucketPR],
        diffs: List[str],
        progress_callback=None,
        skip_large: bool = True
    ) -> List[PRAnalysis]:
        """
        Analyze multiple PRs in parallel using Claude CLI.

        Args:
            prs: List of PRs to analyze
            diffs: List of diff contents
            progress_callback: Optional callback function(current, total, pr_title)
            skip_large: If False, analyze all PRs regardless of size (e.g., for local diffs)
        """
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent CLI calls
        completed_count = [0]  # Use list to make it mutable in closure
        total = len(prs)

        async def analyze_with_semaphore(index, pr, diff):
            async with semaphore:
                analysis = await self.analyze_pr(pr, diff, skip_large=skip_large)
                completed_count[0] += 1

                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed_count[0], total, pr.title)

                return analysis

        tasks = [
            analyze_with_semaphore(i, pr, diff)
            for i, (pr, diff) in enumerate(zip(prs, diffs))
        ]

        return await asyncio.gather(*tasks)

import subprocess
import json
import tempfile
import os
from typing import List
import asyncio
from pathlib import Path

from .models import BitbucketPR, PRAnalysis, InlineComment
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
{{{{"good_points": ["point1", "point2"], "attention_required": ["issue1", "issue2"], "risk_factors": ["risk1", "risk2"], "overall_quality_score": 85, "estimated_review_time": "15min"}}}}

Do not include any other text outside the JSON.'''

    def __init__(self, claude_cli_path: str = None, prompt_template: str = None):
        config = Config()
        self.claude_cli_command = config.claude_cli_command
        self.claude_cli_flags = config.claude_cli_flags
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT
        self._print_config_shown = False

    def _print_ai_config_once(self):
        """Print AI CLI config once"""
        if not hasattr(self, '_config_shown'):
            print(f"🤖 AI CLI: {self.claude_cli_command} {self.claude_cli_flags}")
            self._config_shown = True

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
        if len(diff) > 20000:
            # For large diffs, take first part only to focus on main changes
            # This helps AI provide more specific inline comments
            diff_to_analyze = diff[:25000] + "\n\n[... diff truncated to focus on main changes ...]\n\n"

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
            parsed_json = json.loads(json_str)

            # Handle GLM format which wraps response in {"type": "result", "result": "..."}
            analysis_data = self._extract_analysis_data(parsed_json)

            # Extract line_comments if present
            line_comments_raw = analysis_data.get("line_comments", [])
            line_comments = []
            for lc in line_comments_raw:
                try:
                    line_comments.append(InlineComment(**lc))
                except Exception:
                    # Skip invalid inline comments
                    pass

            return PRAnalysis(
                pr_id=pr.id,
                good_points=analysis_data.get("good_points", []),
                attention_required=analysis_data.get("attention_required", []),
                risk_factors=analysis_data.get("risk_factors", []),
                overall_quality_score=analysis_data.get("overall_quality_score", 50),
                estimated_review_time=analysis_data.get("estimated_review_time", "15min"),
                _diff_size=len(diff),
                line_comments=line_comments
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
        except (json.JSONDecodeError, ValueError, RuntimeError) as e:
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
        """Run Claude CLI analysis via shell command"""
        loop = asyncio.get_event_loop()

        cmd = f"{self.claude_cli_command} {self.claude_cli_flags}"
        cmd = cmd.replace("{prompt_file}", prompt_file)
        cmd = cmd.replace("{prompt}", prompt)

        # Use longer timeout for large prompts (more than 10k chars)
        timeout = 300 if len(prompt) > 10000 else 120

        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    input=prompt,
                    check=False
                )
            )
            if result.stdout.strip():
                return result.stdout
            elif result.stderr.strip():
                return result.stderr
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude CLI command timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to invoke Claude CLI command: {e}")

        raise RuntimeError("Claude CLI command produced no output")

    def _extract_analysis_data(self, parsed_json: dict) -> dict:
        """
        Extract analysis data from either GLM or Claude CLI format.

        GLM format: {"type": "result", "result": "```json\\n{actual_data}\\n```", ...}
        Claude CLI format: {"good_points": [...], "attention_required": [...], ...}

        Args:
            parsed_json: The parsed JSON output from the AI CLI

        Returns:
            dict with keys: good_points, attention_required, risk_factors, etc.
        """
        # Check if this is GLM format (has "type" and "result" keys)
        if isinstance(parsed_json, dict) and "type" in parsed_json and "result" in parsed_json:
            # GLM format - extract from "result" field
            result_content = parsed_json.get("result", "")

            # Find JSON within markdown code blocks
            # GLM may include conversational text before/after the code block
            import re

            # Try to find ```json...``` code block
            json_block = re.search(r'```json\s*\n(.*?)\n```', result_content, re.DOTALL)
            if json_block:
                result_content = json_block.group(1)
            else:
                # Try to find ```...``` code block (without json label)
                json_block = re.search(r'```\s*\n(.*?)\n```', result_content, re.DOTALL)
                if json_block:
                    result_content = json_block.group(1)
                else:
                    # No code block found - try stripping from edges as fallback
                    if result_content.startswith("```json"):
                        result_content = result_content[7:]  # Remove ```json
                    elif result_content.startswith("```"):
                        result_content = result_content[3:]  # Remove ```

                    if result_content.endswith("```"):
                        result_content = result_content[:-3]  # Remove trailing ```

            result_content = result_content.strip()

            # Parse the inner JSON
            try:
                return json.loads(result_content)
            except json.JSONDecodeError as e:
                # If inner JSON parsing fails, return empty analysis
                return {
                    "good_points": [],
                    "attention_required": [f"Failed to parse GLM response: {str(e)[:100]}"],
                    "risk_factors": ["GLM parsing error"],
                    "overall_quality_score": 50,
                    "estimated_review_time": "30min",
                    "line_comments": []
                }

        # Standard Claude CLI format - return as-is
        return parsed_json

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
        # Print AI config once
        self._print_ai_config_once()

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

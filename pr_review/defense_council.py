"""
PR Defense Council - Multi-Agent Review Coordinator

Orchestrates multiple specialized reviewer personas to analyze a single PR
in parallel, then aggregates their findings into a unified comprehensive review.
"""

import asyncio
import subprocess
import tempfile
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass

from .models import BitbucketPR, PRAnalysis, InlineComment, ReviewerPersona
from .config import Config


class ResultAggregator:
    """
    Aggregates analysis results from multiple reviewer personas into a unified review.

    Strategy:
    - good_points: Union of all findings
    - attention_required: Union with deduplication
    - risk_factors: Union with deduplication
    - overall_quality_score: Average of all agent scores
    - estimated_review_time: Maximum (most conservative)
    - line_comments: Merge all, deduplicate by file+line
    """

    @staticmethod
    def aggregate(persona_analyses: List[PRAnalysis], pr_id: str) -> PRAnalysis:
        """
        Aggregate multiple PRAnalysis objects into a single unified analysis.

        Args:
            persona_analyses: List of PRAnalysis objects from different personas
            pr_id: The PR ID being reviewed

        Returns:
            A single PRAnalysis with aggregated findings
        """
        if not persona_analyses:
            return PRAnalysis(
                pr_id=pr_id,
                good_points=[],
                attention_required=["No analysis available"],
                risk_factors=[],
                overall_quality_score=50,
                estimated_review_time="Unknown"
            )

        # Collect all findings
        all_good_points: List[str] = []
        all_attention_required: List[str] = []
        all_risk_factors: List[str] = []
        all_line_comments: List[InlineComment] = []

        for analysis in persona_analyses:
            all_good_points.extend(analysis.good_points)
            all_attention_required.extend(analysis.attention_required)
            all_risk_factors.extend(analysis.risk_factors)
            all_line_comments.extend(analysis.line_comments)

        # Deduplicate while preserving order (using dict as ordered set)
        def deduplicate(items: List[str]) -> List[str]:
            seen = {}
            for item in items:
                normalized = item.strip().lower()
                if normalized not in seen:
                    seen[normalized] = item
            return list(seen.values())

        # Deduplicate line comments by file + line number
        def deduplicate_line_comments(comments: List[InlineComment]) -> List[InlineComment]:
            seen = {}
            for comment in comments:
                key = (comment.file_path, comment.line_number)
                if key not in seen:
                    seen[key] = comment
                # If duplicate exists, keep the one with higher severity
                elif comment.severity < seen[key].severity:
                    # Lower severity value = more severe (critical=0, high=1, etc.)
                    seen[key] = comment
            return list(seen.values())

        # Sort line comments by severity (critical -> high -> medium -> low)
        def sort_by_severity(comments: List[InlineComment]) -> List[InlineComment]:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            return sorted(comments, key=lambda c: severity_order.get(c.severity.lower(), 4))

        # Calculate average quality score
        quality_scores = [a.overall_quality_score for a in persona_analyses if a.overall_quality_score > 0]
        avg_quality = int(sum(quality_scores) / len(quality_scores)) if quality_scores else 50

        # Find maximum (most conservative) review time
        time_order = {"quick": 1, "5min": 2, "15min": 3, "30min": 4, "60min+": 5}
        max_time = "30min"  # Default
        for analysis in persona_analyses:
            time_val = analysis.estimated_review_time.lower()
            if time_order.get(time_val, 0) > time_order.get(max_time, 0):
                max_time = analysis.estimated_review_time

        return PRAnalysis(
            pr_id=pr_id,
            good_points=deduplicate(all_good_points),
            attention_required=deduplicate(all_attention_required),
            risk_factors=deduplicate(all_risk_factors),
            overall_quality_score=avg_quality,
            estimated_review_time=max_time,
            line_comments=sort_by_severity(deduplicate_line_comments(all_line_comments))
        )


class DefenseCouncilAnalyzer:
    """
    Coordinates multiple reviewer personas to analyze a PR in parallel.

    Unlike ClaudeAnalyzer which processes multiple PRs with one agent,
    this uses multiple agents to process one PR for deeper analysis.

    Usage:
        analyzer = DefenseCouncilAnalyzer()
        analysis = await analyzer.analyze_pr(pr, diff)
        # or for multiple PRs (sequential, deep review):
        analyses = await analyzer.analyze_prs(prs, diffs)
    """

    def __init__(self):
        self.config = Config()
        self.claude_cli_command = self.config.claude_cli_command
        self.claude_cli_flags = self.config.claude_cli_flags
        self.personas = self._load_reviewer_personas()
        self._config_shown = False

    def _load_reviewer_personas(self) -> List[ReviewerPersona]:
        """
        Load reviewer personas from multiple sources with priority order.

        Priority:
        1. User config directory (~/.pr-review-cli/reviewers/) - Highest priority
        2. Project directory (reviewers/) - Default personas

        Returns:
            List of ReviewerPersona objects
        """
        import pr_review.defense_council

        # Get project directory (where this module is located)
        project_dir = Path(pr_review.defense_council.__file__).parent.parent
        project_reviewers_dir = project_dir / "reviewers"

        # Get user config directory
        user_reviewers_dir = self.config.reviewers_dir
        user_reviewers_dir.mkdir(parents=True, exist_ok=True)

        persona_slugs = ["security-sentinel", "performance-pursuer", "quality-custodian"]
        personas = []

        for slug in persona_slugs:
            # Priority: user config > project directory
            persona_file = None
            content = None
            source = None

            # Check user config first
            user_persona_file = user_reviewers_dir / f"{slug}.md"
            if user_persona_file.exists():
                persona_file = user_persona_file
                content = user_persona_file.read_text()
                source = "user"

            # Fall back to project directory
            elif project_reviewers_dir.exists():
                project_persona_file = project_reviewers_dir / f"{slug}.md"
                if project_persona_file.exists():
                    persona_file = project_persona_file
                    content = project_persona_file.read_text()
                    source = "project"

            # Fall back to built-in defaults
            if content is None:
                default_content = getattr(self, f"_DEFAULT_{slug.upper().replace('-', '_')}")
                content = default_content
                source = "builtin"
                # Create in user config for next time
                user_reviewers_dir.mkdir(parents=True, exist_ok=True)
                user_persona_file.write_text(content)

            # Remove frontmatter if present
            if content.startswith('---'):
                end_idx = content.find('\n---', 3)
                if end_idx != -1:
                    content = content[end_idx + 4:].strip()

            # Extract name from first line or use slug
            lines = content.strip().split('\n')
            name = lines[0].strip('#').strip() if lines else slug.title()
            description = self._extract_description(content)

            personas.append(ReviewerPersona(
                name=name,
                slug=slug,
                description=description,
                prompt=content
            ))

        # Create README in user config if it doesn't exist
        readme_file = user_reviewers_dir / "README.md"
        if not readme_file.exists():
            # Copy from project directory if available, otherwise use default
            if project_reviewers_dir.exists():
                project_readme = project_reviewers_dir / "README.md"
                if project_readme.exists():
                    readme_file.write_text(project_readme.read_text())
                else:
                    readme_file.write_text(self._DEFAULT_README)
            else:
                readme_file.write_text(self._DEFAULT_README)

        return personas

    def _extract_description(self, content: str) -> str:
        """Extract first paragraph as description"""
        lines = content.split('\n')
        for line in lines[1:]:  # Skip first line (title)
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:200]  # First 200 chars
        return "Specialized reviewer persona"

    def _print_ai_config_once(self):
        """Print AI CLI config once"""
        if not self._config_shown:
            print(f"🤖 AI CLI: {self.claude_cli_command} {self.claude_cli_flags}")
            print(f"⚔️  PR Defense Council: {len(self.personas)} reviewer personas")
            for persona in self.personas:
                print(f"   • {persona.name}")
            self._config_shown = True

    async def analyze_pr(
        self,
        pr: BitbucketPR,
        diff: str,
        max_diff_size: int = 50000
    ) -> PRAnalysis:
        """
        Analyze a single PR using all reviewer personas in parallel.

        Args:
            pr: The PR to analyze
            diff: The diff content
            max_diff_size: Maximum size before skipping large PR handling

        Returns:
            Aggregated PRAnalysis from all personas
        """
        self._print_ai_config_once()

        # Check for extremely large PRs
        if len(diff) > max_diff_size:
            # Still run analysis but note the size
            truncated_diff = diff[:max_diff_size] + "\n\n[... diff truncated ...]\n\n"
        else:
            truncated_diff = diff

        # Run all personas in parallel
        tasks = [
            self._analyze_with_persona(pr, truncated_diff, persona)
            for persona in self.personas
        ]

        persona_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and get valid analyses
        valid_analyses = []
        for i, result in enumerate(persona_results):
            if isinstance(result, Exception):
                # Create fallback analysis for failed persona
                valid_analyses.append(PRAnalysis(
                    pr_id=pr.id,
                    good_points=[],
                    attention_required=[f"{self.personas[i].name} analysis failed: {str(result)[:100]}"],
                    risk_factors=["Persona analysis error"],
                    overall_quality_score=50,
                    estimated_review_time="Unknown"
                ))
            else:
                valid_analyses.append(result)

        # Aggregate all results
        return ResultAggregator.aggregate(valid_analyses, pr.id)

    async def _analyze_with_persona(
        self,
        pr: BitbucketPR,
        diff: str,
        persona: ReviewerPersona
    ) -> PRAnalysis:
        """
        Analyze PR with a specific reviewer persona.

        Args:
            pr: The PR to analyze
            diff: The diff content
            persona: The reviewer persona to use

        Returns:
            PRAnalysis from this persona
        """
        prompt = persona.prompt.format(
            title=pr.title,
            author=pr.author,
            source=pr.source_branch,
            destination=pr.destination_branch,
            diff=diff
        )

        # Write prompt to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            result = await self._run_claude_analysis(prompt, prompt_file)
            output = result.strip()

            # Extract JSON
            json_start = output.find('{')
            json_end = output.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in Claude output")

            json_str = output[json_start:json_end]
            parsed_json = json.loads(json_str)

            # Handle GLM format
            analysis_data = self._extract_analysis_data(parsed_json, persona.name)

            # Extract line_comments
            line_comments_raw = analysis_data.get("line_comments", [])
            line_comments = []
            for lc in line_comments_raw:
                try:
                    line_comments.append(InlineComment(**lc))
                except Exception:
                    pass

            return PRAnalysis(
                pr_id=pr.id,
                good_points=analysis_data.get("good_points", []),
                attention_required=analysis_data.get("attention_required", []),
                risk_factors=analysis_data.get("risk_factors", []),
                overall_quality_score=analysis_data.get("overall_quality_score", 50),
                estimated_review_time=analysis_data.get("estimated_review_time", "15min"),
                line_comments=line_comments
            )

        except asyncio.TimeoutError:
            return PRAnalysis(
                pr_id=pr.id,
                good_points=[],
                attention_required=[f"{persona.name} analysis timed out"],
                risk_factors=["Persona timeout"],
                overall_quality_score=50,
                estimated_review_time="Unknown"
            )
        except (json.JSONDecodeError, ValueError, RuntimeError) as e:
            # Provide more detailed error for debugging
            error_msg = str(e)
            if "No JSON found" in error_msg:
                return PRAnalysis(
                    pr_id=pr.id,
                    good_points=[],
                    attention_required=[f"{persona.name}: AI response did not contain valid JSON"],
                    risk_factors=["AI response format error"],
                    overall_quality_score=50,
                    estimated_review_time="Unknown"
                )
            else:
                return PRAnalysis(
                    pr_id=pr.id,
                    good_points=[],
                    attention_required=[f"{persona.name}: Analysis failed - {error_msg[:150]}"],
                    risk_factors=["Persona analysis error"],
                    overall_quality_score=50,
                    estimated_review_time="Unknown"
                )
        finally:
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

        timeout = 300  # 5 minutes for persona analysis

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
            raise RuntimeError(f"Failed to invoke Claude CLI: {e}")

        raise RuntimeError("Claude CLI produced no output")

    def _extract_analysis_data(self, parsed_json: dict, persona_name: str = "AI") -> dict:
        """Extract analysis data from GLM or Claude CLI format"""
        if isinstance(parsed_json, dict) and "type" in parsed_json and "result" in parsed_json:
            result_content = parsed_json.get("result", "")

            json_block = re.search(r'```json\s*\n(.*?)\n```', result_content, re.DOTALL)
            if json_block:
                result_content = json_block.group(1)
            else:
                json_block = re.search(r'```\s*\n(.*?)\n```', result_content, re.DOTALL)
                if json_block:
                    result_content = json_block.group(1)
                else:
                    if result_content.startswith("```json"):
                        result_content = result_content[7:]
                    elif result_content.startswith("```"):
                        result_content = result_content[3:]
                    if result_content.endswith("```"):
                        result_content = result_content[:-3]

            result_content = result_content.strip()

            try:
                return json.loads(result_content)
            except json.JSONDecodeError as e:
                # Return more descriptive error with persona name
                return {
                    "good_points": [],
                    "attention_required": [f"{persona_name}: Failed to parse AI response (invalid JSON format)"],
                    "risk_factors": ["AI response parsing error"],
                    "overall_quality_score": 50,
                    "estimated_review_time": "30min",
                    "line_comments": []
                }

        return parsed_json

    async def analyze_prs(
        self,
        prs: List[BitbucketPR],
        diffs: List[str],
        progress_callback: Optional[Callable] = None
    ) -> List[PRAnalysis]:
        """
        Analyze multiple PRs sequentially (each gets full multi-agent review).

        Note: Unlike ClaudeAnalyzer, this processes PRs sequentially because
        each PR already uses parallelism across personas.

        Args:
            prs: List of PRs to analyze
            diffs: List of diff contents
            progress_callback: Optional callback(current, total, pr_title)

        Returns:
            List of aggregated PRAnalysis objects
        """
        self._print_ai_config_once()

        total = len(prs)
        analyses = []

        for i, (pr, diff) in enumerate(zip(prs, diffs), 1):
            if progress_callback:
                progress_callback(i, total, pr.title)

            analysis = await self.analyze_pr(pr, diff)
            analyses.append(analysis)

        return analyses

    # Default persona prompts
    _DEFAULT_SECURITY_SENTINEL = '''# Security Sentinel

You are the Security Sentinel, a specialized code reviewer focused exclusively on security vulnerabilities, authentication issues, and potential exploits. Your duty is to protect the codebase from threats.

Analyze this pull request with a security-first mindset:

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

Focus Areas:
- OWASP Top 10 vulnerabilities (SQL injection, XSS, CSRF, etc.)
- Authentication and authorization flaws
- Sensitive data exposure
- Insecure dependencies
- Cryptographic issues
- Input validation
- Session management
- API security

Provide your findings in JSON format:
{{
  "good_points": ["security-positive finding 1", "finding 2"],
  "attention_required": ["security issue requiring fix 1", "issue 2"],
  "risk_factors": ["potential security risk 1", "risk 2"],
  "overall_quality_score": 85,
  "estimated_review_time": "15min",
  "line_comments": [
    {{
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "critical",
      "message": "SQL injection vulnerability - user input not sanitized",
      "code_snippet": "optional relevant code"
    }}
  ]
}}

Severity levels: critical, high, medium, low'''

    _DEFAULT_PERFORMANCE_PURSUER = '''# Performance Pursuer

You are the Performance Pursuer, a specialized code reviewer obsessed with efficiency, scalability, and speed. Your mission is to identify bottlenecks and optimize resource usage.

Analyze this pull request with performance as your primary concern:

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

Focus Areas:
- Algorithm efficiency (Big O complexity)
- Database query optimization (N+1 problems)
- Caching strategies
- Memory usage patterns
- I/O operations
- Concurrency and parallelism
- Resource cleanup
- API response times
- Loop optimizations

Provide your findings in JSON format:
{{
  "good_points": ["performance-positive finding 1", "finding 2"],
  "attention_required": ["performance issue 1", "issue 2"],
  "risk_factors": ["scalability concern 1", "concern 2"],
  "overall_quality_score": 75,
  "estimated_review_time": "20min",
  "line_comments": [
    {{
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "high",
      "message": "N+1 query problem in loop - consider eager loading",
      "code_snippet": "optional relevant code"
    }}
  ]
}}

Severity levels: critical, high, medium, low'''

    _DEFAULT_QUALITY_CUSTODIAN = '''# Code Quality Custodian

You are the Code Quality Custodian, guardian of clean code, maintainability, and software engineering excellence. You ensure the codebase remains elegant and sustainable.

Analyze this pull request with code quality and maintainability as your focus:

PR Title: {title}
Author: {author}
Branch: {source} → {destination}

Diff:
{diff}

Focus Areas:
- SOLID principles adherence
- Design patterns usage
- Code duplication (DRY principle)
- Naming conventions and clarity
- Function/class complexity
- Error handling completeness
- Documentation quality
- Test coverage and quality
- Type safety and validation
- Code organization and modularity

Provide your findings in JSON format:
{{
  "good_points": ["quality-positive finding 1", "finding 2"],
  "attention_required": ["quality issue 1", "issue 2"],
  "risk_factors": ["maintainability risk 1", "risk 2"],
  "overall_quality_score": 80,
  "estimated_review_time": "15min",
  "line_comments": [
    {{
      "file_path": "path/to/file.py",
      "line_number": 42,
      "severity": "medium",
      "message": "Function too complex - consider breaking into smaller functions",
      "code_snippet": "optional relevant code"
    }}
  ]
}}

Severity levels: critical, high, medium, low'''

    _DEFAULT_README = '''# PR Defense Council - Reviewer Personas

This directory contains specialized reviewer personas used in PR Defense Council mode (`--pr-defense` flag).

## What is PR Defense Council?

PR Defense Council mode runs multiple specialized AI reviewer agents in parallel, each analyzing the PR from a different perspective:

- **Security Sentinel** - Focuses on security vulnerabilities and threats
- **Performance Pursuer** - Identifies bottlenecks and optimization opportunities
- **Code Quality Custodian** - Ensures clean code and maintainability

## Customizing Personas

You can edit any `.md` file in this directory to customize the reviewer persona's prompt. Changes take effect on the next run.

## Files

- `security-sentinel.md` - Security-focused reviewer
- `performance-pursuer.md` - Performance-focused reviewer
- `quality-custodian.md` - Code quality-focused reviewer

## Usage

```bash
# Run PR Defense Council on all PRs
pr-review review workspace repo --pr-defense

# Run on a single PR
pr-review review --pr-url https://bitbucket.org/workspace/repo/pull-requests/123 --pr-defense

# Auto-post council review
pr-review review workspace repo --pr-defense --post
```

## Adding New Personas

To add a new reviewer persona:

1. Create a new `.md` file in this directory (e.g., `testing-guru.md`)
2. Use the template structure with placeholder variables:
   - `{title}` - PR title
   - `{author}` - PR author
   - `{source}` - Source branch
   - `{destination}` - Destination branch
   - `{diff}` - Diff content

3. The file will be automatically loaded on next run
'''

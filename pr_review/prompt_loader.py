import os
from pathlib import Path
from typing import List, Dict, Optional
import frontmatter  # For parsing markdown with metadata


class PromptLoader:
    """Load and manage custom analysis prompts from markdown files"""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / ".pr-review-cli"
        self.config_dir = Path(config_dir)
        self.prompts_dir = self.config_dir / "prompts"
        self._ensure_directories()

    def _ensure_directories(self):
        """Create config directories if they don't exist"""
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

        # Create default prompt if missing
        default_prompt_path = self.prompts_dir / "default.md"
        if not default_prompt_path.exists():
            self._create_default_prompt(default_prompt_path)

    def _create_default_prompt(self, path: Path):
        """Create the built-in default prompt template"""
        default_content = '''# PR Analysis Prompt

Analyze this pull request comprehensively.

## Analysis Requirements

### GOOD_POINTS
What did the author do well?
- Code quality and patterns
- Test coverage
- Documentation
- Best practices

### ATTENTION_REQUIRED
What issues need your review?
- Bugs or logic errors
- Security vulnerabilities
- Breaking changes
- Missing error handling

### RISK_FACTORS
What could cause problems?
- Complexity concerns
- Missing test coverage
- Edge cases
- Integration risks

### QUALITY_SCORE
Overall score (0-100):
- 90-100: Excellent, minimal review needed
- 70-89: Good, standard review
- 50-69: Acceptable, needs careful review
- 30-49: Concerning, thorough review required
- 0-29: Major issues, extensive review needed

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
'''
        path.write_text(default_content)

    def list_prompts(self) -> List[str]:
        """List all available prompts"""
        return [
            f.stem for f in self.prompts_dir.glob("*.md")
            if not f.name.startswith("_")
        ]

    def load_prompt(self, name: str) -> str:
        """Load a specific prompt by name"""
        prompt_path = self.prompts_dir / f"{name}.md"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt '{name}' not found in {self.prompts_dir}")

        # Read markdown content
        content = prompt_path.read_text()

        # Parse frontmatter if present
        try:
            post = frontmatter.load(str(prompt_path))
            return post.content
        except:
            return content

    def get_prompt_metadata(self, name: str) -> Dict:
        """Get metadata about a prompt"""
        prompt_path = self.prompts_dir / f"{name}.md"

        if not prompt_path.exists():
            return {}

        try:
            post = frontmatter.load(str(prompt_path))
            return post.metadata
        except:
            return {}

    def get_all_prompts_info(self) -> List[Dict]:
        """Get info about all available prompts"""
        prompts = []
        for prompt_file in self.prompts_dir.glob("*.md"):
            if prompt_file.name.startswith("_"):
                continue

            name = prompt_file.stem
            metadata = self.get_prompt_metadata(name)

            prompts.append({
                "name": name,
                "description": metadata.get("description", f"Custom prompt: {name}"),
                "tags": metadata.get("tags", []),
                "path": str(prompt_file)
            })

        return prompts

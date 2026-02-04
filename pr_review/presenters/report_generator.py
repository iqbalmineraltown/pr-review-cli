from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import List
from pathlib import Path
import json

from ..models import PRWithPriority
from ..priority_scorer import PriorityScorer


def risk_color(risk_level: str) -> str:
    """Get color for risk level"""
    colors = {
        "CRITICAL": "red",
        "HIGH": "bright_red",
        "MEDIUM": "yellow",
        "LOW": "green"
    }
    return colors.get(risk_level, "white")


def generate_markdown_for_pr(pr_with_priority: PRWithPriority) -> str:
    """Generate markdown content for a single PR (for posting as comment)"""
    pr = pr_with_priority.pr
    analysis = pr_with_priority.analysis

    lines = []
    lines.append(f"## 🤖 AI PR Review: {pr.title}\n\n")
    lines.append(f"**Priority Score:** {pr_with_priority.priority_score}/100\n")
    lines.append(f"**Quality Score:** {analysis.overall_quality_score}/100\n")
    lines.append(f"**Est. Review Time:** {analysis.estimated_review_time}\n\n")

    if analysis._skipped_reason:
        lines.append(f"### ⚠️ MANUAL REVIEW REQUIRED\n\n")
        lines.append(f"- **Reason:** {analysis._skipped_reason}\n")
        if analysis._diff_size:
            lines.append(f"- **Diff Size:** {analysis._diff_size:,} characters\n")
        lines.append("\n")
    else:
        if analysis.good_points:
            lines.append("### ✅ Good Points\n\n")
            for point in analysis.good_points:
                lines.append(f"- {point}\n")
            lines.append("\n")

        if analysis.attention_required:
            lines.append("### ⚠️ Attention Required\n\n")
            for attn in analysis.attention_required:
                lines.append(f"- {attn}\n")
            lines.append("\n")

        if analysis.risk_factors:
            lines.append("### 🔍 Risk Factors\n\n")
            for risk in analysis.risk_factors:
                lines.append(f"- {risk}\n")
            lines.append("\n")

        # Add inline comments summary
        if analysis.line_comments:
            lines.append("### 📍 Inline Comments\n\n")
            lines.append(f"This review also includes {len(analysis.line_comments)} inline comment(s) on specific lines of code.\n\n")
            lines.append("---\n\n")
            lines.append("*Posted by PR Review CLI*")
            return "".join(lines)

    lines.append("---\n\n")
    lines.append("*Posted by PR Review CLI*")

    return "".join(lines)


def generate_terminal_report(prs_with_priority: List[PRWithPriority]):
    """Generate beautiful terminal output"""
    console = Console()

    # Summary stats
    console.print()
    console.print(Panel.fit(
        "[bold cyan]📊 PR Review Report[/bold cyan]",
        border_style="cyan"
    ))

    total = len(prs_with_priority)
    console.print(f"Total PRs: [bold]{total}[/bold]")

    # Count by risk level
    for risk in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = sum(1 for p in prs_with_priority if PriorityScorer.get_risk_level(p.priority_score) == risk)
        if count > 0:
            color = risk_color(risk)
            console.print(f"  [{color}]{risk}[/{color}]: {count}")

    # Count large PRs
    large_prs = [p for p in prs_with_priority if p.analysis._skipped_reason]
    if large_prs:
        console.print(f"  [yellow]WARNING: Large PRs (manual review): {len(large_prs)}[/yellow]")

    console.print()

    # Group by risk level
    for risk_level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        risk_prs = [p for p in prs_with_priority if PriorityScorer.get_risk_level(p.priority_score) == risk_level]
        if not risk_prs:
            continue

        console.print(f"[bold][{risk_color(risk_level)}]{risk_level}[/{risk_color(risk_level)}][/bold] ({len(risk_prs)} PRs)\n")

        for item in risk_prs:
            pr = item.pr
            analysis = item.analysis

            # Special display for large PRs
            if analysis._skipped_reason:
                console.print(Panel.fit(
                    f"[bold]Title:[/bold] {pr.title}\n"
                    f"[bold]Repository:[/bold] {pr.workspace}/{pr.repo_slug}\n"
                    f"[bold]Author:[/bold] {pr.author} | "
                    f"[bold]Branch:[/bold] {pr.source_branch} → {pr.destination_branch}\n"
                    f"[bold]Priority Score:[/bold] {item.priority_score}/100 | "
                    f"[bold]Status:[/bold] [red]MANUAL REVIEW REQUIRED[/red]\n"
                    f"[bold]Diff Size:[/bold] {analysis._diff_size:,} characters\n"
                    f"[bold]Reason:[/bold] {analysis._skipped_reason.replace('_', ' ').title()}\n"
                    f"[bold]Link:[/bold] {pr.link}\n\n"
                    f"[red]⚠ {', '.join(analysis.attention_required[:2])}[/red]",
                    title=f"#{pr.id} - 🔴 LARGE PR",
                    border_style="red"
                ))
            else:
                # Normal display for analyzed PRs
                good_points_text = "\n".join(f"  • {p}" for p in analysis.good_points[:3]) if analysis.good_points else "  • None identified"
                attention_text = "\n".join(f"  • {a}" for a in analysis.attention_required[:3]) if analysis.attention_required else "  • None requiring attention"

                panel_content = (
                    f"[bold]Title:[/bold] {pr.title}\n"
                    f"[bold]Repository:[/bold] {pr.workspace}/{pr.repo_slug}\n"
                    f"[bold]Author:[/bold] {pr.author} | "
                    f"[bold]Branch:[/bold] {pr.source_branch} → {pr.destination_branch}\n"
                    f"[bold]Priority Score:[/bold] {item.priority_score}/100 | "
                    f"[bold]Quality:[/bold] {analysis.overall_quality_score}/100\n"
                    f"[bold]Est. Review Time:[/bold] {analysis.estimated_review_time}\n"
                    f"[bold]Link:[/bold] {pr.link}\n\n"
                    f"[green]✓ Good Points:[/green]\n{good_points_text}\n\n"
                    f"[red]⚠ Attention Required:[/red]\n{attention_text}"
                )

                # Add inline comments summary if available
                if analysis.line_comments:
                    panel_content += f"\n\n[cyan]📍 Inline Comments:[/cyan] [dim]{len(analysis.line_comments)} comment(s)[/dim]"

                console.print(Panel.fit(
                    panel_content,
                    title=f"#{pr.id}",
                    border_style=risk_color(risk_level)
                ))

        console.print()


def generate_markdown_report(prs_with_priority: List[PRWithPriority], output_path: str):
    """Export to markdown file"""
    markdown = []
    markdown.append("# PR Review Report\n\n")
    markdown.append(f"**Generated:** {prs_with_priority[0].pr.updated_on.strftime('%Y-%m-%d %H:%M')}\n\n")
    markdown.append("## Summary\n\n")
    markdown.append(f"- **Total PRs:** {len(prs_with_priority)}\n")

    for risk in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = sum(1 for p in prs_with_priority if PriorityScorer.get_risk_level(p.priority_score) == risk)
        if count > 0:
            markdown.append(f"- **{risk}:** {count}\n")

    markdown.append("\n---\n\n")

    # Group by risk level
    for risk_level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        risk_prs = [p for p in prs_with_priority if PriorityScorer.get_risk_level(p.priority_score) == risk_level]
        if not risk_prs:
            continue

        markdown.append(f"## {risk_level} ({len(risk_prs)} PRs)\n\n")

        for item in risk_prs:
            pr = item.pr
            analysis = item.analysis

            markdown.append(f"### #{pr.id}: {pr.title}\n\n")
            markdown.append(f"- **Repository:** `{pr.workspace}/{pr.repo_slug}`\n")
            markdown.append(f"- **Author:** {pr.author}\n")
            markdown.append(f"- **Branch:** `{pr.source_branch}` → `{pr.destination_branch}`\n")
            markdown.append(f"- **Priority Score:** {item.priority_score}/100\n")
            markdown.append(f"- **Quality Score:** {analysis.overall_quality_score}/100\n")
            markdown.append(f"- **Est. Review Time:** {analysis.estimated_review_time}\n")
            markdown.append(f"- **Link:** [View PR]({pr.link})\n\n")

            if analysis._skipped_reason:
                markdown.append(f"**⚠️ MANUAL REVIEW REQUIRED**\n\n")
                markdown.append(f"- **Reason:** {analysis._skipped_reason}\n")
                markdown.append(f"- **Diff Size:** {analysis._diff_size:,} characters\n\n")
            else:
                if analysis.good_points:
                    markdown.append("**✅ Good Points:**\n")
                    for point in analysis.good_points:
                        markdown.append(f"- {point}\n")
                    markdown.append("\n")

                if analysis.attention_required:
                    markdown.append("**⚠️ Attention Required:**\n")
                    for item_attn in analysis.attention_required:
                        markdown.append(f"- {item_attn}\n")
                    markdown.append("\n")

                if analysis.risk_factors:
                    markdown.append("**🔍 Risk Factors:**\n")
                    for risk in analysis.risk_factors:
                        markdown.append(f"- {risk}\n")
                    markdown.append("\n")

                # Add inline comments section
                if analysis.line_comments:
                    markdown.append("**📍 Inline Comments:**\n\n")
                    for comment in analysis.line_comments:
                        severity_emoji = {
                            "critical": "🔴",
                            "high": "🟠",
                            "medium": "🟡",
                            "low": "🟢"
                        }.get(comment.severity, "⚪")
                        markdown.append(f"{severity_emoji} **[{comment.severity.upper()}]** `{comment.file_path}:{comment.line_number}`\n")
                        markdown.append(f"   {comment.message}\n")
                        if comment.code_snippet:
                            markdown.append(f"   ```\n   {comment.code_snippet[:100]}...\n   ```\n")
                        markdown.append("\n")

            markdown.append("---\n\n")

    output_file = Path(output_path)
    output_file.write_text("".join(markdown))


def generate_json_report(prs_with_priority: List[PRWithPriority], output_path: str):
    """Export to JSON for further processing"""
    data = []

    for item in prs_with_priority:
        pr = item.pr
        analysis = item.analysis

        pr_data = {
            "id": pr.id,
            "title": pr.title,
            "author": pr.author,
            "source_branch": pr.source_branch,
            "destination_branch": pr.destination_branch,
            "link": pr.link,
            "priority_score": item.priority_score,
            "risk_level": PriorityScorer.get_risk_level(item.priority_score),
            "analysis": {
                "good_points": analysis.good_points,
                "attention_required": analysis.attention_required,
                "risk_factors": analysis.risk_factors,
                "overall_quality_score": analysis.overall_quality_score,
                "estimated_review_time": analysis.estimated_review_time,
                "skipped_reason": analysis._skipped_reason,
                "diff_size": analysis._diff_size,
                "line_comments": [
                    {
                        "file_path": c.file_path,
                        "line_number": c.line_number,
                        "severity": c.severity,
                        "message": c.message,
                        "code_snippet": c.code_snippet
                    }
                    for c in analysis.line_comments
                ]
            }
        }
        data.append(pr_data)

    output_file = Path(output_path)
    output_file.write_text(json.dumps(data, indent=2))

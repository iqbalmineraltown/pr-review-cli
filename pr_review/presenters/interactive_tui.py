from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static
from textual.containers import Horizontal, Vertical
from rich.text import Text
from rich.console import Console
from rich.panel import Panel
import webbrowser
import asyncio
import sys
import time
from typing import List, Optional

from ..models import PRWithPriority
from ..priority_scorer import PriorityScorer
from ..config import Config
from ..bitbucket_client import BitbucketClient


# Maximum comment size for Bitbucket API (with safety margin)
MAX_COMMENT_SIZE = 30000

# Auto-resume delay after posting comment (in seconds)
AUTO_RESUME_SECONDS = 5


class PRDataTable(DataTable):
    """Custom DataTable that monitors cursor position"""

    def on_mount(self):
        """Set up polling for cursor changes"""
        self.set_interval(0.1, self._check_cursor_change)
        self._last_cursor_row = self.cursor_row

    def _check_cursor_change(self):
        """Check if cursor row changed and notify app"""
        if self.cursor_row != self._last_cursor_row:
            self._last_cursor_row = self.cursor_row

            # Notify parent app
            if hasattr(self.app, 'selected_pr') and hasattr(self.app, 'prs_with_priority'):
                if (self.cursor_row is not None and
                    0 <= self.cursor_row < len(self.app.prs_with_priority)):
                    item = self.app.prs_with_priority[self.cursor_row]
                    self.app.selected_pr = item
                    self.app._update_detail_panel(item)


class PRReviewApp(App):
    """Interactive TUI for PR review"""

    CSS = """
    Screen {
        layout: vertical;
    }

    #pr_list {
        width: 50%;
        height: 1fr;
    }

    #pr_details {
        width: 50%;
        height: 1fr;
        border: solid $primary;
        padding: 1;
        overflow-y: scroll;
    }

    DataTable {
        height: 1fr;
    }

    .critical {
        text-style: bold;
        color: red;
    }

    .high {
        color: ansi_bright_red;
    }

    .medium {
        color: yellow;
    }

    .low {
        color: green;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("o", "open_in_browser", "Open in Browser"),
        ("p", "post_comment", "Post Comment"),
    ]

    def __init__(self, prs_with_priority: List[PRWithPriority]):
        super().__init__()
        self.prs_with_priority = prs_with_priority
        self.selected_pr: Optional[PRWithPriority] = None
        self._relaunch_requested = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="pr_list"):
                yield PRDataTable(id="prs")
            with Vertical(id="pr_details"):
                yield Static(id="detail_content")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the data table"""
        table = self.query_one("#prs", PRDataTable)
        table.add_columns("Priority", "Risk", "Repository", "Title", "Author", "Score")

        for item in self.prs_with_priority:
            pr = item.pr

            # Calculate risk level from priority score
            risk_level = PriorityScorer.get_risk_level(item.priority_score)
            risk_class = {
                "CRITICAL": "critical",
                "HIGH": "high",
                "MEDIUM": "medium",
                "LOW": "low"
            }.get(risk_level, "")

            # Truncate title if too long
            title = pr.title[:30] + "..." if len(pr.title) > 30 else pr.title

            # Show repo slug
            repo_display = pr.repo_slug[:15] + "..." if len(pr.repo_slug) > 15 else pr.repo_slug

            table.add_row(
                str(item.priority_score),
                risk_level,
                repo_display,
                title,
                pr.author,
                str(item.analysis.overall_quality_score),
                key=item.pr.id
            )

        # Select first row by default and show its details
        if self.prs_with_priority:
            table.cursor_type = "row"
            table.focus()  # Set focus to the table so it receives keyboard events
            self.selected_pr = self.prs_with_priority[0]
            self._update_detail_panel(self.prs_with_priority[0])

    def _update_detail_panel(self, item: PRWithPriority):
        """Update the detail panel with PR information"""
        detail_content = self.query_one("#detail_content", Static)
        pr = item.pr
        analysis = item.analysis

        # Create a Text object for rich formatting
        text = Text()
        text.append(f"#{pr.id}: ", style="bold")
        text.append(f"{pr.title}\n\n")
        text.append("Repository: ", style="dim")
        text.append(f"{pr.workspace}/{pr.repo_slug}\n")
        text.append("Author: ", style="dim")
        text.append(f"{pr.author}\n")
        text.append("Branch: ", style="dim")
        text.append(f"{pr.source_branch} → {pr.destination_branch}\n")
        text.append("Priority Score: ", style="dim")
        text.append(f"{item.priority_score}/100\n")
        text.append("Quality Score: ", style="dim")
        text.append(f"{analysis.overall_quality_score}/100\n")
        text.append("Est. Review Time: ", style="dim")
        text.append(f"{analysis.estimated_review_time}\n")
        text.append("Link: ", style="dim")
        text.append(f"{pr.link}\n")
        text.append("\n")

        if analysis._skipped_reason:
            text.append("⚠️  MANUAL REVIEW REQUIRED\n", style="bold red")
            text.append("Reason: ", style="yellow")
            text.append(f"{analysis._skipped_reason}\n")
            if analysis._diff_size:
                text.append("Diff Size: ", style="yellow")
                text.append(f"{analysis._diff_size:,} characters\n")
            text.append("\n")

        if analysis.good_points:
            text.append("✅ Good Points\n", style="bold green")
            for point in analysis.good_points:
                text.append(f"  • {point}\n")
            text.append("\n")

        if analysis.attention_required:
            text.append("⚠️  Attention Required\n", style="bold red")
            for attn in analysis.attention_required:
                text.append(f"  • {attn}\n")
            text.append("\n")

        if analysis.risk_factors:
            text.append("🔍 Risk Factors\n", style="bold yellow")
            for risk in analysis.risk_factors:
                text.append(f"  • {risk}\n")
            text.append("\n")

        detail_content.update(text)

    def action_open_in_browser(self) -> None:
        """Open selected PR in browser"""
        if self.selected_pr:
            webbrowser.open(self.selected_pr.pr.link)

    def _format_analysis_as_markdown(self, item: PRWithPriority) -> str:
        """Format PR analysis as markdown for posting as comment"""
        pr = item.pr
        analysis = item.analysis

        # Validate we have meaningful content to post
        has_content = (
            analysis._skipped_reason or
            analysis.good_points or
            analysis.attention_required or
            analysis.risk_factors
        )

        lines = []
        lines.append(f"## 🤖 AI PR Review: {pr.title}\n\n")
        lines.append(f"**Priority Score:** {item.priority_score}/100\n")
        lines.append(f"**Quality Score:** {analysis.overall_quality_score}/100\n")
        lines.append(f"**Est. Review Time:** {analysis.estimated_review_time}\n\n")

        if not has_content:
            # Return minimal comment for PRs without analysis data
            lines.append("**Note:** No detailed analysis available for this PR.\n\n")
            lines.append("---\n\n")
            lines.append("*Posted by PR Review CLI*")
            return "".join(lines)

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

        lines.append("---\n\n")
        lines.append("*Posted by PR Review CLI*")

        markdown = "".join(lines)

        # Validate size against Bitbucket API limit
        if len(markdown) > MAX_COMMENT_SIZE:
            # Truncate with notice
            markdown = markdown[:MAX_COMMENT_SIZE - 200] + "\n\n... (truncated due to Bitbucket size limit) ...\n\n---\n\n*Posted by PR Review CLI*"

        return markdown

    def _post_comment_terminal(self) -> bool:
        """Post comment to PR using terminal UI. Returns True on success."""
        if not self.selected_pr:
            return False

        pr = self.selected_pr.pr
        console = Console()

        try:
            # Clear screen for clean terminal output
            console.clear()

            # Show header
            title_display = pr.title[:47] + "..." if len(pr.title) > 50 else pr.title
            console.print(Panel.fit(
                f"[bold cyan]Posting Comment[/bold cyan]\n"
                f"[dim]PR: #{pr.id} - {title_display}[/dim]",
                border_style="cyan"
            ))

            # Format comment as markdown
            markdown = self._format_analysis_as_markdown(self.selected_pr)

            # Validate size before attempting to post
            if len(markdown) > MAX_COMMENT_SIZE:
                console.print(f"\n[yellow]⚠️  Comment too large for Bitbucket API[/yellow]")
                console.print(f"[dim]Size: {len(markdown)} characters (limit: ~32,000)[/dim]")
                console.print("\n[dim]The comment has been truncated to fit within the limit.[/dim]")

            # Show preview
            console.print("\n[bold]Comment Preview:[/bold]")
            preview_text = markdown[:500] + "..." if len(markdown) > 500 else markdown
            console.print(Panel(preview_text, border_style="dim"))

            # Post comment
            with console.status("[cyan]Posting comment to Bitbucket...[/cyan]"):
                async def _post():
                    config = Config()
                    async with BitbucketClient(
                        email=config.bitbucket_email,
                        api_token=config.bitbucket_api_token,
                        base_url=config.bitbucket_base_url
                    ) as client:
                        return await client.post_pr_comment(
                            workspace=pr.workspace,
                            repo_slug=pr.repo_slug,
                            pr_id=pr.id,
                            content=markdown
                        )

                result = asyncio.run(_post())

            # Success
            console.print("\n[green]✓[/green] [bold green]Comment posted successfully![/bold green]")
            console.print(f"[dim]Comment ID: {result.get('id', 'N/A')}[/dim]")

        except RuntimeError as e:
            console.print(f"\n[red]❌ Error:[/red] {e}")
        except Exception as e:
            console.print(f"\n[red]❌ Unexpected Error:[/red] {e}")

        # Auto-resume after a brief delay
        console.print(f"\n[dim]Returning to TUI in {AUTO_RESUME_SECONDS} seconds...[/dim]")
        time.sleep(AUTO_RESUME_SECONDS)

        return True

    def action_post_comment(self) -> None:
        """Post analysis as comment to selected PR"""
        if not self.selected_pr:
            return

        # Store the PR to post comment for
        self._pr_to_post = self.selected_pr

        # Exit TUI first - this stops the Textual event loop
        self.exit()


def launch_interactive_tui(prs_with_priority: List[PRWithPriority]):
    """
    Launch the interactive TUI application.

    This function handles the complete TUI lifecycle including:
    - Running the TUI
    - Posting comments when 'p' is pressed
    - Relaunching the TUI after posting
    - Exiting when 'q' is pressed
    """
    while True:
        app = PRReviewApp(prs_with_priority)
        app.run()

        # Check if user pressed 'p' to post a comment
        if hasattr(app, '_pr_to_post') and app._pr_to_post:
            # Store the PR to post
            pr_to_post = app._pr_to_post

            # Post the comment using terminal UI
            # We need to temporarily create an app-like context for the method
            temp_app = PRReviewApp(prs_with_priority)
            temp_app.selected_pr = pr_to_post
            temp_app._post_comment_terminal()

            # Loop continues - relaunch TUI with same PR list
        else:
            # User pressed 'q' to quit
            break

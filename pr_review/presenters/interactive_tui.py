from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static
from textual.containers import Horizontal, Vertical
from rich.text import Text
import webbrowser
from typing import List, Optional

from ..models import PRWithPriority
from ..priority_scorer import PriorityScorer


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
    ]

    def __init__(self, prs_with_priority: List[PRWithPriority]):
        super().__init__()
        self.prs_with_priority = prs_with_priority
        self.selected_pr: Optional[PRWithPriority] = None

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


def launch_interactive_tui(prs_with_priority: List[PRWithPriority]):
    """Launch the interactive TUI application"""
    app = PRReviewApp(prs_with_priority)
    app.run()

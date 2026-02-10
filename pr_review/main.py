import asyncio
import typer
from rich.console import Console
from pathlib import Path

from .config import Config
from .bitbucket_client import BitbucketClient
from .claude_analyzer import ClaudeAnalyzer
from .defense_council import DefenseCouncilAnalyzer
from .priority_scorer import PriorityScorer
from .models import PRAnalysis
from .presenters.interactive_tui import launch_interactive_tui
from .presenters.report_generator import (
    generate_terminal_report,
    generate_markdown_report,
    generate_json_report
)

app = typer.Typer()
console = Console()


@app.command()
def review(
    workspace: str = typer.Argument(None, help="Bitbucket workspace (default: from PR_REVIEWER_BITBUCKET_WORKSPACE env var)"),
    repo: str = typer.Argument(None, help="Repository name (optional - if not specified, searches all repos in workspace)"),
    pr_url: str = typer.Option(None, "--pr-url", help="Bitbucket PR URL to analyze (e.g., https://bitbucket.org/workspace/repo/pull-requests/123)"),
    skip_analyze: bool = typer.Option(False, "--skip-analyze", help="Skip AI analysis and show PR summary only"),
    pr_defense: bool = typer.Option(False, "--pr-defense", help="Use PR Defense Council mode (multi-agent deep review)"),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-I"),
    export: str = typer.Option(None, "--export", "-e", help="Export format: markdown/json"),
    output: str = typer.Option("pr_report", "--output", "-o", help="Output file path"),
    max_prs: int = typer.Option(30, "--max-prs", "-m", help="Max PRs to analyze"),
    post: bool = typer.Option(False, "--post", help="Automatically post comments after analysis (non-interactive mode only)"),
    max_inline_comments: int = typer.Option(20, "--max-inline-comments", help="Maximum inline comments per PR (default: 20)"),
    inline_severity: str = typer.Option("critical,high", "--inline-severity", help="Minimum severity for inline: critical,high,medium,low"),
    local_diff: bool = typer.Option(
        False,
        "--local-diff/--api-diff",
        help="Use local git cloning instead of API for diffs"
    ),
    git_cache_cleanup: bool = typer.Option(
        False,
        "--cleanup-git-cache",
        help="Clean stale git repositories before running"
    ),
    use_https: bool = typer.Option(
        False,
        "--use-https",
        help="Use HTTPS instead of SSH for git operations"
    ),
):
    """
    Fetch and analyze PRs assigned to you as a reviewer from Bitbucket with AI assistance.

    If WORKSPACE is not provided, uses PR_REVIEWER_BITBUCKET_WORKSPACE from .env file.
    If REPO is not specified, searches across ALL repositories in the workspace.

    With --pr-url, analyze a single PR from its Bitbucket URL (automatically non-interactive).
    With --skip-analyze, skip AI analysis and show PR summary only (faster, no API costs).
    With --pr-defense, use PR Defense Council mode: multiple specialized reviewers analyze each PR in parallel for deeper review.
    With --post, automatically post comments after analysis (non-interactive mode only).
    With --max-inline-comments, limit the number of inline comments per PR.
    With --inline-severity, set minimum severity level for inline comments.
    With --local-diff, clone repositories and generate diffs locally (bypasses API rate limits).
    With --cleanup-git-cache, clean stale cached repositories before running (requires --local-diff).
    With --use-https, use HTTPS instead of SSH for git operations (requires --local-diff).
    """

    # ========== SINGLE PR URL ANALYSIS ==========
    # Parse URL and auto-disable interactive mode if --pr-url is provided
    url_workspace = url_repo = url_pr_id = None
    if pr_url:
        # Automatically disable interactive mode for single PR analysis
        if interactive:
            interactive = False
            console.print("[dim]ℹ️  Single PR URL mode: automatically using non-interactive output[/dim]\n")

        # Parse the Bitbucket PR URL
        # Expected format: https://bitbucket.org/{workspace}/{repo}/pull-requests/{pr_id}
        import re
        url_pattern = r'https://bitbucket\.org/([^/]+)/([^/]+)/pull-requests/(\d+)'
        match = re.match(url_pattern, pr_url)

        if not match:
            console.print(f"\n[red]❌ Error:[/red] Invalid Bitbucket PR URL format: {pr_url}")
            console.print("\nExpected format: [cyan]https://bitbucket.org/workspace/repo/pull-requests/123[/cyan]\n")
            raise typer.Exit(1)

        url_workspace, url_repo, url_pr_id = match.groups()

        console.print(f"\n[cyan]📋 Single PR Analysis Mode[/cyan]")
        console.print(f"[dim]Workspace:[/dim] {url_workspace}")
        console.print(f"[dim]Repository:[/dim] {url_repo}")
        console.print(f"[dim]PR ID:[/dim] {url_pr_id}")
        console.print(f"[dim]URL:[/dim] {pr_url}\n")

    async def _review():
        # 0. Validate configuration
        try:
            config = Config()

            # Check for required credentials
            if not config.has_valid_credentials:
                config._print_credentials_warning()
                raise typer.Exit(1)

            # Resolve workspace: use config default if not provided as argument
            target_workspace = workspace
            if target_workspace is None:
                target_workspace = config.bitbucket_workspace
                if not target_workspace:
                    env_file = config.config_dir / ".env"
                    console.print("\n[red]❌ Error:[/red] Workspace not specified.")
                    console.print(f"\nAdd to your config file ({env_file}):")
                    console.print(f"  [cyan]PR_REVIEWER_BITBUCKET_WORKSPACE=[/cyan][dim]your_workspace_name[/dim]\n")
                    console.print("Or provide workspace as argument:")
                    console.print("  [cyan]pr-review review <workspace>[/cyan]\n")
                    raise typer.Exit(1)
                else:
                    console.print(f"[dim]Using workspace from config: {target_workspace}[/dim]\n")

            # Show config info for transparency
            env_file = config.config_dir / ".env"
            console.print(f"[dim]💾 Config: {env_file}[/dim]")
            console.print(f"[dim]🔑 Auth: {config.bitbucket_email}[/dim]\n")

        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

        # 1. Initialize Bitbucket client and auto-detect current user
        console.print("[cyan]📡 Connecting to Bitbucket...[/cyan]")
        async with BitbucketClient(
            email=config.bitbucket_email,
            api_token=config.bitbucket_api_token,
            base_url=config.bitbucket_base_url
        ) as client:
                current_user = None

                # Initialize local git manager if local diff mode is enabled
                git_manager = None
                if local_diff:
                    from .git_diff_manager import LocalGitDiffManager
                    from .utils.git_operations import GitOperations

                    # Verify git is available
                    if not GitOperations.verify_git_available():
                        console.print("\n[red]❌ Error:[/red] git is not installed or not accessible.")
                        console.print("\nPlease install git to use --local-diff mode:")
                        console.print("  [cyan]https://git-scm.com/downloads[/cyan]\n")
                        raise typer.Exit(1)

                    git_manager = LocalGitDiffManager(
                        cache_dir=config.cache_dir,
                        console=console,
                        use_ssh=not use_https,
                        max_age_days=config.git_cache_max_age_days,
                        max_size_gb=config.git_cache_max_size_gb,
                        timeout_seconds=config.git_timeout_seconds
                    )

                    if git_cache_cleanup:
                        with console.status("[cyan]Cleaning git cache...[/cyan]"):
                            await git_manager.cleanup_stale_repos()
                        console.print("[green]✓[/green] Git cache cleaned\n")

                    if use_https:
                        console.print("[dim]ℹ️  Using HTTPS for git operations[/dim]\n")

                # Try to get user info from /user endpoint (may fail with some API tokens)
                # First, check if we have UUID from config (preferred)
                user_uuid = config.bitbucket_user_uuid

                if user_uuid:
                    console.print(f"[green]✓[/green] Using UUID from config: [bold]{user_uuid[:8]}...[/bold]")
                else:
                    # No UUID in config - try to get from /user endpoint
                    try:
                        current_user = await client.get_current_user()
                        console.print(f"[green]✓[/green] Authenticated as [bold]{current_user.display_name}[/bold] ({current_user.username})")
                        user_uuid = current_user.uuid
                        # Note: UUID could be saved to config for faster startup, but auto-detection works fine
                    except RuntimeError as e:
                        if "user_endpoint_not_accessible" in str(e):
                            console.print("\n[red]❌ Error:[/red] Cannot determine your identity.")
                            console.print("Your API Token doesn't have the [cyan]Account: Read[/cyan] permission.")
                            console.print("\nPlease update your API Token with these permissions:")
                            console.print("  [cyan]Pull requests: Read, Repositories: Read, Account: Read[/cyan]\n")
                            raise typer.Exit(1)
                        elif "token_invalid_or_expired" in str(e):
                            error_msg = str(e).split(":", 1)[1] if ":" in str(e) else "Authentication failed"
                            console.print("\n[red]❌ Authentication Error:[/red]")
                            console.print(f"[dim]{error_msg}[/dim]")
                            console.print("\nPlease check your API Token credentials in:")
                            console.print(f"  [cyan]~/.pr-review-cli/.env[/cyan]\n")
                            raise typer.Exit(1)
                        else:
                            raise

                # No username fallback anymore - UUID is required
                user_username = None

                # ========== FETCH PRs (Single PR or Multi-PR) ==========
                if pr_url:
                    # Single PR mode: fetch the specific PR from URL
                    with console.status(f"[cyan]Fetching PR #{url_pr_id}...[/cyan]"):
                        pr = await client.get_single_pr(url_workspace, url_repo, url_pr_id)
                        console.print(f"[green]✓[/green] Found PR: [bold]{pr.title}[/bold]")

                    # Fetch diff based on mode
                    if local_diff:
                        with console.status(f"[cyan]Generating local diff...[/cyan]"):
                            diff = await git_manager.get_pr_diff_local(
                                workspace=url_workspace,
                                repo_slug=url_repo,
                                pr_id=url_pr_id,
                                source_branch=pr.source_branch,
                                destination_branch=pr.destination_branch
                            )
                            console.print(f"[green]✓[/green] Diff loaded ([cyan]{diff.additions + diff.deletions:,}[/cyan] lines changed)")
                    else:
                        with console.status(f"[cyan]Retrieving diff...[/cyan]"):
                            diff = await client.get_pr_diff(url_workspace, url_repo, url_pr_id)
                            console.print(f"[green]✓[/green] Diff loaded ([cyan]{diff.additions + diff.deletions:,}[/cyan] lines changed)")

                    prs = [pr]
                    diffs = [diff]
                else:
                    # Multi-PR mode: fetch all PRs assigned to user
                    if repo:
                        search_scope = f"[cyan]{target_workspace}/{repo}[/cyan]"
                    else:
                        search_scope = f"[cyan]all repositories in {target_workspace}[/cyan]"

                    # Fetch PRs (API mode always needed for PR metadata)
                    with console.status(f"[cyan]Fetching PRs assigned to you for review in {search_scope}...[/cyan]"):
                        prs = await client.fetch_prs_assigned_to_me(target_workspace, repo, user_uuid, user_username)

                    if not prs:
                        console.print("[yellow]No PRs assigned to you for review. You're all caught up! 🎉[/yellow]")
                        return  # Exit gracefully without error

                    repo_text = f" in {target_workspace}/{repo}" if repo else f" across all repositories in {target_workspace}"
                    console.print(f"[green]✓[/green] Found [bold]{len(prs)}[/bold] PR(s) requiring your review{repo_text}")

                    # Limit PRs if specified
                    prs = prs[:max_prs]
                    if len(prs) < max_prs:
                        console.print(f"[dim]Processing {len(prs)} PRs (limited from {max_prs})[/dim]")

                    # Fetch diffs based on mode
                    if local_diff:
                        # Local git mode - generate diffs from cloned repos
                        diffs = []
                        for pr in prs:
                            with console.status(f"[cyan]Generating local diff for PR {pr.id}...[/cyan]"):
                                diff = await git_manager.get_pr_diff_local(
                                    workspace=pr.workspace,
                                    repo_slug=pr.repo_slug,
                                    pr_id=pr.id,
                                    source_branch=pr.source_branch,
                                    destination_branch=pr.destination_branch
                                )
                                diffs.append(diff)
                                console.print(f"[green]✓[/green] PR {pr.id}: [cyan]{diff.additions + diff.deletions:,}[/cyan] lines changed")
                    else:
                        # API mode - fetch diffs via API
                        with console.status(f"[cyan]Fetching diffs for {len(prs)} PR(s)...[/cyan]"):
                            # Fetch diffs in parallel
                            import asyncio
                            tasks = [
                                client.get_pr_diff(pr.workspace, pr.repo_slug, pr.id)
                                for pr in prs
                            ]
                            diffs = await asyncio.gather(*tasks)

                        total_lines = sum(d.additions + d.deletions for d in diffs)
                        console.print(f"[green]✓[/green] Loaded [cyan]{total_lines:,}[/cyan] lines changed across [cyan]{len(diffs)}[/cyan] PR(s)")

                # 3. Analyze with Claude (parallel processing) - or skip if requested
                if skip_analyze:
                    console.print("[dim]⏭️  Skipping AI analysis (--skip-analyze flag)[/dim]")
                    # Create placeholder PRAnalysis objects
                    analyses = [
                        PRAnalysis(
                            pr_id=pr.id,
                            good_points=[],
                            attention_required=["AI analysis skipped"],
                            risk_factors=[],
                            overall_quality_score=50,  # Neutral score
                            estimated_review_time="N/A",
                            _skipped_reason="user_requested"
                        )
                        for pr in prs
                    ]
                elif pr_defense:
                    # PR Defense Council mode: multi-agent deep review
                    analyzer = DefenseCouncilAnalyzer()
                    diff_contents = [diff.diff_content for diff in diffs]

                    total_prs = len(prs)
                    console.print(f"[cyan]⚔️  PR Defense Council: Analyzing {total_prs} PR(s) with 3 personas each...[/cyan]\n")

                    # Defense Council processes PRs sequentially (each uses parallel agents)
                    # Create progress tracking
                    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console,
                        transient=True
                    ) as progress:
                        task = progress.add_task("[cyan]Council review progress[/cyan]", total=total_prs)

                        def update_progress(current, total, title):
                            progress.update(task, advance=1, description=f"[cyan]Reviewing: {title[:30]}[/cyan]")

                        analyses = await analyzer.analyze_prs(prs, diff_contents, progress_callback=update_progress)
                else:
                    # Standard mode: parallel PR processing with single agent
                    analyzer = ClaudeAnalyzer()
                    diff_contents = [diff.diff_content for diff in diffs]

                    total_prs = len(prs)
                    console.print(f"[cyan]🤖 Analyzing {total_prs} PR(s) with AI (3 in parallel)...[/cyan]\n")

                    # For local diffs, analyze all PRs regardless of size
                    # For API diffs, skip large PRs (>50K chars)
                    skip_large = not local_diff

                    # Create progress tracking
                    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console,
                        transient=True
                    ) as progress:
                        task = progress.add_task("[cyan]AI analysis progress[/cyan]", total=total_prs)

                        def update_progress(current, total, title):
                            progress.update(task, advance=1, description=f"[cyan]Analyzing: {title[:30]}[/cyan]")

                        analyses = await analyzer.analyze_prs_parallel(
                            prs,
                            diff_contents,
                            progress_callback=update_progress,
                            skip_large=skip_large
                        )

                # 4. Calculate priority scores
                with console.status("[cyan]Calculating priorities...[/cyan]"):
                    scorer = PriorityScorer(config.cache_dir)
                    prs_with_priority = scorer.score_prs(prs, analyses, diffs)

                # 5. Auto-post comments if requested (non-interactive mode only)
                if post and not interactive:
                    # Parse inline severity filter
                    severity_levels = ["critical", "high", "medium", "low"]
                    requested_severities = [s.strip().lower() for s in inline_severity.split(",")]
                    min_severity_index = min(
                        [severity_levels.index(s) for s in requested_severities if s in severity_levels],
                        default=1  # Default to "high"
                    )
                    allowed_severities = set(severity_levels[min_severity_index:])

                    console.print("\n[cyan]📝 Posting Comments[/cyan]\n")

                    for pr_with_priority in prs_with_priority:
                        pr = pr_with_priority.pr
                        analysis = pr_with_priority.analysis

                        # Post summary comment
                        from .presenters.report_generator import generate_markdown_for_pr
                        summary = generate_markdown_for_pr(pr_with_priority)

                        try:
                            await client.post_pr_comment(
                                workspace=pr.workspace,
                                repo_slug=pr.repo_slug,
                                pr_id=pr.id,
                                content=summary
                            )
                            console.print(f"[green]✓[/green] Posted summary comment to PR [cyan]{pr.id}[/cyan]: [bold]{pr.title[:40]}...[/bold]")
                        except RuntimeError as e:
                            console.print(f"[red]✗[/red] Failed to post summary to PR {pr.id}: {str(e)[:60]}")
                            continue  # Skip inline comments if summary fails

                        # Post inline comments (filtered by severity and max count)
                        inline_comments = [
                            c for c in analysis.line_comments
                            if c.severity in allowed_severities
                        ][:max_inline_comments]

                        if inline_comments:
                            try:
                                results = await client.post_inline_comments_batch(
                                    workspace=pr.workspace,
                                    repo_slug=pr.repo_slug,
                                    pr_id=pr.id,
                                    comments=inline_comments,
                                    delay_between=0.5
                                )

                                successful = sum(1 for r in results if r.get("success"))
                                failed = len(results) - successful

                                if successful > 0:
                                    console.print(f"  [green]✓[/green] Posted [cyan]{successful}[/cyan] inline comment(s)")
                                if failed > 0:
                                    console.print(f"  [yellow]⚠[/yellow] [cyan]{failed}[/cyan] inline comment(s) failed")

                            except RuntimeError as e:
                                console.print(f"  [yellow]⚠[/yellow] Inline comments failed: {str(e)[:60]}")
                        else:
                            console.print("  [dim]No inline comments to post[/dim]")

                    console.print()

                # 6. Present results
                if interactive:
                    # For TUI, we need to exit the async context first
                    # Pass client for comment posting functionality
                    return prs_with_priority, client
                else:
                    generate_terminal_report(prs_with_priority)

                # 7. Export if requested
                if export:
                    if export == "markdown":
                        output_path = f"{output}.md"
                        generate_markdown_report(prs_with_priority, output_path)
                        console.print(f"[green]✓[/green] Report exported to [cyan]{output_path}[/cyan]")
                    elif export == "json":
                        output_path = f"{output}.json"
                        generate_json_report(prs_with_priority, output_path)
                        console.print(f"[green]✓[/green] Report exported to [cyan]{output_path}[/cyan]")
                    else:
                        console.print(f"[red]Unknown export format: {export}[/red]")

        return None

    # Run the async function
    try:
        result = asyncio.run(_review())

        # If TUI mode, launch it outside the asyncio context
        if result and interactive:
            # Handle both tuple (with client) and list (legacy) return types
            if isinstance(result, tuple):
                prs_with_priority, client = result
                launch_interactive_tui(prs_with_priority, client)
            else:
                launch_interactive_tui(result)

    except RuntimeError as e:
        console.print(f"\n[red]{str(e)}[/red]\n")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(0)


@app.command()
def cache_stats():
    """Show cached author statistics"""
    config = Config()
    cache_dir = config.cache_dir
    author_cache_file = cache_dir / "author_history.json"

    console.print(f"\n[cyan]Cache Directory:[/cyan] {cache_dir}\n")

    if author_cache_file.exists():
        import json
        with open(author_cache_file, 'r') as f:
            author_history = json.load(f)

        console.print(f"[bold]Author PR History:[/bold]\n")
        sorted_authors = sorted(author_history.items(), key=lambda x: x[1], reverse=True)
        for author, count in sorted_authors[:20]:
            console.print(f"  • {author}: {count} PRs")

        if len(sorted_authors) > 20:
            console.print(f"\n  [dim]... and {len(sorted_authors) - 20} more authors[/dim]")
    else:
        console.print("[yellow]No author history cached yet[/yellow]")


if __name__ == "__main__":
    app()

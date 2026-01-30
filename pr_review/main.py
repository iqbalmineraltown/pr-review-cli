import asyncio
import typer
from rich.console import Console
from pathlib import Path

from .config import Config
from .bitbucket_client import BitbucketClient
from .claude_analyzer import ClaudeAnalyzer
from .priority_scorer import PriorityScorer
from .prompt_loader import PromptLoader
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
    workspace: str = typer.Argument("", help="Bitbucket workspace (default: from PR_REVIEWER_BITBUCKET_WORKSPACE env var)"),
    repo: str = typer.Argument("", help="Repository name (optional - if not specified, searches all repos in workspace)"),
    pr_url: str = typer.Option("", "--pr-url", help="Bitbucket PR URL to analyze (e.g., https://bitbucket.org/workspace/repo/pull-requests/123)"),
    prompt: str = typer.Option("default", "--prompt", "-p", help="Custom prompt to use"),
    skip_analyze: bool = typer.Option(False, "--skip-analyze", help="Skip AI analysis and show PR summary only"),
    no_interactive: bool = typer.Option(False, "--no-interactive", help="Disable interactive mode"),
    export: str = typer.Option("", "--export", "-e", help="Export format: markdown/json"),
    output: str = typer.Option("pr_report", "--output", "-o", help="Output file path"),
    max_prs: int = typer.Option(30, "--max-prs", "-m", help="Max PRs to analyze"),
    local_diff: bool = typer.Option(False, "--local-diff", help="Use local git cloning instead of API for diffs"),
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
    With --local-diff, clone repositories and generate diffs locally (bypasses API rate limits).
    With --cleanup-git-cache, clean stale cached repositories before running (requires --local-diff).
    With --use-https, use HTTPS instead of SSH for git operations (requires --local-diff).
    """

    # Convert no_interactive flag to interactive for internal use
    interactive = not no_interactive

    # ========== SINGLE PR URL ANALYSIS ==========
    # Parse URL and auto-disable interactive mode if --pr-url is provided
    url_workspace = url_repo = url_pr_id = None
    if pr_url and pr_url.strip():
        # Automatically disable interactive mode for single PR analysis
        interactive = not no_interactive
        if interactive:
            no_interactive = True
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
            if not target_workspace or not target_workspace.strip():
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

        # Initialize prompt loader (creates directories if needed)
        prompt_loader = PromptLoader(config.config_dir)

        # Show prompt notification
        console.print("\n[dim]💡 Custom prompts available in:[/dim]")
        console.print(f"   [dim]{prompt_loader.prompts_dir}[/dim]")
        console.print(f"   [dim]Drop .md files there to create custom analysis prompts![/dim]\n")

        # Verify requested prompt exists
        available_prompts = prompt_loader.list_prompts()
        if prompt not in available_prompts:
            console.print(f"[red]Error:[/red] Prompt '{prompt}' not found!")
            console.print(f"\n[cyan]Available prompts:[/cyan]")
            for p in available_prompts:
                console.print(f"  • {p}")
            raise typer.Exit(1)

        # Load the custom prompt
        prompt_template = prompt_loader.load_prompt(prompt)

        # 1. Initialize Bitbucket client and auto-detect current user
        with console.status("[cyan]Connecting to Bitbucket...[/cyan]"):
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
                else:
                    analyzer = ClaudeAnalyzer(prompt_template=prompt_template)
                    # Extract diff content from PRDiff objects
                    diff_contents = [diff.diff_content for diff in diffs]

                    # Create progress tracking
                    total_prs = len(prs)
                    status = console.status("[cyan]Initializing analysis...[/cyan]")
                    status.start()

                    def update_progress(current, total, title):
                        truncated_title = title[:40] + "..." if len(title) > 40 else title
                        status.update(f"[cyan]Analyzing PR {current}/{total}:[/cyan] {truncated_title}")

                    try:
                        analyses = await analyzer.analyze_prs_parallel(
                            prs,
                            diff_contents,
                            progress_callback=update_progress
                        )
                    finally:
                        status.stop()

                # 4. Calculate priority scores
                with console.status("[cyan]Calculating priorities...[/cyan]"):
                    scorer = PriorityScorer(config.cache_dir)
                    prs_with_priority = scorer.score_prs(prs, analyses, diffs)

                # 5. Present results
                interactive = not no_interactive
                if interactive:
                    # For TUI, we need to exit the async context first
                    return prs_with_priority
                else:
                    generate_terminal_report(prs_with_priority)

                # 6. Export if requested
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
        if result and isinstance(result, list) and interactive:
            launch_interactive_tui(result)

    except RuntimeError as e:
        console.print(f"\n[red]{str(e)}[/red]\n")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(0)


@app.command()
def prompts(
    list_only: bool = typer.Option(False, "--list", "-l", help="List available prompts"),
):
    """Manage custom analysis prompts"""
    prompt_loader = PromptLoader()

    console.print(f"\n[cyan]Prompt Directory:[/cyan] {prompt_loader.prompts_dir}\n")

    available_prompts = prompt_loader.list_prompts()

    if list_only:
        console.print("[bold]Available Prompts:[/bold]\n")
        for prompt_name in available_prompts:
            metadata = prompt_loader.get_prompt_metadata(prompt_name)
            description = metadata.get("description", "No description")
            tags = metadata.get("tags", [])

            console.print(f"  • [bold]{prompt_name}[/bold]")
            if description:
                console.print(f"    {description}")
            if tags:
                console.print(f"    [dim]Tags: {', '.join(tags)}[/dim]")
            console.print()
    else:
        console.print("[bold]Available Prompts:[/bold]\n")
        for prompt_name in available_prompts:
            console.print(f"  • {prompt_name}")

        console.print("\n[bold]Usage:[/bold]")
        console.print("  pr-review review <workspace> <repo> --prompt <name>")
        console.print("\n[bold]To create a custom prompt:[/bold]")
        console.print(f"  1. Create a .md file in: {prompt_loader.prompts_dir}")
        console.print("  2. Use placeholders: {title}, {author}, {source}, {destination}, {diff}")
        console.print("  3. Response must be valid JSON format")


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


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
):
    """
    Start the web interface server.

    Launches a FastAPI server with REST API and WebSocket support.
    Access the web interface at http://localhost:8000

    Examples:
        pr-review serve                    # Start with default settings (127.0.0.1:8000)
        pr-review serve --port 3000        # Use custom port
        pr-review serve --host 0.0.0.0     # Listen on all interfaces
    """
    import asyncio

    config = Config()
    if not config.has_valid_credentials:
        config._print_credentials_warning()
        raise typer.Exit(1)

    # Allow env vars to override defaults
    server_host = host if host != "127.0.0.1" else config.web_host
    server_port = port if port != 8000 else config.web_port

    console.print(f"\n[cyan]🚀 Starting PR Review Web Server[/cyan]")
    console.print(f"[dim]Server will run at:[/dim] http://{server_host}:{server_port}")
    console.print(f"[dim]API documentation:[/dim] http://{server_host}:{server_port}/api/docs")
    console.print(f"[dim]WebSocket endpoint:[/dim] ws://{server_host}:{server_port}/ws/analyze\n")

    try:
        from .web.server import start_server
        asyncio.run(start_server(host=server_host, port=server_port))
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
        raise typer.Exit(0)


if __name__ == "__main__":
    app()

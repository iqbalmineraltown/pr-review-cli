"""
REST API Routes for PR Review Web Interface

This module provides REST endpoints for:
- Listing and fetching PRs
- Triggering analysis
- Getting configuration
- Managing prompts
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional
from pydantic import BaseModel
import asyncio

from ...config import Config
from ...bitbucket_client import BitbucketClient
from ...claude_analyzer import ClaudeAnalyzer
from ...priority_scorer import PriorityScorer
from ...prompt_loader import PromptLoader
from ...models import BitbucketPR, PRWithPriority, PRDiff
from .websocket import broadcast_message, analysis_results_store


# Request/Response models
class AnalyzeRequest(BaseModel):
    workspace: str
    repo_slug: Optional[str] = None
    prompt: str = "default"
    max_prs: int = 30


class PRListResponse(BaseModel):
    prs: List[dict]
    count: int


class PRDetailResponse(BaseModel):
    pr: dict
    diff: dict


class ConfigResponse(BaseModel):
    workspace: Optional[str]
    prompts: List[dict]


router = APIRouter()


async def run_analysis_background(
    workspace: str,
    repo_slug: Optional[str],
    prompt: str,
    max_prs: int,
    analysis_id: str
):
    """
    Background task to run PR analysis and broadcast progress via WebSocket.

    This function:
    1. Fetches PRs from Bitbucket
    2. Fetches diffs
    3. Analyzes with Claude
    4. Scores PRs
    5. Broadcasts progress and results via WebSocket
    """
    config = Config()

    try:
        # Initialize components
        prompt_loader = PromptLoader(config.config_dir)
        prompt_template = prompt_loader.load_prompt(prompt)

        async with BitbucketClient(
            email=config.bitbucket_email,
            api_token=config.bitbucket_api_token,
            base_url=config.bitbucket_base_url
        ) as client:
            # Get user UUID
            user_uuid = config.bitbucket_user_uuid
            if not user_uuid:
                try:
                    current_user = await client.get_current_user()
                    user_uuid = current_user.uuid
                except RuntimeError:
                    # Fallback: workspace-wide search without UUID
                    pass

            # Broadcast: Fetching PRs
            await broadcast_message({
                "type": "progress",
                "analysis_id": analysis_id,
                "current": 0,
                "total": 100,
                "status": "Fetching PRs from Bitbucket..."
            })

            # Fetch PRs
            prs = await client.fetch_prs_assigned_to_me(
                workspace, repo_slug, user_uuid, None
            )

            if not prs:
                await broadcast_message({
                    "type": "complete",
                    "analysis_id": analysis_id,
                    "results": []
                })
                return

            # Limit PRs
            prs = prs[:max_prs]

            # Broadcast: Fetching diffs
            await broadcast_message({
                "type": "progress",
                "analysis_id": analysis_id,
                "current": 10,
                "total": 100,
                "status": f"Fetching diffs for {len(prs)} PR(s)..."
            })

            # Fetch diffs in parallel
            tasks = [
                client.get_pr_diff(pr.workspace, pr.repo_slug, pr.id)
                for pr in prs
            ]
            diffs = await asyncio.gather(*tasks)

            # Broadcast: Analyzing with Claude
            await broadcast_message({
                "type": "progress",
                "analysis_id": analysis_id,
                "current": 30,
                "total": 100,
                "status": "Analyzing PRs with Claude AI..."
            })

            # Analyze with Claude (parallel processing)
            analyzer = ClaudeAnalyzer(prompt_template=prompt_template)
            diff_contents = [diff.diff_content for diff in diffs]

            analyses = await analyzer.analyze_prs_parallel(
                prs,
                diff_contents,
                progress_callback=lambda current, total, title: asyncio.create_task(
                    broadcast_message({
                        "type": "progress",
                        "analysis_id": analysis_id,
                        "current": 30 + int((current / total) * 50),
                        "total": 100,
                        "status": f"Analyzing {current}/{total}: {title[:40]}..."
                    })
                )
            )

            # Broadcast: Calculating priorities
            await broadcast_message({
                "type": "progress",
                "analysis_id": analysis_id,
                "current": 90,
                "total": 100,
                "status": "Calculating priority scores..."
            })

            # Score PRs
            scorer = PriorityScorer(config.cache_dir)
            prs_with_priority = scorer.score_prs(prs, analyses, diffs)

            # Convert to JSON-serializable format
            results = [
                {
                    "pr": pr_with_priority.pr.model_dump(mode="json"),
                    "analysis": pr_with_priority.analysis.model_dump(mode="json"),
                    "priority_score": pr_with_priority.priority_score,
                    "risk_level": PriorityScorer.get_risk_level(pr_with_priority.priority_score)
                }
                for pr_with_priority in prs_with_priority
            ]

            # Store results for later retrieval
            analysis_results_store[analysis_id] = results

            # Broadcast: Complete
            await broadcast_message({
                "type": "complete",
                "analysis_id": analysis_id,
                "results": results
            })

    except Exception as e:
        # Broadcast error
        await broadcast_message({
            "type": "error",
            "analysis_id": analysis_id,
            "error": str(e)
        })


@router.get("/prs", response_model=PRListResponse)
async def list_prs(
    workspace: str = Query(..., description="Bitbucket workspace name"),
    repo: Optional[str] = Query(None, description="Repository name (optional)"),
) -> PRListResponse:
    """
    List PRs assigned to the current user for review.

    Args:
        workspace: Bitbucket workspace name
        repo: Repository slug (optional - if not specified, searches all repos)

    Returns:
        List of PRs with metadata
    """
    config = Config()

    if not config.has_valid_credentials:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Broadcast: Starting PR fetch
    await broadcast_message({
        "type": "progress",
        "current": 0,
        "total": 100,
        "status": f"Starting PR fetch from {workspace}..."
    })

    async with BitbucketClient(
        email=config.bitbucket_email,
        api_token=config.bitbucket_api_token,
        base_url=config.bitbucket_base_url
    ) as client:
        # Get user UUID
        await broadcast_message({
            "type": "progress",
            "current": 10,
            "total": 100,
            "status": "Authenticating with Bitbucket..."
        })

        user_uuid = config.bitbucket_user_uuid
        if not user_uuid:
            try:
                current_user = await client.get_current_user()
                user_uuid = current_user.uuid
            except RuntimeError:
                pass

        # Broadcast: Fetching PRs
        await broadcast_message({
            "type": "progress",
            "current": 30,
            "total": 100,
            "status": f"Fetching PRs from {repo + '/' if repo else ''}{workspace}..."
        })

        # Define progress callback to broadcast updates
        async def progress_callback(status_message: str):
            await broadcast_message({
                "type": "progress",
                "current": 40,  # Keep at 40% during fetching
                "total": 100,
                "status": status_message
            })

        # Fetch PRs with progress callback
        prs = await client.fetch_prs_assigned_to_me(
            workspace, repo, user_uuid, None, progress_callback=progress_callback
        )

        # Broadcast: Complete
        await broadcast_message({
            "type": "progress",
            "current": 100,
            "total": 100,
            "status": f"Found {len(prs)} PR(s)"
        })

        return PRListResponse(
            prs=[pr.model_dump(mode="json") for pr in prs],
            count=len(prs)
        )


@router.get("/prs/{pr_id}", response_model=PRDetailResponse)
async def get_pr_detail(
    pr_id: str,
    workspace: str = Query(..., description="Bitbucket workspace name"),
    repo: str = Query(..., description="Repository name")
) -> PRDetailResponse:
    """
    Get detailed information about a specific PR including diff.

    Args:
        pr_id: Pull request ID
        workspace: Bitbucket workspace name
        repo: Repository name

    Returns:
        PR details with diff
    """
    config = Config()

    if not config.has_valid_credentials:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    async with BitbucketClient(
        email=config.bitbucket_email,
        api_token=config.bitbucket_api_token,
        base_url=config.bitbucket_base_url
    ) as client:
        # Get PR and diff
        pr = await client.get_single_pr(workspace, repo, pr_id)
        diff = await client.get_pr_diff(workspace, repo, pr_id)

        return PRDetailResponse(
            pr=pr.model_dump(mode="json"),
            diff=diff.model_dump(mode="json")
        )


@router.post("/analyze")
async def analyze_prs(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Trigger analysis of PRs with Claude AI.

    This endpoint starts a background task that:
    1. Fetches PRs from Bitbucket
    2. Fetches diffs
    3. Analyzes with Claude
    4. Scores PRs
    5. Streams progress via WebSocket

    Args:
        request: Analysis request with workspace, repo_slug, prompt, and max_prs

    Returns:
        Analysis ID to subscribe to via WebSocket
    """
    config = Config()

    if not config.has_valid_credentials:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate unique analysis ID
    import uuid
    analysis_id = str(uuid.uuid4())

    # Start background analysis
    background_tasks.add_task(
        run_analysis_background,
        request.workspace,
        request.repo_slug,
        request.prompt,
        request.max_prs,
        analysis_id
    )

    return {
        "analysis_id": analysis_id,
        "message": "Analysis started. Subscribe to WebSocket for progress updates.",
        "websocket_url": f"/ws/analyze"
    }


@router.get("/analyze/{analysis_id}")
async def get_analysis_results(analysis_id: str) -> dict:
    """
    Get cached analysis results by ID.

    Args:
        analysis_id: Analysis ID from POST /api/analyze

    Returns:
        Cached analysis results or 404 if not found
    """
    if analysis_id not in analysis_results_store:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "analysis_id": analysis_id,
        "results": analysis_results_store[analysis_id]
    }


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """
    Get configuration information.

    Returns:
        Configuration with workspace and available prompts
    """
    config = Config()

    prompt_loader = PromptLoader(config.config_dir)
    prompts_info = prompt_loader.get_all_prompts_info()

    return ConfigResponse(
        workspace=config.bitbucket_workspace,
        prompts=prompts_info
    )


@router.get("/prompts")
async def list_prompts() -> dict:
    """
    List all available custom prompts.

    Returns:
        List of available prompts
    """
    config = Config()
    prompt_loader = PromptLoader(config.config_dir)

    return {
        "prompts": prompt_loader.list_prompts(),
        "prompts_info": prompt_loader.get_all_prompts_info()
    }

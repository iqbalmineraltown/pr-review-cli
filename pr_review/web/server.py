"""
FastAPI Web Server for PR Review CLI

This module provides a FastAPI backend with:
- REST API endpoints for PR operations
- WebSocket support for real-time analysis progress
- Static file serving for Vue.js frontend
- CORS middleware for local development
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional
import uvicorn

from .api.routes import router as api_router
from .api.websocket import handler as websocket_handler


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="PR Review CLI Web Interface",
        description="Interactive web interface for PR Review CLI",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Configure CORS for local development
    # Allows requests from Vite dev server (localhost:5174) and production (localhost:8000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5174",  # Vite dev server
            "http://127.0.0.1:5174",
            "http://localhost:5173",  # Legacy Vite dev server port
            "http://127.0.0.1:5173",
            "http://localhost:8000",  # Production server
            "http://127.0.0.1:8000",
            "http://0.0.0.0:8000",    # Alternative access
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Include API routes
    app.include_router(api_router, prefix="/api")

    # Include WebSocket endpoint
    app.add_websocket_route("/ws/analyze", websocket_handler)

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint for monitoring"""
        return {"status": "healthy", "service": "pr-review-web"}

    # Mount static files (Vue.js build output)
    # Check if static files exist (production build)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:
        # If no build exists, return a friendly message
        @app.get("/")
        async def root():
            return {
                "message": "PR Review CLI Web Server",
                "status": "Running but no frontend build found",
                "instructions": "Build the Vue.js frontend with `cd pr-review-web && npm run build`"
            }

    return app


async def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """
    Start the uvicorn server.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload for development
    """
    app = create_app()

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )

    server = uvicorn.Server(config)

    await server.serve()

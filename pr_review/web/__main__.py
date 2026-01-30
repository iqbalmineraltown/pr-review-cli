"""
Main entry point for running the PR Review Web Server

Usage:
    python -m pr_review.web

This will start the FastAPI server on http://127.0.0.1:8000
"""

import asyncio
import sys

from .server import start_server


async def main():
    """Start the web server"""
    await start_server(host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
        sys.exit(0)

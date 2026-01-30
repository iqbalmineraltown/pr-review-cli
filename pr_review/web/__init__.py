"""
PR Review CLI - Web Interface Package

This package provides a FastAPI backend and Vue.js frontend
for interactive PR review through a browser.
"""

from .server import create_app, start_server

__all__ = ["create_app", "start_server"]

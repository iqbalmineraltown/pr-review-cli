"""
API Routes for PR Review Web Interface

This package contains REST API endpoints and WebSocket handlers
for the web interface.
"""

from .routes import router
from .websocket import handler as websocket_handler

__all__ = ["router", "websocket_handler"]

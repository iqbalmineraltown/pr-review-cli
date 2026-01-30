"""
WebSocket Handler for PR Review Web Interface

This module provides real-time progress updates for PR analysis.
Clients connect to /ws/analyze and subscribe to analysis updates.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Set
import json
import asyncio

# In-memory storage for analysis results (for development)
# In production, this would use Redis or a similar solution
analysis_results_store: Dict[str, list] = {}

# Active WebSocket connections
active_connections: Set[WebSocket] = set()


class ConnectionManager:
    """Manage WebSocket connections and broadcasts"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            await websocket.send_json(message)
        except:
            # Connection might be closed
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager instance
manager = ConnectionManager()


async def broadcast_message(message: dict):
    """
    Broadcast a message to all connected WebSocket clients.

    Args:
        message: Message dictionary to broadcast
    """
    await manager.broadcast(message)


async def handler(websocket: WebSocket):
    """
    WebSocket endpoint handler for /ws/analyze

    Clients can send messages to subscribe to specific analysis:
    {"action": "subscribe", "analysis_id": "uuid"}

    The server broadcasts:
    - Progress updates: {"type": "progress", "current": 50, "total": 100, "status": "..."}
    - Completion: {"type": "complete", "results": [...]}
    - Errors: {"type": "error", "error": "..."}
    """
    await manager.connect(websocket)
    active_connections.add(websocket)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle subscribe action
            if message.get("action") == "subscribe":
                analysis_id = message.get("analysis_id")

                # If analysis already has results, send them immediately
                if analysis_id and analysis_id in analysis_results_store:
                    await websocket.send_json({
                        "type": "complete",
                        "analysis_id": analysis_id,
                        "results": analysis_results_store[analysis_id]
                    })
                else:
                    # Acknowledge subscription
                    await websocket.send_json({
                        "type": "subscribed",
                        "analysis_id": analysis_id,
                        "message": "Subscribed to analysis updates"
                    })

            # Handle ping/pong for keep-alive
            elif message.get("action") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        active_connections.discard(websocket)
    except Exception as e:
        # Handle other errors
        manager.disconnect(websocket)
        active_connections.discard(websocket)


__all__ = ["handler", "broadcast_message", "analysis_results_store", "active_connections"]

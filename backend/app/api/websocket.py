"""
WebSocket Connection Manager.

Manages active WebSocket connections for live interview sessions.
This allows us to broadcast events (like 'question_generated') from
the REST API or background tasks back to the connected client.
"""

import json
from typing import Dict, Any
from fastapi import WebSocket

from app.observability.logging import get_logger
from app.schemas.common import WebSocketEvent, WebSocketEventType

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self):
        # Maps session_id to the active WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")
        
        # Send initial confirmation
        await self.send_event(
            session_id, 
            WebSocketEventType.CONNECTION_ESTABLISHED, 
            {"message": "Connected to interview session"}
        )

    def disconnect(self, session_id: str):
        """Remove a disconnected WebSocket."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_event(self, session_id: str, event_type: WebSocketEventType, payload: dict[str, Any]):
        """
        Send a typed event to a specific session's WebSocket.
        If the client is not connected, the message is dropped (stateless).
        """
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            event = WebSocketEvent(
                event_type=event_type,
                session_id=session_id,
                payload=payload
            )
            try:
                # model_dump_json ensures enums and datetimes are serialized safely
                await websocket.send_text(event.model_dump_json())
            except Exception as e:
                logger.error(f"Failed to send WS message to {session_id}: {e}")
                self.disconnect(session_id)

# Global singleton
manager = ConnectionManager()

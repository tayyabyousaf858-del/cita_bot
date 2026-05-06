"""WebSocket routes for real-time admin dashboard updates."""
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set
import structlog

from app.core.security import decode_token
from app.core.redis import get_redis

logger = structlog.get_logger()
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""
    
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        logger.info("WebSocket connected", total=len(self.active))

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        logger.info("WebSocket disconnected", total=len(self.active))

    async def broadcast(self, message: dict):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active.discard(ws)


manager = ConnectionManager()


async def redis_subscriber():
    """Subscribe to Redis channels and broadcast to WebSocket clients."""
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.psubscribe("job:*", "otp:*", "system:*", "jobs:queue")

    async for message in pubsub.listen():
        if message["type"] in ("pmessage", "message"):
            try:
                data = json.loads(message["data"])
                channel = message.get("channel", "")
                await manager.broadcast({
                    "channel": channel,
                    **data,
                })
            except Exception as e:
                logger.error("Redis subscriber error", error=str(e))


@router.websocket("/admin")
async def admin_websocket(
    ws: WebSocket,
    token: str = Query(...),
):
    """Admin WebSocket endpoint — requires valid JWT."""
    payload = decode_token(token)
    if not payload:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(ws)
    try:
        # Send initial connection ack
        await ws.send_json({"type": "connected", "data": {"message": "Connected to CitaMonitor"}})
        
        # Keep connection alive, handle pings
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send heartbeat
                await ws.send_json({"type": "heartbeat"})
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


# Start Redis subscriber as a background task
_subscriber_task = None


def start_subscriber():
    global _subscriber_task
    loop = asyncio.get_event_loop()
    _subscriber_task = loop.create_task(redis_subscriber())

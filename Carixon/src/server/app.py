from __future__ import annotations

from datetime import datetime
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ..services.order_service import order_service
from ..utils.logger import get_logger

app = FastAPI(title="Carixon RT Server")
logger = get_logger("RTServer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connections: Dict[str, WebSocket] = {}


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Carixon RT server started at %s", datetime.utcnow().isoformat())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("Carixon RT server stopped")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/orders")
async def list_orders() -> list[dict]:
    return [order.model_dump() for order in order_service.list()]


@app.websocket("/ws")
async def websocket_endpoint(socket: WebSocket) -> None:
    await socket.accept()
    connection_id = socket.headers.get("x-connection-id") or str(id(socket))
    connections[connection_id] = socket
    logger.info("Client %s connected", connection_id)
    try:
        while True:
            message = await socket.receive_json()
            if message.get("type") == "ping":
                await socket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            elif message.get("type") == "order_status":
                order_id = int(message["order_id"])
                status = message["status"]
                dto = order_service.change_status(order_id, status)
                await broadcast({"type": "order_status", "payload": dto.model_dump()})
    except WebSocketDisconnect:
        logger.info("Client %s disconnected", connection_id)
    finally:
        connections.pop(connection_id, None)


async def broadcast(message: dict) -> None:
    for socket in list(connections.values()):
        await socket.send_json(message)

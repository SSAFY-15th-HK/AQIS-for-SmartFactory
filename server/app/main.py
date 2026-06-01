import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.conveyor import conveyor
from app.config import settings
from app.schemas.events import DetectionData
from app.services.stats_service import stats_service
from app.ws.manager import manager

app = FastAPI(title="AQIS Smart Factory API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COLORS = ["red", "green", "blue", "yellow"]


def system_status_event() -> dict:
    return {
        "type": "system_status",
        "data": {
            "server_ok": True,
            "conveyor_ok": True,
            "vision_ok": True,
            "robot_ok": True,
            "voice_ok": True,
            "mode": settings.mode,
        },
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": settings.mode,
        "stats": stats_service.current(),
    }


@app.get("/api/stats/current")
def current_stats() -> dict:
    return stats_service.current()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await websocket.send_json(system_status_event())
    try:
        while True:
            # Keep the connection open. UI can send ping/debug text if needed.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/mock/detection")
async def create_mock_detection(color: str | None = None) -> dict:
    selected_color = color if color in COLORS else random.choice(COLORS)
    is_defect = selected_color == "red"
    current = stats_service.add_detection(is_defect)

    if is_defect:
        conveyor.sort_defect()
    else:
        conveyor.sort_normal()

    data = DetectionData(
        id=current["session_total"],
        color=selected_color,  # type: ignore[arg-type]
        is_defect=is_defect,
        confidence=round(random.uniform(0.86, 0.98), 2),
        bbox=[random.randint(250, 360), random.randint(180, 260), 80, 60],
        session_total=current["session_total"],
        session_defects=current["session_defects"],
        defect_rate=current["defect_rate"],
    )
    event = {"type": "detection", "data": data.model_dump()}
    await manager.broadcast(event)
    await manager.broadcast({"type": "conveyor_status", "data": conveyor.status()})
    return {"status": "ok", "event": event}


@app.post("/api/conveyor/start")
async def start_conveyor() -> dict:
    event = {"type": "conveyor_status", "data": conveyor.start()}
    await manager.broadcast(event)
    return {"status": "ok", "event": event}


@app.post("/api/conveyor/stop")
async def stop_conveyor() -> dict:
    event = {"type": "conveyor_status", "data": conveyor.stop()}
    await manager.broadcast(event)
    return {"status": "ok", "event": event}


@app.post("/api/emergency_stop")
async def emergency_stop() -> dict:
    conveyor.stop()
    stats_service.emergency_stop()
    events = [
        {"type": "conveyor_status", "data": conveyor.status()},
        {
            "type": "system_status",
            "data": {
                "server_ok": True,
                "conveyor_ok": True,
                "vision_ok": True,
                "robot_ok": True,
                "voice_ok": True,
                "emergency_stop_active": True,
                "mode": settings.mode,
            },
        },
    ]
    for event in events:
        await manager.broadcast(event)
    return {"status": "stopped", "events": events}

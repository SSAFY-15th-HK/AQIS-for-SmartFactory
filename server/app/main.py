import asyncio
import random
from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.adapters.conveyor import conveyor
from app.adapters.robodk import robodk
from app.config import settings
from app.schemas.events import DetectionData
from app.services.stats_service import stats_service
from app.services.text_command_service import TextCommandService
from app.ws.manager import manager

app = FastAPI(title="AQIS Smart Factory API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COLORS = ["red", "green", "blue", "yellow"]
text_command_service = TextCommandService(stats_service)


class SimDetectionRequest(BaseModel):
    part_id: str | None = None
    color: str = "blue"
    result: str | None = None
    source: str = "robodk"
    script_id: str | None = None
    confidence: float | None = None


class RoboDKStatusRequest(BaseModel):
    script_id: str | None = None
    connected: bool | None = None
    running: bool | None = None
    stage: str | None = None
    message: str | None = None
    red_x: float | None = None


class TextCommandRequest(BaseModel):
    text: str


class AgvDispatchRequest(BaseModel):
    source: str = "ui"
    script_id: str | None = None


class AgvStateRequest(BaseModel):
    status: str
    source: str = "robodk"
    script_id: str | None = None
    message: str | None = None
    waypoint_index: int | None = None
    waypoint_total: int | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None


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
            **stats_service.current(),
        },
    }


def sim_status_event() -> dict:
    return stats_service.status_event()


def robodk_status_event() -> dict:
    return {"type": "robodk_status", "data": robodk.status()}


def apply_robodk_status_to_stats(status: dict) -> None:
    if status.get("running"):
        stats_service.set_robodk_status("RUNNING")
    elif status.get("connected"):
        stats_service.set_robodk_status("CONNECTED")
    else:
        stats_service.set_robodk_status("DISCONNECTED")


async def broadcast_current_status() -> None:
    await manager.broadcast(system_status_event())
    await manager.broadcast(sim_status_event())
    await manager.broadcast({"type": "conveyor_status", "data": conveyor.status()})
    await manager.broadcast(robodk_status_event())


async def run_agv_mission_background() -> None:
    await stats_service.run_agv_mission(manager.broadcast)
    await manager.broadcast(sim_status_event())


def schedule_agv_if_needed(before_status: str, *, source: str = "mock") -> None:
    if source == "robodk":
        return
    current = stats_service.current()
    if before_status == "IDLE" and current["agv_status"] == "MOVING_TO_DEFECT_BIN":
        asyncio.create_task(run_agv_mission_background())


def should_wait_for_robodk_agv(source: str) -> bool:
    return source != "mock" and bool(robodk.status().get("connected"))


def is_active_robodk_event(source: str, script_id: str | None) -> bool:
    if source != "robodk":
        return True
    active_script_id = robodk.status().get("active_script_id")
    return not active_script_id or script_id == active_script_id


def detection_event_from_current(color: str, is_defect: bool, confidence: float | None = None) -> dict:
    current = stats_service.current()
    data = DetectionData(
        id=current["session_total"],
        color=color if color in COLORS else "blue",  # type: ignore[arg-type]
        is_defect=is_defect,
        confidence=confidence if confidence is not None else round(random.uniform(0.86, 0.98), 2),
        bbox=[random.randint(250, 360), random.randint(180, 260), 80, 60],
        session_total=current["session_total"],
        session_defects=current["session_defects"],
        defect_rate=current["defect_rate"],
    ).model_dump()
    data.update(
        {
            "normal_count": current["normal_count"],
            "defect_bin_load": current["defect_bin_load"],
            "defect_threshold": current["defect_threshold"],
            "agv_status": current["agv_status"],
        }
    )
    return {"type": "detection", "data": data}


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": settings.mode,
        "stats": stats_service.current(),
        "robodk": robodk.status(),
    }


@app.get("/api/robodk/command")
def robodk_command(script_id: str | None = None) -> dict:
    """Polled by the RoboDK Python script. Reading consumes the pending command."""
    return {"command": robodk.consume_command(script_id)}


@app.post("/api/robodk/status")
async def update_robodk_status(payload: RoboDKStatusRequest) -> dict:
    active_script_id = robodk.status().get("active_script_id")
    if active_script_id and not payload.script_id:
        return {"status": "ignored", "reason": "stale_robodk_script", "data": robodk.status()}

    status = robodk.update_status(**payload.model_dump())
    apply_robodk_status_to_stats(status)
    event = robodk_status_event()
    await manager.broadcast(event)
    await manager.broadcast(sim_status_event())
    return {"status": "ok", "data": {**status, "robodk_status": stats_service.current()["robodk_status"]}}


@app.get("/api/stats/current")
def current_stats() -> dict:
    return stats_service.current()


@app.get("/api/sim/status")
def sim_status() -> dict:
    return stats_service.current()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await websocket.send_json(system_status_event())
    await websocket.send_json(sim_status_event())
    await websocket.send_json({"type": "conveyor_status", "data": conveyor.status()})
    await websocket.send_json(robodk_status_event())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/sim/start")
async def start_simulation() -> dict:
    apply_robodk_status_to_stats(robodk.start_simulation())
    conveyor.start()
    event = {"type": "sim_status", "data": stats_service.start_simulation()}
    await broadcast_current_status()
    return event


@app.post("/api/sim/pause")
async def pause_simulation() -> dict:
    apply_robodk_status_to_stats(robodk.pause_simulation())
    conveyor.stop()
    event = {"type": "sim_status", "data": stats_service.pause_simulation()}
    await broadcast_current_status()
    return event


@app.post("/api/sim/stop")
async def stop_simulation() -> dict:
    apply_robodk_status_to_stats(robodk.stop_simulation())
    conveyor.stop()
    event = {"type": "sim_status", "data": stats_service.stop_simulation()}
    await broadcast_current_status()
    return event


@app.post("/api/sim/reset")
async def reset_simulation() -> dict:
    conveyor.stop()
    event = {"type": "sim_status", "data": stats_service.reset_all()}
    apply_robodk_status_to_stats(robodk.reset_simulation())
    await broadcast_current_status()
    return event


@app.post("/api/sim/detection")
async def create_sim_detection(payload: SimDetectionRequest) -> dict:
    if not is_active_robodk_event(payload.source, payload.script_id):
        return {"status": "ignored", "reason": "stale_robodk_script", "sim": stats_service.current()}

    color = payload.color if payload.color in COLORS else random.choice(COLORS)
    is_defect = payload.result == "defect" if payload.result else color == "red"
    before_status = stats_service.current()["agv_status"]
    stats_service.add_detection(
        is_defect=is_defect,
        color=color,
        part_id=payload.part_id,
        allow_auto_dispatch=payload.source != "robodk",
    )

    if is_defect:
        conveyor.sort_defect()
    else:
        conveyor.sort_normal()

    detection_event = detection_event_from_current(color, is_defect, payload.confidence)
    await manager.broadcast(detection_event)
    await manager.broadcast({"type": "conveyor_status", "data": conveyor.status()})
    await manager.broadcast(sim_status_event())
    schedule_agv_if_needed(before_status, source=payload.source)
    return {"status": "ok", "event": detection_event, "sim": stats_service.current()}


@app.post("/api/sim/agv/dispatch")
async def dispatch_agv(payload: AgvDispatchRequest | None = Body(default=None)) -> dict:
    payload = payload or AgvDispatchRequest()
    if not is_active_robodk_event(payload.source, payload.script_id):
        return {"status": "ignored", "reason": "stale_robodk_script", "event": stats_service.agv_event(), "sim": stats_service.current()}

    before_status = stats_service.current()["agv_status"]
    if payload.source == "robodk":
        stats_service.dispatch_agv(manual=True)
    elif should_wait_for_robodk_agv(payload.source):
        apply_robodk_status_to_stats(robodk.dispatch_agv())
    else:
        apply_robodk_status_to_stats(robodk.dispatch_agv())
        stats_service.dispatch_agv(manual=True)
        schedule_agv_if_needed(before_status, source=payload.source)

    await manager.broadcast(stats_service.agv_event())
    await manager.broadcast(robodk_status_event())
    await manager.broadcast(sim_status_event())
    return {"status": "ok", "event": stats_service.agv_event(), "sim": stats_service.current()}


@app.post("/api/sim/agv/state")
async def update_agv_state(payload: AgvStateRequest) -> dict:
    if not is_active_robodk_event(payload.source, payload.script_id):
        return {"status": "ignored", "reason": "stale_robodk_script", "event": stats_service.agv_event(), "sim": stats_service.current()}

    stats_service.update_agv_state(
        status=payload.status,
        message=payload.message,
        waypoint_index=payload.waypoint_index,
        waypoint_total=payload.waypoint_total,
        x=payload.x,
        y=payload.y,
        z=payload.z,
    )
    await manager.broadcast(stats_service.agv_event())
    await manager.broadcast(sim_status_event())
    return {"status": "ok", "event": stats_service.agv_event(), "sim": stats_service.current()}


@app.get("/api/sim/agv/status")
def agv_status() -> dict:
    return stats_service.agv_event()["data"]


@app.post("/api/text-command")
async def text_command(payload: TextCommandRequest) -> dict:
    parsed = text_command_service.parse(payload.text)
    intent = parsed["intent"]
    before_status = stats_service.current()["agv_status"]

    if intent == "START_SIM":
        apply_robodk_status_to_stats(robodk.start_simulation())
        conveyor.start()
        stats_service.start_simulation()
    elif intent == "PAUSE_SIM":
        apply_robodk_status_to_stats(robodk.pause_simulation())
        conveyor.stop()
        stats_service.pause_simulation()
    elif intent == "STOP_SIM":
        apply_robodk_status_to_stats(robodk.stop_simulation())
        conveyor.stop()
        stats_service.stop_simulation()
    elif intent == "RESET_SIM":
        stats_service.reset_all()
        apply_robodk_status_to_stats(robodk.reset_simulation())
        conveyor.stop()
    elif intent == "DISPATCH_AGV" and parsed["action_executed"]:
        apply_robodk_status_to_stats(robodk.dispatch_agv())
        if not should_wait_for_robodk_agv("text"):
            stats_service.dispatch_agv(manual=True)
            schedule_agv_if_needed(before_status)

    event = {
        "type": "text_command",
        "data": {
            "user_text": payload.text,
            "intent": parsed["intent"],
            "message": parsed["message"],
            "assistant_message": parsed["message"],
            "action_executed": parsed["action_executed"],
        },
    }
    await manager.broadcast(event)
    await broadcast_current_status()
    return event["data"]


@app.post("/api/mock/detection")
async def create_mock_detection(color: str | None = None) -> dict:
    selected_color = color if color in COLORS else random.choice(COLORS)
    payload = SimDetectionRequest(color=selected_color, result="defect" if selected_color == "red" else "normal", source="mock")
    return await create_sim_detection(payload)


@app.post("/api/conveyor/start")
async def start_conveyor() -> dict:
    stats_service.start_simulation()
    event = {"type": "conveyor_status", "data": conveyor.start()}
    await manager.broadcast(event)
    await manager.broadcast(sim_status_event())
    return {"status": "ok", "event": event}


@app.post("/api/conveyor/stop")
async def stop_conveyor() -> dict:
    stats_service.stop_simulation()
    event = {"type": "conveyor_status", "data": conveyor.stop()}
    await manager.broadcast(event)
    await manager.broadcast(sim_status_event())
    return {"status": "ok", "event": event}

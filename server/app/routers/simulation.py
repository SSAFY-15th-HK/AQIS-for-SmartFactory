import asyncio
import random
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.adapters.conveyor import conveyor
from app.adapters.robodk import robodk
from app.schemas.events import DetectionData
from app.services.stats_service import stats_service
from app.ws.manager import manager

COLORS = ["red", "green", "blue", "yellow"]

router = APIRouter(prefix="/api/sim", tags=["simulation"])
mock_router = APIRouter(tags=["simulation"])
_status_broadcaster: Callable[[], Awaitable[None]] | None = None


class SimDetectionRequest(BaseModel):
    part_id: str | None = None
    color: str = "blue"
    result: str | None = None
    source: str = "robodk"
    script_id: str | None = None
    confidence: float | None = None


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


def set_status_broadcaster(callback: Callable[[], Awaitable[None]]) -> None:
    global _status_broadcaster
    _status_broadcaster = callback


async def broadcast_current_status() -> None:
    if _status_broadcaster:
        await _status_broadcaster()


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


async def run_agv_mission_background() -> None:
    await stats_service.run_agv_mission(manager.broadcast)
    await manager.broadcast(sim_status_event())


def schedule_agv_if_needed(before_status: str, *, source: str = "mock") -> None:
    if source == "robodk":
        return
    current = stats_service.current()
    if before_status == "IDLE" and current["agv_status"] == "MOVING_TO_PICKUP":
        try:
            asyncio.get_running_loop().create_task(run_agv_mission_background())
        except RuntimeError:
            return


def should_wait_for_robodk_agv(source: str) -> bool:
    return source != "mock" and bool(robodk.status().get("connected"))


def is_active_robodk_event(source: str, script_id: str | None) -> bool:
    if source != "robodk":
        return True
    active_script_id = robodk.status().get("active_script_id")
    return not active_script_id or script_id == active_script_id


def _bbox_from_payload(payload: dict | None) -> list[int] | None:
    if not payload:
        return None
    bbox = payload.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        try:
            return [int(value) for value in bbox[:4]]
        except (TypeError, ValueError):
            return None
    return None


def _confidence_from_payload(payload: dict | None, fallback: float | None = None) -> float | None:
    value = payload.get("confidence") if payload else fallback
    return float(value) if isinstance(value, (int, float)) else fallback


def detection_event_from_current(
    color: str,
    is_defect: bool,
    confidence: float | None = None,
    *,
    bbox: list[int] | None = None,
    payload: dict | None = None,
    random_fallback: bool = True,
) -> dict:
    current = stats_service.current()
    payload_bbox = bbox or _bbox_from_payload(payload)
    payload_confidence = _confidence_from_payload(payload, confidence)
    data = DetectionData(
        id=current["session_total"],
        color=color if color in COLORS else "blue",  # type: ignore[arg-type]
        is_defect=is_defect,
        confidence=payload_confidence
        if payload_confidence is not None
        else (round(random.uniform(0.86, 0.98), 2) if random_fallback else 0.0),
        bbox=payload_bbox
        or ([random.randint(250, 360), random.randint(180, 260), 80, 60] if random_fallback else [0, 0, 0, 0]),
        session_total=current["session_total"],
        session_defects=current["session_defects"],
        defect_rate=current["defect_rate"],
    ).model_dump()
    data.update(
        {
            "normal_count": current["normal_count"],
            "agv_status": current["agv_status"],
        }
    )
    if payload:
        for key in ("source", "label", "center", "image_size", "result", "part_id"):
            if key in payload:
                data[key] = payload[key]
    return {"type": "detection", "data": data}


@router.get("/status")
def sim_status() -> dict:
    return stats_service.current()


@router.post("/start")
async def start_simulation() -> dict:
    apply_robodk_status_to_stats(robodk.start_simulation())
    conveyor.start()
    event = {"type": "sim_status", "data": stats_service.start_simulation()}
    await broadcast_current_status()
    return event


@router.post("/pause")
async def pause_simulation() -> dict:
    apply_robodk_status_to_stats(robodk.pause_simulation())
    conveyor.stop()
    event = {"type": "sim_status", "data": stats_service.pause_simulation()}
    await broadcast_current_status()
    return event


@router.post("/stop")
async def stop_simulation() -> dict:
    apply_robodk_status_to_stats(robodk.stop_simulation())
    conveyor.stop()
    event = {"type": "sim_status", "data": stats_service.stop_simulation()}
    await broadcast_current_status()
    return event


@router.post("/reset")
async def reset_simulation() -> dict:
    conveyor.stop()
    event = {"type": "sim_status", "data": stats_service.reset_all()}
    apply_robodk_status_to_stats(robodk.reset_simulation())
    await broadcast_current_status()
    return event


@router.post("/detection")
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


@router.post("/agv/dispatch")
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


@router.post("/agv/state")
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


@router.get("/agv/status")
def agv_status() -> dict:
    return stats_service.agv_event()["data"]


@mock_router.post("/api/mock/detection")
async def create_mock_detection(color: str | None = None) -> dict:
    selected_color = color if color in COLORS else random.choice(COLORS)
    payload = SimDetectionRequest(color=selected_color, result="defect" if selected_color == "red" else "normal", source="mock")
    return await create_sim_detection(payload)

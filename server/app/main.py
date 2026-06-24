import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.adapters.conveyor import conveyor
from app.adapters.robodk import robodk
from app.config import settings
from app.routers.simulation import (
    AgvDispatchRequest,
    AgvStateRequest,
    COLORS,
    SimDetectionRequest,
    apply_robodk_status_to_stats,
    agv_status,
    create_mock_detection,
    create_sim_detection,
    detection_event_from_current,
    dispatch_agv,
    mock_router,
    pause_simulation,
    reset_simulation,
    robodk_status_event,
    router as sim_router,
    schedule_agv_if_needed,
    set_status_broadcaster,
    sim_status,
    sim_status_event,
    start_simulation,
    stop_simulation,
    update_agv_state,
)
from app.services.detection_deduper import DetectionDeduper
from app.services.dobot_pick_place import DobotPickPlaceService
from app.services.llm_command_service import LlmCommandService, command_message
from app.services.process_service import AqisProcessService
from app.services.ros_bridge import RosBridgeService
from app.services.stats_service import stats_service
from app.ws.manager import manager

app = FastAPI(title="AQIS Smart Factory API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_command_service = LlmCommandService(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model,
    timeout_sec=settings.llm_timeout_sec,
)
aqis_process = AqisProcessService(settings.aqis_start_command)
dobot_pick_place = DobotPickPlaceService(settings.robot_mode, settings.dobot_pick_place_command, resume_callback=conveyor.start)
ros_bridge = RosBridgeService(enabled=settings.ros_enabled)
detection_deduper = DetectionDeduper(
    window_sec=settings.detection_dedupe_window_sec,
    iou_threshold=settings.detection_dedupe_iou_threshold,
    center_distance_px=settings.detection_dedupe_center_distance_px,
)
pending_stopped_pick: dict = {
    "active": False,
    "ready_at": 0.0,
    "started_at": 0.0,
    "first_detection": None,
}


class RoboDKStatusRequest(BaseModel):
    script_id: str | None = None
    connected: bool | None = None
    running: bool | None = None
    stage: str | None = None
    message: str | None = None
    red_x: float | None = None


class TextCommandRequest(BaseModel):
    text: str


@app.on_event("startup")
async def on_startup() -> None:
    ros_bridge.start(manager.broadcast, handle_ros_detection)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    ros_bridge.stop()
    aqis_process.stop(timeout_sec=2.0)
    conveyor.stop()
    dobot_pick_place.stop(timeout_sec=1.0)


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
            "aqis_process": aqis_process.status(),
            "ros_bridge": ros_bridge.status(),
            **stats_service.current(),
        },
    }


def runtime_config_event() -> dict:
    return {
        "type": "runtime_config",
        "data": {
            "realsense_stream_url": settings.realsense_stream_url,
            "turtlebot_view_url": settings.turtlebot_view_url,
            "ros_enabled": settings.ros_enabled,
        },
    }


def dobot_pick_place_event() -> dict:
    return {"type": "dobot_pick_place_status", "data": dobot_pick_place.status()}


def reset_pending_stopped_pick() -> None:
    pending_stopped_pick.update(
        {
            "active": False,
            "ready_at": 0.0,
            "started_at": 0.0,
            "first_detection": None,
        }
    )


def pending_stopped_pick_event() -> dict:
    return {
        "type": "stopped_pick_status",
        "data": {
            "active": pending_stopped_pick["active"],
            "ready_at": pending_stopped_pick["ready_at"],
            "started_at": pending_stopped_pick["started_at"],
            "first_detection": pending_stopped_pick["first_detection"],
        },
    }


async def broadcast_current_status() -> None:
    await manager.broadcast(system_status_event())
    await manager.broadcast({"type": "aqis_process", "data": aqis_process.status()})
    await manager.broadcast(sim_status_event())
    await manager.broadcast({"type": "conveyor_status", "data": conveyor.status()})
    await manager.broadcast(robodk_status_event())
    await manager.broadcast(dobot_pick_place_event())
    await manager.broadcast(pending_stopped_pick_event())


def normalize_detection_payload(payload: dict) -> dict | None:
    if payload.get("detected") is False or payload.get("has_detection") is False:
        return None

    detections = payload.get("detections")
    if isinstance(detections, list) and not detections:
        return None

    result = str(payload.get("result", "")).strip().lower()
    if result in {"none", "no_detection", "no detection", "empty"}:
        return None

    if isinstance(payload.get("is_defect"), bool):
        is_defect = bool(payload["is_defect"])
    elif result in {"defect", "defective", "ng", "bad"}:
        is_defect = True
    elif result in {"normal", "ok", "good", "pass"}:
        is_defect = False
    elif isinstance(detections, list) and detections:
        is_defect = True
    else:
        return None

    color = str(payload.get("defect_class") or payload.get("color") or payload.get("label") or ("red" if is_defect else "blue")).lower()
    return {**payload, "is_defect": is_defect, "color": color, "result": "defect" if is_defect else "normal"}


def expanded_detection_payloads(payload: dict) -> list[dict]:
    detections = payload.get("detections")
    if not isinstance(detections, list):
        return [payload]

    shared = {
        key: payload[key]
        for key in ("source", "frame_id", "timestamp", "image_size")
        if key in payload
    }
    return [{**shared, **item} for item in detections if isinstance(item, dict)]


def detection_timestamp(payload: dict) -> float | None:
    try:
        return float(payload["timestamp"])
    except (KeyError, TypeError, ValueError):
        return None


def is_fresh_stopped_detection(payload: dict, now: float) -> bool:
    timestamp = detection_timestamp(payload)
    if timestamp is None:
        return True
    if timestamp < float(pending_stopped_pick["ready_at"]):
        return False
    return now - timestamp <= settings.dobot_pick_max_detection_age_sec


def handle_ros_detection(payload: dict) -> list[dict]:
    if stats_service.current().get("system_status") != "RUNNING":
        return []

    before_status = stats_service.current()["agv_status"]
    now = time.time()
    detection_events = []
    accepted = []
    normalized_items = [
        normalized
        for item in expanded_detection_payloads(payload)
        if (normalized := normalize_detection_payload(item))
    ]
    defect_items = [item for item in normalized_items if item["is_defect"]]

    if pending_stopped_pick["active"]:
        stopped_items = [item for item in defect_items if is_fresh_stopped_detection(item, now)]
        if stopped_items and now >= float(pending_stopped_pick["ready_at"]):
            stopped_detection = next((item for item in stopped_items if item.get("has_depth")), stopped_items[0])
            pick_result = dobot_pick_place.trigger(stopped_detection)
            reset_pending_stopped_pick()
            return [
                {"type": "conveyor_status", "data": conveyor.status()},
                dobot_pick_place_event(),
                pending_stopped_pick_event(),
            ]
        return []

    for normalized in normalized_items:
        if not detection_deduper.should_accept(normalized):
            continue

        is_defect = bool(normalized["is_defect"])
        color = str(normalized["color"]).lower()
        stats_service.add_detection(
            is_defect=is_defect,
            color=color if color in COLORS else None,
            part_id=normalized.get("part_id"),
            allow_auto_dispatch=True,
            metadata={
                key: normalized[key]
                for key in (
                    "confidence",
                    "bbox",
                    "center",
                    "image_size",
                    "source",
                    "label",
                    "result",
                    "roi_hit",
                    "roi",
                    "has_depth",
                    "depth_center",
                    "depth_m",
                    "camera_point_m",
                )
                if key in normalized
            },
        )
        accepted.append(normalized)
        detection_events.append(detection_event_from_current(color, is_defect, payload=normalized, random_fallback=False))

    if not accepted:
        return []

    if any(item["is_defect"] for item in accepted):
        conveyor.stop()
        pending_stopped_pick.update(
            {
                "active": True,
                "started_at": now,
                "ready_at": now + settings.dobot_pick_after_stop_delay_sec,
                "first_detection": next(item for item in accepted if item["is_defect"]),
            }
        )
        pick_result = None
    else:
        pick_result = None

    schedule_agv_if_needed(before_status, source="ros")
    events = detection_events + [{"type": "conveyor_status", "data": conveyor.status()}, sim_status_event(), pending_stopped_pick_event()]
    if pick_result:
        events.append(dobot_pick_place_event())
    return events


def real_state() -> dict:
    return {
        "stats": stats_service.current(),
        "process": aqis_process.status(),
        "ros": ros_bridge.status(),
        "dobot": ros_bridge.latest_dobot_status,
        "dobot_pick_place": dobot_pick_place.status(),
        "turtlebot_pose": ros_bridge.latest_turtlebot_pose,
        "conveyor": conveyor.status(),
    }


def conveyor_api_response(event: dict, *, success_status: str = "ok") -> dict:
    data = event.get("data", {})
    if data.get("command_ok") is False or data.get("last_error"):
        return {
            "status": "error",
            "message": data.get("last_error") or "Conveyor command failed.",
            "event": event,
        }
    return {"status": success_status, "event": event}


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": settings.mode,
        "stats": stats_service.current(),
        "robodk": robodk.status(),
        "aqis_process": aqis_process.status(),
        "ros_bridge": ros_bridge.status(),
    }


@app.get("/api/runtime/config")
def runtime_config() -> dict:
    return runtime_config_event()["data"]


@app.get("/api/aqis/status")
def aqis_status() -> dict:
    return {"process": aqis_process.status(), "ros_bridge": ros_bridge.status(), "state": real_state()}


@app.post("/api/aqis/start")
async def start_aqis() -> dict:
    reset_pending_stopped_pick()
    result = aqis_process.start()
    stats_service.start_simulation()
    conveyor_result = conveyor.start()
    await manager.broadcast({"type": "aqis_process", "data": aqis_process.status()})
    await manager.broadcast({"type": "conveyor_status", "data": conveyor_result})
    await broadcast_current_status()
    return {**result, "conveyor": conveyor_result}


@app.post("/api/aqis/stop")
async def stop_aqis() -> dict:
    reset_pending_stopped_pick()
    result = aqis_process.stop()
    stats_service.stop_simulation()
    conveyor_result = conveyor.stop()
    dobot_result = dobot_pick_place.stop()
    await manager.broadcast({"type": "aqis_process", "data": aqis_process.status()})
    await manager.broadcast({"type": "conveyor_status", "data": conveyor_result})
    await manager.broadcast(dobot_pick_place_event())
    await broadcast_current_status()
    return {**result, "conveyor": conveyor_result, "dobot_pick_place": dobot_result}


@app.post("/api/emergency_stop")
async def emergency_stop() -> dict:
    reset_pending_stopped_pick()
    process_result = aqis_process.stop(timeout_sec=2.0)
    stats_service.stop_simulation()
    conveyor_result = conveyor.emergency_stop()
    dobot_result = dobot_pick_place.stop(timeout_sec=1.0)
    event = {
        "type": "emergency_stop",
        "data": {
            "status": "stopped" if conveyor_result.get("command_ok", True) else "error",
            "process": process_result["process"],
            "conveyor": conveyor_result,
            "dobot_pick_place": dobot_result,
            "message": "Emergency stop executed.",
        },
    }
    await manager.broadcast(event)
    await broadcast_current_status()
    response = {"status": event["data"]["status"], "event": event}
    if response["status"] == "error":
        response["message"] = conveyor_result.get("last_error") or "Conveyor emergency stop failed."
    return response


@app.get("/api/dobot/pick_place/status")
def dobot_pick_place_status() -> dict:
    return {"status": "ok", "data": dobot_pick_place.status()}


@app.post("/api/dobot/pick_place")
async def trigger_dobot_pick_place() -> dict:
    result = dobot_pick_place.trigger({"source": "manual"})
    await manager.broadcast(dobot_pick_place_event())
    return result


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


@app.post("/api/stats/reset")
async def reset_stats() -> dict:
    detection_deduper.reset()
    reset_pending_stopped_pick()
    data = stats_service.reset_all()
    event = {"type": "sim_status", "data": data}
    await manager.broadcast(event)
    await manager.broadcast(system_status_event())
    return {"status": "ok", "event": event}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    await websocket.send_json(runtime_config_event())
    await websocket.send_json(system_status_event())
    await websocket.send_json({"type": "aqis_process", "data": aqis_process.status()})
    await websocket.send_json(sim_status_event())
    await websocket.send_json({"type": "conveyor_status", "data": conveyor.status()})
    await websocket.send_json(robodk_status_event())
    await websocket.send_json(dobot_pick_place_event())
    await websocket.send_json(pending_stopped_pick_event())
    if ros_bridge.latest_map_event:
        await websocket.send_json(ros_bridge.latest_map_event)
    if ros_bridge.latest_turtlebot_pose:
        await websocket.send_json({"type": "turtlebot_pose", "data": ros_bridge.latest_turtlebot_pose})
    if ros_bridge.latest_dobot_status:
        await websocket.send_json({"type": "dobot_status", "data": ros_bridge.latest_dobot_status})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


set_status_broadcaster(broadcast_current_status)
app.include_router(sim_router)
app.include_router(mock_router)


@app.post("/api/text-command")
async def text_command(payload: TextCommandRequest) -> dict:
    parsed = llm_command_service.classify(payload.text)
    intent = parsed["intent"]
    before_status = stats_service.current()["agv_status"]
    action_status: str | None = None

    if intent == "START_AQIS":
        reset_pending_stopped_pick()
        result = aqis_process.start()
        action_status = result["status"]
        conveyor_result = conveyor.start()
        if conveyor_result.get("command_ok") is False:
            action_status = "error"
        stats_service.start_simulation()
    elif intent == "STOP_AQIS":
        reset_pending_stopped_pick()
        result = aqis_process.stop()
        action_status = result["status"]
        conveyor_result = conveyor.stop()
        dobot_pick_place.stop()
        if conveyor_result.get("command_ok") is False:
            action_status = "error"
        stats_service.stop_simulation()
    elif intent == "EMERGENCY_STOP":
        reset_pending_stopped_pick()
        result = aqis_process.stop(timeout_sec=2.0)
        action_status = result["status"]
        conveyor_result = conveyor.emergency_stop()
        dobot_pick_place.stop(timeout_sec=1.0)
        if conveyor_result.get("command_ok") is False:
            action_status = "error"
        stats_service.stop_simulation()
    elif intent == "DISPATCH_AGV":
        if stats_service.current()["session_defects"] <= 0:
            action_status = "blocked"
        else:
            stats_service.dispatch_agv(manual=True)
            schedule_agv_if_needed(before_status)

    message = command_message(intent, real_state(), action_status=action_status)

    event = {
        "type": "text_command",
        "data": {
            "user_text": payload.text,
            "intent": intent,
            "message": message,
            "assistant_message": message,
            "action_executed": intent not in {"UNKNOWN", "QUERY_STATUS", "QUERY_DEFECT_RATE", "QUERY_TOTAL_COUNT", "QUERY_DOBOT", "QUERY_TURTLEBOT_POSE"},
            "source": parsed.get("source", "unknown"),
            "llm_error": parsed.get("llm_error"),
        },
    }
    await manager.broadcast(event)
    await broadcast_current_status()
    return event["data"]


@app.post("/api/conveyor/start")
async def start_conveyor() -> dict:
    reset_pending_stopped_pick()
    stats_service.start_simulation()
    event = {"type": "conveyor_status", "data": conveyor.start()}
    await manager.broadcast(event)
    await manager.broadcast(sim_status_event())
    return conveyor_api_response(event)


@app.post("/api/conveyor/stop")
async def stop_conveyor() -> dict:
    reset_pending_stopped_pick()
    stats_service.stop_simulation()
    dobot_pick_place.stop()
    event = {"type": "conveyor_status", "data": conveyor.stop()}
    await manager.broadcast(event)
    await manager.broadcast(dobot_pick_place_event())
    await manager.broadcast(sim_status_event())
    return conveyor_api_response(event)

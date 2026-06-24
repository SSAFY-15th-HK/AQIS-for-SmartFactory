import asyncio
from typing import Awaitable, Callable

MissionCallback = Callable[[dict], Awaitable[None]]


class StatsService:
    def __init__(self, defect_threshold: int = 3, agv_step_delay: float = 1.0) -> None:
        _ = defect_threshold
        self.agv_step_delay = agv_step_delay
        self.reset_all()

    def reset_all(self) -> dict:
        self.total = 0
        self.defects = 0
        self.normal_count = 0
        self.completed_missions = 0
        self.system_status = "STOPPED"
        self.conveyor_status = "OFF"
        self.robodk_status = "MOCK"
        self.agv_status = "IDLE"
        self.current_mission_id: str | None = None
        self.agv_waypoint_index: int | None = None
        self.agv_waypoint_total: int | None = None
        self.agv_position: dict[str, float] | None = None
        self.agv_message = ""
        self.recent_detections: list[dict] = []
        self._mission_running = False
        return self.current()

    def start_simulation(self) -> dict:
        self.system_status = "RUNNING"
        self.conveyor_status = "ON"
        return self.current()

    def pause_simulation(self) -> dict:
        self.system_status = "PAUSED"
        self.conveyor_status = "PAUSED"
        return self.current()

    def stop_simulation(self) -> dict:
        self.system_status = "STOPPED"
        self.conveyor_status = "OFF"
        return self.current()

    def set_robodk_status(self, status: str) -> dict:
        self.robodk_status = status
        return self.current()

    def add_detection(
        self,
        is_defect: bool,
        color: str | None = None,
        part_id: str | None = None,
        allow_auto_dispatch: bool = True,
        metadata: dict | None = None,
    ) -> dict:
        self.total += 1
        result = "defect" if is_defect else "normal"
        if is_defect:
            self.defects += 1
        else:
            self.normal_count += 1

        detection = {
            "part_id": part_id or f"part_{self.total:03d}",
            "color": color or ("red" if is_defect else "blue"),
            "result": result,
            "is_defect": is_defect,
            "session_total": self.total,
            "session_defects": self.defects,
            "normal_count": self.normal_count,
            "defect_rate": self.current()["defect_rate"],
        }
        if metadata:
            detection.update(metadata)
        self.recent_detections = [detection, *self.recent_detections][:12]

        if allow_auto_dispatch and self.should_dispatch_agv():
            self.dispatch_agv()
        return self.current()

    def should_dispatch_agv(self) -> bool:
        return False

    def dispatch_agv(self, manual: bool = False) -> dict:
        if self._mission_running:
            return self.current()
        if manual and self.defects <= 0:
            return self.current()
        self._mission_running = True
        self.current_mission_id = f"mission_{self.completed_missions + 1:03d}"
        self.agv_status = "MOVING_TO_PICKUP"
        self.agv_waypoint_index = None
        self.agv_waypoint_total = None
        self.agv_position = None
        self.agv_message = "AGV mission dispatched."
        return self.current()

    def update_agv_state(
        self,
        *,
        status: str,
        message: str | None = None,
        waypoint_index: int | None = None,
        waypoint_total: int | None = None,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> dict:
        if not self._mission_running and status not in {"IDLE", "COMPLETED"}:
            self.dispatch_agv(manual=True)

        if status == "COMPLETED":
            self.completed_missions += 1
            self._mission_running = False
            self.agv_status = "IDLE"
        else:
            self.agv_status = status
            if status == "IDLE":
                self._mission_running = False

        self.agv_waypoint_index = waypoint_index
        self.agv_waypoint_total = waypoint_total
        if x is not None or y is not None or z is not None:
            self.agv_position = {
                "x": x if x is not None else 0.0,
                "y": y if y is not None else 0.0,
                "z": z if z is not None else 0.0,
            }
        if message is not None:
            self.agv_message = message
        return self.current()

    async def run_agv_mission(self, callback: MissionCallback | None = None) -> dict:
        if not self._mission_running:
            self.dispatch_agv(manual=True)
        if not self._mission_running:
            return self.current()

        for status in [
            "MOVING_TO_PICKUP",
            "LOADING",
            "MOVING_TO_DROPOFF",
            "UNLOADING",
            "RETURNING_HOME",
            "COMPLETED",
        ]:
            self.agv_status = status
            if callback:
                await callback(self.agv_event())
            if self.agv_step_delay:
                await asyncio.sleep(self.agv_step_delay)

        self.completed_missions += 1
        self.agv_status = "IDLE"
        self._mission_running = False
        if callback:
            await callback(self.agv_event())
        return self.current()

    async def finish_pending_agv_mission(self) -> dict:
        return await self.run_agv_mission()

    def current(self) -> dict:
        defect_rate = self.defects / self.total if self.total else 0.0
        return {
            "system_status": self.system_status,
            "conveyor_status": self.conveyor_status,
            "robodk_status": self.robodk_status,
            "session_total": self.total,
            "session_defects": self.defects,
            "normal_count": self.normal_count,
            "defect_rate": round(defect_rate, 4),
            "agv_status": self.agv_status,
            "current_mission_id": self.current_mission_id,
            "completed_missions": self.completed_missions,
            "agv_waypoint_index": self.agv_waypoint_index,
            "agv_waypoint_total": self.agv_waypoint_total,
            "agv_position": self.agv_position,
            "agv_message": self.agv_message,
            "recent_detections": self.recent_detections,
        }

    def status_event(self) -> dict:
        return {"type": "sim_status", "data": self.current()}

    def agv_event(self) -> dict:
        return {
            "type": "agv_mission",
            "data": {
                "mission_id": self.current_mission_id,
                "status": self.agv_status,
                "completed_missions": self.completed_missions,
                "waypoint_index": self.agv_waypoint_index,
                "waypoint_total": self.agv_waypoint_total,
                "position": self.agv_position,
                "message": self.agv_message,
            },
        }


stats_service = StatsService()

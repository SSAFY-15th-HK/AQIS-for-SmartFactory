import asyncio
from typing import Awaitable, Callable

MissionCallback = Callable[[dict], Awaitable[None]]


class StatsService:
    def __init__(self, defect_threshold: int = 3, agv_step_delay: float = 1.0) -> None:
        self.defect_threshold = defect_threshold
        self.agv_step_delay = agv_step_delay
        self.reset_all()

    def reset_all(self) -> dict:
        self.total = 0
        self.defects = 0
        self.normal_count = 0
        self.defect_bin_load = 0
        self.completed_missions = 0
        self.emergency_stop_active = False
        self.system_status = "STOPPED"
        self.conveyor_status = "OFF"
        self.robodk_status = "MOCK"
        self.agv_status = "IDLE"
        self.current_mission_id: str | None = None
        self.recent_detections: list[dict] = []
        self._mission_running = False
        return self.current()

    def start_simulation(self) -> dict:
        if not self.emergency_stop_active:
            self.system_status = "RUNNING"
            self.conveyor_status = "ON"
        return self.current()

    def pause_simulation(self) -> dict:
        if not self.emergency_stop_active:
            self.system_status = "PAUSED"
            self.conveyor_status = "PAUSED"
        return self.current()

    def stop_simulation(self) -> dict:
        if not self.emergency_stop_active:
            self.system_status = "STOPPED"
            self.conveyor_status = "OFF"
        return self.current()

    def reset_emergency_stop(self) -> dict:
        self.emergency_stop_active = False
        self.system_status = "STOPPED"
        self.conveyor_status = "OFF"
        return self.current()

    def emergency_stop(self) -> dict:
        self.emergency_stop_active = True
        self.system_status = "EMERGENCY_STOP"
        self.conveyor_status = "OFF"
        self.agv_status = "EMERGENCY_STOP"
        self._mission_running = False
        return self.current()

    def add_detection(self, is_defect: bool, color: str | None = None, part_id: str | None = None) -> dict:
        self.total += 1
        result = "defect" if is_defect else "normal"
        if is_defect:
            self.defects += 1
            self.defect_bin_load += 1
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
            "defect_bin_load": self.defect_bin_load,
        }
        self.recent_detections = [detection, *self.recent_detections][:12]

        if self.should_dispatch_agv():
            self.dispatch_agv()
        return self.current()

    def should_dispatch_agv(self) -> bool:
        return (
            not self.emergency_stop_active
            and not self._mission_running
            and self.agv_status == "IDLE"
            and self.defect_bin_load >= self.defect_threshold
        )

    def dispatch_agv(self, manual: bool = False) -> dict:
        if self.emergency_stop_active:
            return self.current()
        if self._mission_running:
            return self.current()
        if manual and self.defect_bin_load <= 0:
            return self.current()
        self._mission_running = True
        self.current_mission_id = f"mission_{self.completed_missions + 1:03d}"
        self.agv_status = "MOVING_TO_DEFECT_BIN"
        return self.current()

    async def run_agv_mission(self, callback: MissionCallback | None = None) -> dict:
        if not self._mission_running:
            self.dispatch_agv(manual=True)
        if not self._mission_running:
            return self.current()

        for status in [
            "MOVING_TO_DEFECT_BIN",
            "LOADING_DEFECT_BIN",
            "MOVING_TO_DROPOFF",
            "UNLOADING",
            "RETURNING_HOME",
            "COMPLETED",
        ]:
            if self.emergency_stop_active:
                break
            self.agv_status = status
            if callback:
                await callback(self.agv_event())
            if self.agv_step_delay:
                await asyncio.sleep(self.agv_step_delay)

        if not self.emergency_stop_active:
            self.completed_missions += 1
            self.defect_bin_load = 0
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
            "defect_bin_load": self.defect_bin_load,
            "defect_threshold": self.defect_threshold,
            "agv_status": self.agv_status,
            "current_mission_id": self.current_mission_id,
            "completed_missions": self.completed_missions,
            "recent_detections": self.recent_detections,
            "emergency_stop_active": self.emergency_stop_active,
        }

    def status_event(self) -> dict:
        return {"type": "sim_status", "data": self.current()}

    def agv_event(self) -> dict:
        return {
            "type": "agv_mission",
            "data": {
                "mission_id": self.current_mission_id,
                "status": self.agv_status,
                "defect_bin_load": self.defect_bin_load,
                "completed_missions": self.completed_missions,
            },
        }


stats_service = StatsService()

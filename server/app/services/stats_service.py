class StatsService:
    def __init__(self) -> None:
        self.total = 0
        self.defects = 0
        self.emergency_stop_active = False

    def add_detection(self, is_defect: bool) -> dict:
        self.total += 1
        if is_defect:
            self.defects += 1
        return self.current()

    def current(self) -> dict:
        defect_rate = self.defects / self.total if self.total else 0.0
        return {
            "session_total": self.total,
            "session_defects": self.defects,
            "defect_rate": round(defect_rate, 4),
            "emergency_stop_active": self.emergency_stop_active,
        }

    def emergency_stop(self) -> dict:
        self.emergency_stop_active = True
        return self.current()

    def reset_emergency_stop(self) -> dict:
        self.emergency_stop_active = False
        return self.current()


stats_service = StatsService()

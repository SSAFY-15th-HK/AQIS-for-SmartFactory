from app.services.stats_service import StatsService


class TextCommandService:
    def __init__(self, stats: StatsService) -> None:
        self.stats = stats

    def parse(self, text: str) -> dict:
        normalized = text.strip().lower()
        current = self.stats.current()

        if any(keyword in normalized for keyword in ["비상", "emergency"]):
            return {
                "intent": "EMERGENCY_STOP",
                "message": "비상 정지를 실행합니다. 모든 시뮬레이션 동작을 중지합니다.",
                "action_executed": True,
            }
        if any(keyword in normalized for keyword in ["일시정지", "pause"]):
            return {"intent": "PAUSE_SIM", "message": "시뮬레이션을 일시정지합니다.", "action_executed": True}
        if any(keyword in normalized for keyword in ["시작", "start", "재개"]):
            return {"intent": "START_SIM", "message": "시뮬레이션을 시작합니다.", "action_executed": True}
        if any(keyword in normalized for keyword in ["멈춰", "정지", "stop"]):
            return {"intent": "STOP_SIM", "message": "시뮬레이션을 정지합니다.", "action_executed": True}
        if any(keyword in normalized for keyword in ["초기화", "reset"]):
            return {"intent": "RESET_SIM", "message": "시뮬레이션 상태와 카운트를 초기화합니다.", "action_executed": True}
        if any(keyword in normalized for keyword in ["비워", "수거", "agv", "출동"]):
            if current["defect_bin_load"] <= 0:
                return {
                    "intent": "DISPATCH_AGV",
                    "message": "현재 수거할 불량품이 없습니다. Defect Bin Load는 0개입니다.",
                    "action_executed": False,
                }
            return {"intent": "DISPATCH_AGV", "message": "불량품 수거 미션을 시작합니다.", "action_executed": True}
        if any(keyword in normalized for keyword in ["불량률", "defect rate"]):
            rate = current["defect_rate"] * 100
            return {
                "intent": "QUERY_DEFECT_RATE",
                "message": f"현재 총 {current['session_total']}개 검사했고, 불량품은 {current['session_defects']}개입니다. 불량률은 {rate:.1f}%입니다.",
                "action_executed": False,
            }
        if any(keyword in normalized for keyword in ["상태", "status"]):
            return {
                "intent": "QUERY_STATUS",
                "message": f"현재 시스템 상태는 {current['system_status']}, AGV 상태는 {current['agv_status']}, Defect Bin Load는 {current['defect_bin_load']}개입니다.",
                "action_executed": False,
            }

        return {
            "intent": "UNKNOWN",
            "message": "이해하지 못한 명령입니다. 예: 시작, 정지, 비상 정지, 불량품 비워줘, 불량률 알려줘",
            "action_executed": False,
        }

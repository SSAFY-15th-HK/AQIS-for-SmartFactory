from app.services.stats_service import StatsService


class TextCommandService:
    def __init__(self, stats: StatsService) -> None:
        self.stats = stats

    def parse(self, text: str) -> dict:
        normalized = text.strip().lower()
        current = self.stats.current()

        if any(keyword in normalized for keyword in ["pause", "일시정지", "잠시"]):
            return {
                "intent": "PAUSE_SIM",
                "message": "시뮬레이션을 일시정지합니다.",
                "action_executed": True,
            }
        if any(keyword in normalized for keyword in ["start", "시작", "재개"]):
            return {
                "intent": "START_SIM",
                "message": "시뮬레이션을 시작합니다.",
                "action_executed": True,
            }
        if any(keyword in normalized for keyword in ["stop", "정지", "멈춰"]):
            return {
                "intent": "STOP_SIM",
                "message": "시뮬레이션을 정지합니다.",
                "action_executed": True,
            }
        if any(keyword in normalized for keyword in ["reset", "초기화"]):
            return {
                "intent": "RESET_SIM",
                "message": "시뮬레이션 상태와 카운터를 초기화합니다.",
                "action_executed": True,
            }
        if any(keyword in normalized for keyword in ["agv", "비워", "수거", "출동"]):
            if current["session_defects"] <= 0:
                return {
                    "intent": "DISPATCH_AGV",
                    "message": "현재 수거할 불량품이 없습니다. 불량 카운트는 0개입니다.",
                    "action_executed": False,
                }
            return {
                "intent": "DISPATCH_AGV",
                "message": "불량품 수거 미션을 시작합니다.",
                "action_executed": True,
            }
        if any(keyword in normalized for keyword in ["defect rate", "불량률"]):
            rate = current["defect_rate"] * 100
            return {
                "intent": "QUERY_DEFECT_RATE",
                "message": (
                    f"현재 총 {current['session_total']}개 검사했고 "
                    f"불량품은 {current['session_defects']}개입니다. "
                    f"불량률은 {rate:.1f}%입니다."
                ),
                "action_executed": False,
            }
        if any(keyword in normalized for keyword in ["status", "상태"]):
            return {
                "intent": "QUERY_STATUS",
                "message": (
                    f"현재 시스템 상태는 {current['system_status']}, "
                    f"AGV 상태는 {current['agv_status']}, "
                    f"불량 카운트는 {current['session_defects']}개입니다."
                ),
                "action_executed": False,
            }

        return {
            "intent": "UNKNOWN",
            "message": "이해하지 못한 명령입니다. 시작, 정지, 초기화, AGV 출동, 상태 조회를 사용할 수 있습니다.",
            "action_executed": False,
        }

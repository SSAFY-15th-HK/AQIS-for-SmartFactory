import asyncio

from app.services.stats_service import StatsService
from app.services.text_command_service import TextCommandService


def test_defect_bin_load_triggers_agv_then_resets_after_mission():
    service = StatsService(defect_threshold=3, agv_step_delay=0)

    service.add_detection(is_defect=True, color="red")
    service.add_detection(is_defect=True, color="red")
    third = service.add_detection(is_defect=True, color="red")

    assert third["defect_bin_load"] == 3
    assert third["agv_status"] == "MOVING_TO_DEFECT_BIN"

    asyncio.run(service.finish_pending_agv_mission())

    current = service.current()
    assert current["defect_bin_load"] == 0
    assert current["completed_missions"] == 1
    assert current["agv_status"] == "IDLE"


def test_text_command_maps_korean_commands_to_intents_and_messages():
    stats = StatsService(defect_threshold=3, agv_step_delay=0)
    stats.add_detection(is_defect=False, color="blue")
    stats.add_detection(is_defect=True, color="red")
    service = TextCommandService(stats)

    status = service.parse("현재 상태 알려줘")
    defect_rate = service.parse("불량률 알려줘")
    dispatch = service.parse("불량품 비워줘")
    emergency = service.parse("비상 정지")

    assert status["intent"] == "QUERY_STATUS"
    assert "RUNNING" not in status["message"]
    assert defect_rate["intent"] == "QUERY_DEFECT_RATE"
    assert "50.0%" in defect_rate["message"]
    assert dispatch["intent"] == "DISPATCH_AGV"
    assert emergency["intent"] == "EMERGENCY_STOP"

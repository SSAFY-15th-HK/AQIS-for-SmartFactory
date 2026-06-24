import asyncio

from app.services.stats_service import StatsService
from app.services.text_command_service import TextCommandService


def test_defect_counts_do_not_auto_dispatch_bin_mission():
    service = StatsService(defect_threshold=3, agv_step_delay=0)

    service.add_detection(is_defect=True, color="red")
    service.add_detection(is_defect=True, color="red")
    third = service.add_detection(is_defect=True, color="red")

    assert third["session_defects"] == 3
    assert "defect_bin_load" not in third
    assert third["agv_status"] == "IDLE"


def test_manual_agv_mission_still_runs_without_bin_counter():
    service = StatsService(defect_threshold=3, agv_step_delay=0)
    service.add_detection(is_defect=True, color="red")
    service.dispatch_agv(manual=True)

    asyncio.run(service.finish_pending_agv_mission())

    current = service.current()
    assert "defect_bin_load" not in current
    assert current["completed_missions"] == 1
    assert current["agv_status"] == "IDLE"


def test_text_command_maps_commands_to_intents_and_messages():
    stats = StatsService(defect_threshold=3, agv_step_delay=0)
    stats.add_detection(is_defect=False, color="blue")
    stats.add_detection(is_defect=True, color="red")
    service = TextCommandService(stats)

    status = service.parse("status")
    defect_rate = service.parse("defect rate")
    dispatch = service.parse("agv")
    stop = service.parse("stop")

    assert status["intent"] == "QUERY_STATUS"
    assert "RUNNING" not in status["message"]
    assert defect_rate["intent"] == "QUERY_DEFECT_RATE"
    assert "50.0%" in defect_rate["message"]
    assert dispatch["intent"] == "DISPATCH_AGV"
    assert stop["intent"] == "STOP_SIM"

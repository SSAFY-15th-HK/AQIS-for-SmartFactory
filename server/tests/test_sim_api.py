import asyncio

from app.main import (
    RoboDKStatusRequest,
    SimDetectionRequest,
    TextCommandRequest,
    create_sim_detection,
    robodk_command,
    start_simulation,
    pause_simulation,
    reset_simulation,
    sim_status,
    text_command,
    update_robodk_status,
)
from app.services.stats_service import stats_service


def drain_robodk_commands():
    while robodk_command()["command"] is not None:
        pass


def test_sim_detection_triggers_agv_and_text_command_status():
    stats_service.reset_all()
    drain_robodk_commands()

    assert asyncio.run(start_simulation())["data"]["system_status"] == "RUNNING"

    for index in range(3):
        response = asyncio.run(
            create_sim_detection(
                SimDetectionRequest(part_id=f"part_{index}", color="red", result="defect", source="test")
            )
        )
        assert response["status"] == "ok"

    current = sim_status()
    assert current["defect_bin_load"] == 3
    assert current["agv_status"] in {"MOVING_TO_DEFECT_BIN", "IDLE"}

    command = asyncio.run(text_command(TextCommandRequest(text="defect rate")))
    assert command["intent"] == "QUERY_DEFECT_RATE"
    assert "100.0%" in command["message"]


def test_normal_detection_is_processed_without_defect_dispatch():
    stats_service.reset_all()
    drain_robodk_commands()

    response = asyncio.run(
        create_sim_detection(
            SimDetectionRequest(part_id="normal_001", color="blue", result="normal", source="robodk")
        )
    )

    assert response["status"] == "ok"
    sim = response["sim"]
    assert sim["session_total"] == 1
    assert sim["normal_count"] == 1
    assert sim["session_defects"] == 0
    assert sim["defect_bin_load"] == 0
    assert sim["agv_status"] == "IDLE"


def test_web_control_enqueues_commands_for_robodk_script():
    stats_service.reset_all()
    drain_robodk_commands()

    asyncio.run(start_simulation())
    first = robodk_command()
    second = robodk_command()

    assert first == {"command": "START"}
    assert second == {"command": None}

    asyncio.run(pause_simulation())
    assert robodk_command() == {"command": "PAUSE"}

    asyncio.run(reset_simulation())
    assert robodk_command() == {"command": "RESET"}


def test_robodk_status_and_detection_updates_are_accepted_from_script():
    stats_service.reset_all()
    drain_robodk_commands()

    status_response = asyncio.run(
        update_robodk_status(
            RoboDKStatusRequest(running=True, stage="CONVEYOR", message="moving", red_x=123.4)
        )
    )
    assert status_response["data"]["robodk_status"] == "RUNNING"

    normal_response = asyncio.run(
        create_sim_detection(
            SimDetectionRequest(part_id="robodk_blue_001", color="blue", result="normal", source="robodk")
        )
    )
    assert normal_response["event"]["data"]["normal_count"] == 1

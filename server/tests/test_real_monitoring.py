import asyncio
from types import SimpleNamespace

from app.main import TextCommandRequest, aqis_process, aqis_status, start_aqis, stop_aqis, text_command
from app.services.ros_converters import (
    alarms_to_partial,
    joint_state_to_dobot_partial,
    occupancy_grid_to_event,
)
from app.services.stats_service import stats_service


def pose(x=0.0, y=0.0, z=0.0, w=1.0):
    return SimpleNamespace(
        position=SimpleNamespace(x=x, y=y, z=0.0),
        orientation=SimpleNamespace(x=0.0, y=0.0, z=z, w=w),
    )


def test_occupancy_grid_to_map_event_contains_png_and_metadata():
    msg = SimpleNamespace(
        info=SimpleNamespace(width=2, height=2, resolution=0.05, origin=pose(-1.0, -2.0)),
        data=[-1, 0, 50, 100],
    )

    event = occupancy_grid_to_event(msg)

    assert event["type"] == "map_update"
    assert event["data"]["image"].startswith("data:image/png;base64,")
    assert event["data"]["width"] == 2
    assert event["data"]["height"] == 2
    assert event["data"]["resolution"] == 0.05
    assert event["data"]["origin"]["x"] == -1.0
    assert event["data"]["origin"]["y"] == -2.0


def test_dobot_joint_and_alarm_converters():
    joint_msg = SimpleNamespace(
        name=["magician_joint_1", "magician_joint_2"],
        position=[0.0, 1.57079632679],
        velocity=[],
        effort=[],
    )
    alarms_msg = SimpleNamespace(alarms_list=[1, 12])

    joints = joint_state_to_dobot_partial(joint_msg)
    alarms = alarms_to_partial(alarms_msg)

    assert joints["joints"][0]["position_deg"] == 0.0
    assert joints["joints"][1]["position_deg"] == 90.0
    assert alarms["alarms"] == [1, 12]


def test_aqis_process_endpoints_with_mock_command(monkeypatch):
    state = {"running": False, "pid": None, "returncode": None}

    def fake_status():
        return {**state, "command": "mock", "started_at": None, "stopped_at": None}

    def fake_start():
        state.update({"running": True, "pid": 1234, "returncode": None})
        return {"status": "started", "process": fake_status()}

    def fake_stop(timeout_sec=8.0):
        state.update({"running": False, "pid": 1234, "returncode": 0})
        return {"status": "stopped", "process": fake_status()}

    monkeypatch.setattr(aqis_process, "status", fake_status)
    monkeypatch.setattr(aqis_process, "start", fake_start)
    monkeypatch.setattr(aqis_process, "stop", fake_stop)
    stats_service.reset_all()

    started = asyncio.run(start_aqis())
    assert started["status"] == "started"
    assert started["process"]["running"] is True

    status = aqis_status()
    assert status["process"]["running"] is True

    stopped = asyncio.run(stop_aqis())
    assert stopped["status"] == "stopped"
    assert stopped["process"]["running"] is False


def test_text_command_query_and_emergency_stop():
    stats_service.reset_all()
    stats_service.add_detection(is_defect=True, color="red")

    query = asyncio.run(text_command(TextCommandRequest(text="defect rate")))
    assert query["intent"] == "QUERY_DEFECT_RATE"
    assert "100.0%" in query["message"]

    emergency = asyncio.run(text_command(TextCommandRequest(text="정지")))
    assert emergency["intent"] == "EMERGENCY_STOP"
    assert emergency["action_executed"] is True

import asyncio
from types import SimpleNamespace

import pytest

from app.main import (
    TextCommandRequest,
    aqis_process,
    aqis_status,
    conveyor,
    detection_deduper,
    handle_ros_detection,
    reset_stats,
    start_aqis,
    start_conveyor,
    stop_aqis,
    stop_conveyor,
    text_command,
)
from app.services.detection_deduper import DetectionDeduper
from app.services.ros_converters import (
    alarms_to_partial,
    joint_state_to_dobot_partial,
    occupancy_grid_to_event,
    transform_to_turtlebot_event,
)
from app.services.stats_service import stats_service


@pytest.fixture(autouse=True)
def reset_detection_deduper():
    detection_deduper.reset()
    yield
    detection_deduper.reset()


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


def test_transform_to_turtlebot_event_uses_map_frame_translation():
    msg = SimpleNamespace(
        transform=SimpleNamespace(
            translation=SimpleNamespace(x=1.25, y=-0.5, z=0.0),
            rotation=SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0),
        )
    )

    event = transform_to_turtlebot_event(msg, "tf_map_base_footprint")

    assert event["type"] == "turtlebot_pose"
    assert event["data"]["source"] == "tf_map_base_footprint"
    assert event["data"]["x"] == 1.25
    assert event["data"]["y"] == -0.5
    assert event["data"]["yaw"] == 0.0


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


def test_ros_detection_preserves_realsense_metadata():
    stats_service.reset_all()
    payload = {
        "is_defect": True,
        "defect_class": "red",
        "confidence": 0.91,
        "bbox": [11, 22, 33, 44],
        "center": [27, 44],
        "image_size": [640, 480],
        "source": "realsense_yolo",
        "label": "red",
        "part_id": "real-001",
    }

    events = handle_ros_detection(payload)
    detection_event = next(event for event in events if event["type"] == "detection")
    data = detection_event["data"]
    recent = stats_service.current()["recent_detections"][0]

    assert data["confidence"] == 0.91
    assert data["bbox"] == [11, 22, 33, 44]
    assert data["center"] == [27, 44]
    assert data["image_size"] == [640, 480]
    assert data["source"] == "realsense_yolo"
    assert recent["confidence"] == 0.91
    assert recent["bbox"] == [11, 22, 33, 44]


def test_ros_detection_ignores_empty_or_implicit_payloads():
    stats_service.reset_all()

    assert handle_ros_detection({}) == []
    assert handle_ros_detection({"detections": []}) == []
    assert handle_ros_detection({"detected": False, "source": "realsense_yolo"}) == []
    assert handle_ros_detection({"result": "no_detection"}) == []

    current = stats_service.current()
    assert current["session_total"] == 0
    assert current["session_defects"] == 0
    assert current["normal_count"] == 0


def test_ros_detection_counts_explicit_normal_result():
    stats_service.reset_all()

    events = handle_ros_detection({"result": "normal", "color": "blue", "confidence": 0.87})
    detection_event = next(event for event in events if event["type"] == "detection")
    current = stats_service.current()

    assert detection_event["data"]["is_defect"] is False
    assert current["session_total"] == 1
    assert current["session_defects"] == 0
    assert current["normal_count"] == 1


def test_ros_detection_dedupes_same_tracked_object():
    stats_service.reset_all()
    payload = {
        "track_id": 7,
        "is_defect": True,
        "label": "scratch",
        "bbox": [100, 120, 80, 60],
        "confidence": 0.93,
    }

    assert handle_ros_detection(payload)
    assert handle_ros_detection({**payload, "bbox": [103, 121, 80, 60]}) == []

    current = stats_service.current()
    assert current["session_total"] == 1
    assert current["session_defects"] == 1


def test_ros_detection_dedupes_same_bbox_without_track_id():
    stats_service.reset_all()
    first = {"is_defect": True, "label": "scratch", "bbox": [100, 120, 80, 60], "confidence": 0.93}
    overlap = {"is_defect": True, "label": "scratch", "bbox": [108, 124, 80, 60], "confidence": 0.91}
    separate = {"is_defect": True, "label": "scratch", "bbox": [280, 120, 80, 60], "confidence": 0.94}

    assert handle_ros_detection(first)
    assert handle_ros_detection(overlap) == []
    assert handle_ros_detection(separate)

    current = stats_service.current()
    assert current["session_total"] == 2
    assert current["session_defects"] == 2


def test_ros_detection_counts_multiple_objects_in_batch():
    stats_service.reset_all()
    payload = {
        "source": "realsense_yolo",
        "image_size": [640, 480],
        "detections": [
            {"is_defect": True, "label": "canlid_defective", "bbox": [100, 120, 80, 60], "center": [140, 150]},
            {"is_defect": True, "label": "canlid_defective", "bbox": [300, 120, 80, 60], "center": [340, 150]},
        ],
    }

    events = handle_ros_detection(payload)
    detection_events = [event for event in events if event["type"] == "detection"]
    current = stats_service.current()

    assert len(detection_events) == 2
    assert current["session_total"] == 2
    assert current["session_defects"] == 2


def test_reset_stats_clears_counts_and_dedupe_cache():
    stats_service.reset_all()
    payload = {"is_defect": True, "label": "canlid_defective", "bbox": [100, 120, 80, 60]}

    assert handle_ros_detection(payload)
    assert asyncio.run(reset_stats())["status"] == "ok"
    assert stats_service.current()["session_total"] == 0
    assert handle_ros_detection(payload)
    assert stats_service.current()["session_total"] == 1


def test_detection_deduper_refreshes_duplicate_window():
    now = {"value": 0.0}
    deduper = DetectionDeduper(window_sec=2.0, time_fn=lambda: now["value"])
    payload = {"is_defect": True, "label": "scratch", "bbox": [100, 120, 80, 60]}

    assert deduper.should_accept(payload) is True
    now["value"] = 1.5
    assert deduper.should_accept({**payload, "bbox": [103, 122, 80, 60]}) is False
    now["value"] = 3.0
    assert deduper.should_accept({**payload, "bbox": [105, 123, 80, 60]}) is False
    now["value"] = 5.2
    assert deduper.should_accept({**payload, "bbox": [106, 124, 80, 60]}) is True


def test_detection_deduper_handles_yolo_two_second_cooldown():
    now = {"value": 0.0}
    deduper = DetectionDeduper(window_sec=8.0, time_fn=lambda: now["value"])
    payload = {"is_defect": True, "label": "board panel", "bbox": [440, 520, 90, 85]}

    assert deduper.should_accept(payload) is True
    for seconds, bbox in [
        (2.05, [442, 522, 88, 84]),
        (4.12, [439, 519, 91, 86]),
        (6.2, [444, 521, 87, 84]),
    ]:
        now["value"] = seconds
        assert deduper.should_accept({**payload, "bbox": bbox}) is False


def test_detection_deduper_suppresses_same_label_without_geometry():
    now = {"value": 0.0}
    deduper = DetectionDeduper(window_sec=8.0, time_fn=lambda: now["value"])
    payload = {"is_defect": True, "label": "board panel"}

    assert deduper.should_accept(payload) is True
    now["value"] = 2.1
    assert deduper.should_accept(payload) is False


def test_conveyor_endpoints_report_command_failure(monkeypatch):
    def failed_start():
        return {
            "running": False,
            "mode": "real",
            "sorter_position": "normal",
            "speed": 0.5,
            "last_error": "connection refused",
            "command_ok": False,
        }

    def failed_stop():
        return {
            "running": True,
            "mode": "real",
            "sorter_position": "normal",
            "speed": 0.5,
            "last_error": "timeout",
            "command_ok": False,
        }

    monkeypatch.setattr(conveyor, "start", failed_start)
    monkeypatch.setattr(conveyor, "stop", failed_stop)

    started = asyncio.run(start_conveyor())
    stopped = asyncio.run(stop_conveyor())

    assert started["status"] == "error"
    assert "connection refused" in started["message"]
    assert stopped["status"] == "error"
    assert "timeout" in stopped["message"]

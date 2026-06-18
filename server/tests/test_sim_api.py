from fastapi.testclient import TestClient

from app.main import app
from app.services.stats_service import stats_service


def test_sim_detection_triggers_agv_and_text_command_status():
    stats_service.reset_all()
    client = TestClient(app)

    assert client.post("/api/sim/start").json()["data"]["system_status"] == "RUNNING"

    for index in range(3):
        response = client.post(
            "/api/sim/detection",
            json={"part_id": f"part_{index}", "color": "red", "result": "defect", "source": "test"},
        )
        assert response.status_code == 200

    current = client.get("/api/sim/status").json()
    assert current["defect_bin_load"] == 3
    assert current["agv_status"] in {"MOVING_TO_DEFECT_BIN", "IDLE"}

    command = client.post("/api/text-command", json={"text": "defect rate"}).json()
    assert command["intent"] == "QUERY_DEFECT_RATE"
    assert "100.0%" in command["message"]


def test_normal_detection_is_processed_without_defect_dispatch():
    stats_service.reset_all()
    client = TestClient(app)

    response = client.post(
        "/api/sim/detection",
        json={"part_id": "normal_001", "color": "blue", "result": "normal", "source": "robodk"},
    )

    assert response.status_code == 200
    sim = response.json()["sim"]
    assert sim["session_total"] == 1
    assert sim["normal_count"] == 1
    assert sim["session_defects"] == 0
    assert sim["defect_bin_load"] == 0
    assert sim["agv_status"] == "IDLE"


def test_web_control_enqueues_commands_for_robodk_script():
    stats_service.reset_all()
    client = TestClient(app)

    client.post("/api/sim/start")
    first = client.get("/api/robodk/command").json()
    second = client.get("/api/robodk/command").json()

    assert first == {"command": "START"}
    assert second == {"command": None}

    client.post("/api/sim/pause")
    assert client.get("/api/robodk/command").json() == {"command": "PAUSE"}

    client.post("/api/sim/reset")
    assert client.get("/api/robodk/command").json() == {"command": "RESET"}


def test_robodk_status_and_detection_updates_are_accepted_from_script():
    stats_service.reset_all()
    client = TestClient(app)

    status_response = client.post(
        "/api/robodk/status",
        json={"running": True, "stage": "CONVEYOR", "message": "moving", "red_x": 123.4},
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["robodk_status"] == "RUNNING"

    normal_response = client.post(
        "/api/sim/detection",
        json={"part_id": "robodk_blue_001", "color": "blue", "result": "normal", "source": "robodk"},
    )
    assert normal_response.status_code == 200
    assert normal_response.json()["event"]["data"]["normal_count"] == 1

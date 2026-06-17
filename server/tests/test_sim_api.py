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

    command = client.post("/api/text-command", json={"text": "현재 불량률 알려줘"}).json()
    assert command["intent"] == "QUERY_DEFECT_RATE"
    assert "100.0%" in command["message"]

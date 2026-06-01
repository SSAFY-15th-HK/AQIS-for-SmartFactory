# AQIS Interfaces

## WebSocket Endpoint

```text
ws://localhost:8000/ws
```

## Event Types

- `detection`
- `conveyor_status`
- `mission_update`
- `voice_response`
- `system_status`
- `error`

## Detection Event

```json
{
  "type": "detection",
  "data": {
    "id": 1,
    "timestamp": "2026-06-01T10:00:00Z",
    "color": "red",
    "is_defect": true,
    "confidence": 0.91,
    "bbox": [320, 240, 80, 60],
    "session_total": 12,
    "session_defects": 3,
    "defect_rate": 0.25
  }
}
```

## Conveyor Status Event

```json
{
  "type": "conveyor_status",
  "data": {
    "running": true,
    "mode": "mock",
    "sorter_position": "normal",
    "speed": 0.5
  }
}
```

## Mission Status Event

```json
{
  "type": "mission_update",
  "data": {
    "mission_id": 1,
    "status": "moving",
    "trigger": "count_threshold",
    "current_pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
    "goal_pose": {"x": 3.0, "y": 2.0, "yaw": 0.0}
  }
}
```

Mission status 후보:

```text
idle, queued, moving, arrived, returning, completed, aborted
```

## Voice Response Event

```json
{
  "type": "voice_response",
  "data": {
    "transcript": "지금 불량률 얼마야?",
    "intent": "query_defect_rate",
    "response": "현재 불량률은 25퍼센트입니다."
  }
}
```

## System Status Event

```json
{
  "type": "system_status",
  "data": {
    "server_ok": true,
    "conveyor_ok": true,
    "vision_ok": true,
    "robot_ok": true,
    "voice_ok": true,
    "mode": {
      "conveyor": "mock",
      "vision": "mock",
      "robot": "mock",
      "voice": "text"
    }
  }
}
```

## REST API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | 서버 상태 |
| GET | `/api/stats/current` | 현재 통계 |
| POST | `/api/conveyor/start` | 컨베이어 시작 |
| POST | `/api/conveyor/stop` | 컨베이어 정지 |
| POST | `/api/emergency_stop` | 비상 정지 |
| POST | `/api/mock/detection` | Mock 검출 이벤트 생성 |

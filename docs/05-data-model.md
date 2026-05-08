# 05. 데이터 모델

본 문서는 시스템 내 모든 데이터 인터페이스의 스키마를 정의한다.

- DB 테이블 (영속 저장)
- ROS2 토픽 메시지 (노드 간 통신)
- WebSocket 메시지 (Server ↔ Browser)
- REST API 엔드포인트 (Browser → Server)
- 컨베이어 HTTP 슬레이브 API (Server → 라즈베리파이 5)

## DB 스키마 (SQLite)

### sessions

서버 시작 단위. 서버 켜질 때 row 1개 생성, 종료 시 ended_at 채움(graceful shutdown 시).

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    note TEXT
);
```

### detections

검출 이벤트. 정상/불량 모두 기록. 불량률 계산 raw data.

```sql
CREATE TABLE detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_defect BOOLEAN NOT NULL,
    defect_class TEXT,           -- 'red', 'green', 'blue', 'yellow', null
    confidence REAL,             -- 0.0 ~ 1.0
    bbox_json TEXT               -- '[x, y, w, h]' JSON
);

CREATE INDEX idx_detections_session ON detections(session_id);
CREATE INDEX idx_detections_timestamp ON detections(timestamp);
```

### robot_missions

터틀봇 출동 기록.

```sql
CREATE TABLE robot_missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    trigger TEXT NOT NULL,       -- 'voice', 'count_threshold', 'manual_button'
    status TEXT NOT NULL         -- 'moving', 'arrived', 'returning', 'completed', 'aborted'
);
```

### voice_logs

STT/LLM 대화 기록. 디버깅 + 발표 자료로 가치 있음.

```sql
CREATE TABLE voice_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    transcript TEXT NOT NULL,    -- STT 결과
    intent TEXT,                 -- LLM이 추출한 의도
    response TEXT                -- TTS로 출력한 응답 (있는 경우)
);
```

## ROS2 토픽

### 발행/구독 일람

| 토픽 | 메시지 타입 | 발행자 | 구독자 | 빈도 |
|---|---|---|---|---|
| `/camera/color/image_raw` | sensor_msgs/Image | realsense-ros | Vision Node | 30Hz |
| `/camera/depth/image_rect_raw` | sensor_msgs/Image | realsense-ros | Vision Node | 30Hz |
| `/defect/detection` | std_msgs/String (JSON) | Vision Node | Server | 검출 시마다 |
| `/conveyor/status` | std_msgs/String (JSON) | Server | UI 표시용 | 상태 변화 시 |
| `/scan` | sensor_msgs/LaserScan | turtlebot3 | Nav2 | 5Hz |
| `/odom` | nav_msgs/Odometry | turtlebot3 | Nav2 | 30Hz |
| `/cmd_vel` | geometry_msgs/Twist | Nav2 | turtlebot3 | 10Hz |
| `/amcl_pose` | geometry_msgs/PoseWithCovarianceStamped | Nav2 | Server | 5Hz |
| `/turtlebot/mission_status` | std_msgs/String (JSON) | Server | UI 표시용 | 상태 변화 시 |

### 토픽 페이로드 예시

**`/defect/detection`**

```json
{
  "frame_id": 1234,
  "timestamp": 1731000000.123,
  "is_defect": true,
  "defect_class": "red",
  "confidence": 0.87,
  "bbox": [320, 240, 80, 60],
  "image_size": [640, 480]
}
```

**`/conveyor/status`**

```json
{
  "running": true,
  "speed": 0.5,
  "sorter_position": "defect"
}
```

**`/turtlebot/mission_status`**

```json
{
  "mission_id": 7,
  "status": "moving",
  "trigger": "voice",
  "current_pose": {"x": 1.2, "y": 0.8, "yaw": 1.57},
  "goal_pose": {"x": 3.0, "y": 2.0}
}
```

## WebSocket 메시지 (Server ↔ Browser)

`ws://localhost:8000/ws` 엔드포인트. Server → Browser 단방향이 대부분, Browser → Server는 ping/pong과 STOP만.

### Server → Browser 메시지

모든 메시지는 `type` 필드로 구분.

**`detection`** — 검출 이벤트

```json
{
  "type": "detection",
  "data": {
    "is_defect": true,
    "defect_class": "red",
    "timestamp": "2024-11-08T10:23:45Z",
    "session_total": 234,
    "session_defects": 28,
    "defect_rate": 0.1197
  }
}
```

**`mission_update`** — 터틀봇 미션 상태 변화

```json
{
  "type": "mission_update",
  "data": {
    "mission_id": 7,
    "status": "moving",
    "current_pose": {"x": 1.2, "y": 0.8}
  }
}
```

**`conveyor_status`** — 컨베이어 상태

```json
{
  "type": "conveyor_status",
  "data": {"running": true}
}
```

**`voice_response`** — TTS로 음성 출력 + UI에도 표시

```json
{
  "type": "voice_response",
  "data": {
    "transcript": "지금 불량률 얼마야",
    "response": "현재 세션에서 234개 중 28개가 불량입니다. 불량률은 12퍼센트예요."
  }
}
```

**`error`** — 시스템 오류 알림

```json
{
  "type": "error",
  "data": {"code": "TURTLEBOT_DISCONNECTED", "message": "터틀봇 응답 없음"}
}
```

### Browser → Server 메시지

**`ping`** — 연결 유지 (필요 시)

```json
{"type": "ping"}
```

**`emergency_stop`** — STOP 버튼 (REST로 보내도 무방)

```json
{"type": "emergency_stop"}
```

## REST API (Browser → Server)

기본 경로 `/api`.

| 메서드 | 경로 | 용도 | 요청 본문 | 응답 |
|---|---|---|---|---|
| POST | `/api/conveyor/start` | 컨베이어 시작 | `{}` | `{"status": "ok"}` |
| POST | `/api/conveyor/stop` | 컨베이어 정지 | `{}` | `{"status": "ok"}` |
| POST | `/api/emergency_stop` | 즉시 정지 (LLM 우회) | `{}` | `{"status": "stopped"}` |
| POST | `/api/voice/upload` | 음성 파일 업로드 | multipart/form-data | `{"transcript": "...", "response": "..."}` |
| GET | `/api/stats/current` | 현재 세션 통계 | — | 통계 JSON |
| GET | `/api/sessions` | 세션 목록 | — | 세션 배열 |
| GET | `/api/sessions/{id}/detections` | 특정 세션의 검출 이력 | — | detections 배열 |
| GET | `/api/missions` | 미션 이력 | — | missions 배열 |

### 응답 예시

**`GET /api/stats/current`**

```json
{
  "session_id": 12,
  "total": 234,
  "defects": 28,
  "defect_rate": 0.1197,
  "robot_pose": {"x": 0.0, "y": 0.0},
  "robot_status": "idle",
  "conveyor_running": true,
  "box_count": 3
}
```

## 컨베이어 HTTP 슬레이브 API

라즈베리파이 5의 Flask 서버. 노트북 Server에서 호출.

기본 경로 `http://<rpi-ip>:5000`.

| 메서드 | 경로 | 용도 |
|---|---|---|
| POST | `/conveyor/start` | 스테퍼 모터 회전 시작 |
| POST | `/conveyor/stop` | 스테퍼 모터 정지 |
| POST | `/sort/normal` | 서보를 정상 갈래 위치로 |
| POST | `/sort/defect` | 서보를 불량 갈래 위치로 |
| POST | `/emergency_stop` | 모든 모터 즉시 정지 |
| GET | `/status` | 현재 상태 조회 (running, sorter_position 등) |

응답은 일관되게 `{"status": "ok"}` 또는 오류 시 `{"status": "error", "message": "..."}`.

## LLM 호출 인터페이스

llama.cpp의 OpenAI 호환 API 사용. Server가 내부적으로 호출.

### 의도 추출 프롬프트 (시스템)

```
You are an intent classifier for a smart factory voice control system.

Given user utterance in Korean, output ONLY a JSON object with these fields:
- intent: one of [start_conveyor, stop_conveyor, go_to_unload, return_home,
                  emergency_stop, query_defect_rate, query_total_count,
                  query_robot_location, query_box_count, query_status, unknown]
- urgency: one of [normal, high]
- params: object with extracted parameters (or empty)

Output strict JSON, no other text.
```

### 응답 생성 프롬프트 (시스템)

```
You are a voice assistant for a smart factory system. Given the current state
and a user question in Korean, generate a brief natural Korean response in
1-2 sentences. Use polite formal speech (-요/-습니다).

Current state will be provided as JSON. Respond about the current session
unless the user explicitly asks about all-time data.
```

## 데이터 흐름 시퀀스

### 검출 → 분류 → DB → UI

```
Vision Node (검출)
  → publish /defect/detection
  → Server 구독 콜백
    → INSERT into detections
    → POST http://rpi:5000/sort/{normal|defect}
    → WebSocket broadcast { type: "detection", ... }
  → UI 차트 갱신
```

### 음성 명령 → 미션

```
Browser 마이크 녹음
  → POST /api/voice/upload
  → Whisper STT
  → 안전 키워드 매칭 ("정지" 등) → 매칭 시 즉시 emergency_stop 후 종료
  → LLM 의도 추출
  → 의도 = "go_to_unload"
    → INSERT into voice_logs
    → INSERT into robot_missions (status='moving', trigger='voice')
    → Nav2 send_goal(dropoff_pose)
    → WebSocket broadcast { type: "mission_update" }
  → LLM 응답 생성 ("터틀봇이 적재장으로 출발합니다")
  → pyttsx3 TTS 또는 WebSocket으로 텍스트 푸시
```

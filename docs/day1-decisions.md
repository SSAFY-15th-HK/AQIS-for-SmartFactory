# Day 1 Decisions

## 1. Mock-first 개발 전략

하드웨어를 마지막 3일만 사용할 수 있으므로, 앞 3주는 Mock adapter 기반으로 전체 시스템을 완성한다.

## 2. Adapter 전환 방식

`.env`의 mode 값으로 Mock/Real 구현체를 전환한다.

```env
CONVEYOR_MODE=mock
VISION_MODE=mock
ROBOT_MODE=mock
VOICE_MODE=text
```

## 3. Day 1 통합 목표

DB/ROS2/실제 하드웨어 없이 메모리 상태만으로 다음 흐름을 먼저 검증한다.

```text
UI Button → REST API → Server Event → WebSocket → UI State Update
```

## 4. Day 2 확장 후보

- SQLite 저장 추가
- Mock conveyor loop 추가
- defect threshold 기반 mock robot mission 추가
- sample video 기반 OpenCV 검출 추가

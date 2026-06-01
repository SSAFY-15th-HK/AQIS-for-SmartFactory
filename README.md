# AQIS for SmartFactory

스마트 팩토리 자동화 시스템 — 컨베이어 비전 검출 + 모바일 로봇 운반 + 음성 인터페이스

## Development Strategy

본 프로젝트는 초기 3주 동안 실제 하드웨어 없이 개발한다. 따라서 모든 외부 장치는 Adapter 인터페이스를 통해 추상화하고, 기본 개발 모드는 Mock이다.

```env
CONVEYOR_MODE=mock
VISION_MODE=mock
ROBOT_MODE=mock
VOICE_MODE=text
```

마지막 3일 동안 실제 하드웨어를 사용할 수 있을 때, 각 Adapter를 real 모드로 전환하여 통합한다.

```env
CONVEYOR_MODE=real
VISION_MODE=realsense
ROBOT_MODE=ros2
VOICE_MODE=whisper
```

## Day 1 Goal

Day 1의 목표는 하드웨어 없이도 개발 가능한 최소 관통 흐름을 만드는 것이다.

```text
[Mock Detection 버튼]
→ FastAPI 서버 이벤트 생성
→ WebSocket broadcast
→ UI에 검사 수/불량 수/불량률 표시
```

## Structure

```text
server/          FastAPI + WebSocket mock backend
web/             Vite React TypeScript dashboard
docs/            인터페이스/결정 문서
sample-data/     추후 샘플 영상/이미지 저장 위치
```

## Quick Start

### 1. Server

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

확인:

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/mock/detection
```

### 2. Web

```bash
cd web
npm install
npm run dev -- --host 0.0.0.0
```

브라우저:

```text
http://localhost:5173
```

## Day 1 Done Criteria

- [ ] FastAPI 서버 실행
- [ ] `/api/health` 응답
- [ ] WebSocket `/ws` 연결
- [ ] UI 실행
- [ ] UI에서 WebSocket connected 표시
- [ ] Mock Detection 버튼 클릭 시 UI에 detection 표시
- [ ] 총 검사 수 / 불량 수 / 불량률 표시

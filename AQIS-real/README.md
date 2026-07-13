# AQIS Real Workspace

실제 장비용 RealOps Dashboard, 컨베이어 제어 서버, Dobot 실행 스크립트를 모은 workspace입니다. 전체 시스템 실행 순서는 [실제 장비 시작 가이드](../docs/real-hardware-startup.md)를 기준으로 합니다.

## 구조

```text
AQIS-real/
  web/                          # React/Vite RealOps Dashboard
    src/App.tsx                 # 공정 관제와 제어 UI
    src/DobotUrdfView.tsx       # Three.js 기반 Dobot URDF 렌더링
    public/dobot/               # Dobot URDF와 mesh
  conveyor/
    conveyor_http_server.py     # Raspberry Pi 컨베이어 HTTP bridge
  scripts/
    dobot_pick_place_once.py    # 단일 Pick & Place 실행
    monitoring_session.sh       # 모니터링 세션 보조 스크립트
```

## RealOps Dashboard

대시보드는 FastAPI REST API와 WebSocket, MJPEG stream을 통해 다음 상태를 표시합니다.

- 검사 수, 정상·불량 수와 최근 detection
- RealSense·TurtleBot 카메라 영상
- TurtleBot odom/AMCL 위치와 map
- Dobot joint, TCP pose, gripper/alarm 상태와 3D 모델
- 컨베이어·시뮬레이션·실제 장비 상태
- Start, Stop, E-Stop과 LLM 텍스트 명령 로그

```bash
cd AQIS-real/web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 컨베이어 서버

Raspberry Pi에서 실행하며 FastAPI의 장비 명령을 컨베이어 제어로 전달합니다. 장비 핀과 네트워크 설정은 환경에 맞게 확인하세요.

```bash
cd AQIS-real/conveyor
python3 conveyor_http_server.py
```

## Dobot

`scripts/dobot_pick_place_once.py`는 환경 변수로 전달된 pick/place 좌표를 사용해 한 번의 흡착 작업을 수행합니다. 실제 실행 전 좌표계와 안전 범위를 반드시 보정하세요.

서버의 전체 자동화 흐름은 다음과 같습니다.

```text
defect event → conveyor stop → latest camera point
→ camera-to-Dobot coordinate transform → pick-and-place → conveyor resume
```

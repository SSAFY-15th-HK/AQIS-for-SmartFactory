# AQIS Simulation Workspace

RoboDK 디지털 트윈과 Simulation Dashboard를 모은 workspace입니다. 실제 장비가 준비되기 전에 동일한 FastAPI 백엔드와 이벤트 모델을 공유하는 simulation 경로로 공정 흐름을 개발·검증하기 위해 사용했습니다.

## 구조

```text
AQIS-sim/
  robodk/
    AQIS.rdk                    # RoboDK station
    Main.py                     # FastAPI와 통신하는 simulation script
    robot/                      # UR5, TurtleBot3 Waffle
    tool/                       # OnRobot VG10 vacuum gripper
    conv/                       # 2m conveyor
    object/                     # can, normal/abnormal can lid, factory objects
    box/                        # normal/defect bins
    visual_assets/              # 공장·안전·경로 시각 자산
  web/                          # React/Vite Simulation Dashboard
```

## RoboDK 실행

1. 루트의 FastAPI 서버를 실행합니다.
2. RoboDK에서 `robodk/AQIS.rdk`를 엽니다.
3. `robodk/Main.py`를 실행합니다.

기본 서버 주소:

```text
http://localhost:8000
```

RoboDK station에는 다음 주요 자산이 포함됩니다.

- `robot/UR5.robot`: Pick & Place robot arm
- `tool/OnRobot-VG10-Vacuum-Gripper.tool`: Vacuum gripper
- `conv/Conveyor-Belt-2m.robot`: Conveyor
- `robot/turtlebot3_waffle.step`: Mobile robot visual model
- `object/can.step`: Can body
- `object/canlid_normal.step`, `object/canlid_abnormal.step`: Inspection parts
- `box/Bin-Blue.sld`, `box/Bin-Red.sld`: Normal/defect bins

## Simulation Dashboard

```bash
cd AQIS-sim/web
npm install
npm run dev -- --host 0.0.0.0
```

Simulation Dashboard는 공정 상태를 이해하고 서버 이벤트 흐름을 검증하기 위한 모니터링 UI입니다. RoboDK 프레임과 픽셀 단위로 동기화되는 렌더러는 아닙니다.

## Mock-first 역할

```text
mock device events → FastAPI → WebSocket → Simulation Dashboard
                           ↓
                     RoboDK process
```

시뮬레이션과 실제 장비 경로가 같은 이벤트 모델을 사용하도록 구성해, 하드웨어 없이도 UI·API·공정 상태 전이를 먼저 검증할 수 있습니다.

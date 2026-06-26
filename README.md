# AQIS for SmartFactory

AQIS는 컨베이어 위의 캔 뚜껑을 RealSense + YOLO로 검사하고, 불량품을 Dobot Magician으로 Pick & Place 하는 스마트팩토리 실시간 모니터링 프로젝트입니다. TurtleBot3, Dobot, RealSense, 컨베이어, FastAPI, React 대시보드를 하나의 시스템으로 연결합니다.

영문 문서는 [README.en.md](./README.en.md)를 참고하세요.

## 현재 시스템 구성

```text
AQIS-for-SmartFactory/
  aqis_ws/src/integrate_prac/  # AQIS 소유 ROS2 패키지: RealSense YOLO, ROI, Dobot 연동 노드
  AQIS-real/                   # 실제 장비용 웹 UI, 컨베이어 서버, Dobot 실행 스크립트
  AQIS-sim/                    # RoboDK 기반 시뮬레이션
  server/                      # FastAPI + ROS2 bridge + WebSocket + LLM proxy
  maps/                        # Nav2/SLAM 지도
  config/nav2/                 # Nav2/AMCL 파라미터
  docs/                        # 상세 문서
  ros2.repos                   # 외부 ROS 소스 의존성 목록
```

## Git에 포함하는 것과 포함하지 않는 것

포함합니다:

- AQIS가 직접 작성한 ROS2 패키지: `aqis_ws/src/integrate_prac`
- FastAPI 서버: `server`
- 실제 장비 대시보드: `AQIS-real/web`
- 시뮬레이션: `AQIS-sim`
- 지도/파라미터/모델: `maps`, `config`, `aqis_ws/src/integrate_prac/models/best.pt`
- 실행 문서와 예시 환경 파일

포함하지 않습니다:

- `build/`, `install/`, `log/`
- `.env`, API key, LLM token
- `.venv`, `node_modules`, `dist`
- ROS bag, 녹화 영상, DB 파일
- TurtleBot3, Dobot, RealSense 드라이버 같은 외부 패키지의 빌드 결과

## 외부 ROS 패키지

AQIS가 사용한 외부 ROS 패키지는 Git에 빌드 결과를 넣지 않고, `ros2.repos`와 문서로 재현합니다.

| 용도 | 저장소 | 권장 방식 |
|---|---|---|
| Dobot Magician | `https://github.com/jkaniuka/magician_ros2.git` | source build |
| RealSense ROS wrapper | `https://github.com/realsenseai/realsense-ros.git` | apt 또는 source build |
| TurtleBot3 | `https://github.com/ROBOTIS-GIT/turtlebot3.git` | TurtleBot 공식 workspace 또는 source build |

외부 소스를 한 번에 받을 때:

```bash
mkdir -p ~/aqis_external_ws/src
cd ~/aqis_external_ws
vcs import src < "$AQIS_ROOT/ros2.repos"
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

새 터미널에서는 필요에 따라 다음을 source 합니다.

```bash
source ~/aqis_external_ws/install/setup.bash
```

## 빠른 설치

Ubuntu 22.04 + ROS2 Humble 기준입니다.

```bash
git clone https://github.com/SSAFY-15th-HK/AQIS-for-SmartFactory.git
cd AQIS-for-SmartFactory
export AQIS_ROOT="$(pwd)"
./scripts/setup_dev.sh
```

설치 후 새 터미널마다:

```bash
source /opt/ros/humble/setup.bash
source "$AQIS_ROOT/aqis_ws/install/setup.bash"
export ROS_DOMAIN_ID=33
export AQIS_YOLOV5_REPO=~/yolov5
```

서버 환경 파일:

```bash
cd "$AQIS_ROOT/server"
cp .env.example .env
```

실제 장비 IP, LLM URL/token, Dobot 좌표는 `server/.env`에서 장비 환경에 맞게 수정합니다.

## 실제 장비 실행 순서

자세한 명령은 [docs/real-hardware-startup.md](./docs/real-hardware-startup.md)를 기준으로 실행합니다.

요약:

1. TurtleBot3에서 `robot.launch.py` 실행
2. 노트북에서 Nav2 또는 SLAM 실행
3. 노트북에서 Dobot bringup 실행
4. 노트북에서 RealSense YOLO 실행
5. 라즈베리파이에서 컨베이어 HTTP 서버 실행
6. 노트북에서 FastAPI 서버 실행
7. 노트북에서 React 대시보드 실행

## 핵심 명령

RealSense YOLO:

```bash
ros2 launch integrate_prac realsense_yolo.launch.py \
  confidence:=0.7 \
  roi_width:=220 \
  roi_height:=180
```

FastAPI:

```bash
cd "$AQIS_ROOT/server"
source /opt/ros/humble/setup.bash
source ../aqis_ws/install/setup.bash
.venv-ros/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Real dashboard:

```bash
cd "$AQIS_ROOT/AQIS-real/web"
npm run dev -- --host 0.0.0.0 --port 5173
```

## 주요 토픽

| 토픽 | 용도 |
|---|---|
| `/detection_image` | 웹에 표시할 YOLO annotated MJPEG 이미지 |
| `/defect/detection` | FastAPI가 받는 검사 결과 JSON |
| `/dobot_joint_states` | Dobot 관절 상태 |
| `/dobot_pose_raw` | Dobot TCP/raw pose |
| `/odom`, `/amcl_pose` | TurtleBot 위치 |
| `/map` | SLAM/Nav2 지도 |

## 문서

- [실제 장비 시작 가이드](./docs/real-hardware-startup.md)
- [문서 인덱스](./docs/README.md)
- [시뮬레이션 README](./AQIS-sim/README.md)
- [실제 장비 README](./AQIS-real/README.md)

## 개발 원칙

- AQIS 소유 코드는 이 저장소에 둡니다.
- 외부 ROS 패키지는 apt 또는 `ros2.repos`로 재현합니다.
- `server/.env`에는 비밀값을 넣되 Git에는 올리지 않습니다.
- 하드웨어 좌표/지도/모델이 바뀌면 README 또는 `docs/real-hardware-startup.md`를 같이 갱신합니다.

# 04. 기술 스택

## 운영 체제

| 머신 | OS |
|---|---|
| 노트북 | Ubuntu 22.04 LTS |
| 컨베이어 라즈베리파이 5 | Raspberry Pi OS 64-bit (Bookworm) |
| 터틀봇3 와플 | Ubuntu 22.04 또는 ROS2 Humble 호환 OS |

## ROS2

- **배포판**: ROS2 Humble Hawksbill
- **DDS**: 기본 (rmw_fastrtps_cpp). 다중 머신 통신 불안정 시 CycloneDDS로 통일
- **빌드 도구**: colcon
- **패키지**:
  - `realsense-ros` (카메라 노드)
  - `turtlebot3` (`turtlebot3_bringup`, `turtlebot3_navigation2` 등)
  - `nav2_*` (Navigation2 스택)
  - `slam_toolbox`
  - `rqt_image_view`, `rviz2` (디버깅용)

## 백엔드 (노트북)

- **언어**: Python 3.10
- **ROS2 클라이언트**: `rclpy`
- **웹 프레임워크**: FastAPI 0.110+
- **ASGI 서버**: uvicorn
- **WebSocket**: FastAPI 내장 지원
- **DB**:
  - SQLite (단일 파일, 별도 서버 불필요)
  - SQLAlchemy 2.0+ (ORM)
  - Alembic (마이그레이션)
- **비전**: OpenCV 4.x, NumPy
- **MJPEG 스트리밍**: Flask 또는 FastAPI 자체 StreamingResponse
- **STT**: faster-whisper (또는 openai-whisper)
- **TTS**: pyttsx3 (오프라인) — 음질 부족 시 클라우드 TTS API로 교체 검토
- **LLM 클라이언트**: requests로 llama.cpp HTTP API 호출

## 프론트엔드 (Browser)

- **프레임워크**: React 18 (TypeScript) — 두 분 익숙도에 따라 Vue로 변경 가능
- **빌드 도구**: Vite
- **차트**: Recharts 또는 Chart.js
- **WebSocket 클라이언트**: 브라우저 내장 `WebSocket`
- **영상 표시**: `<img src="http://laptop:8080/stream">` (MJPEG)
- **스타일링**: Tailwind CSS (선택, 작업 빠름)

## 컨베이어 라즈베리파이 5

- **언어**: Python 3.11
- **GPIO**: `gpiozero` (라즈베리파이 5 호환, lgpio 백엔드 자동)
- **HTTP 서버**: Flask 3.x (단순 슬레이브용으로 충분)
- **systemd**: 부팅 시 자동 시작 서비스 등록

## LLM 서버 (집 데스크톱)

- **모델 런타임**: llama.cpp (서버 모드 `llama-server`)
- **모델**: Llama 3.1 8B Instruct 또는 Qwen 2.5 7B Instruct (4-bit GGUF)
  - 응답 속도와 한국어 의도 추출 정확도 균형 고려
- **터널**: Tailscale (집 ↔ 노트북)
- **호출 방식**: OpenAI 호환 REST API (llama-server 기본 제공)

## 4차 (Dobot)

- **SDK**: 보유 모델에 따라 결정 (Magician Lite, MG400 등)
- ROS2 패키지 없는 모델이면 SDK를 wrapping한 자체 ROS2 노드 작성

## 개발 도구

- **버전 관리**: Git + GitHub (private repo)
- **에디터**: VS Code (또는 Cursor) — 두 분 합의 필수 (포맷터 통일 위해)
- **포맷터/린터**:
  - Python: `ruff` (린트 + 포맷)
  - TypeScript: `prettier` + `eslint`
- **AI 코딩 도우미**: Claude / Cursor / Copilot 활용

## 패키지 매니저

- Python: `uv` 또는 `pip` + `requirements.txt`
- Node: `pnpm` 권장 (빠르고 디스크 절약)

## 환경 변수 / 설정 파일

각 머신에 `.env` 파일을 두고 비공개 값 관리. Git에는 `.env.example` 만 commit.

```
ROS_DOMAIN_ID=42
SERVER_HOST=192.168.x.x
SERVER_PORT=8000
MJPEG_PORT=8080
DB_PATH=./data/factory.db
LLM_BASE_URL=http://100.x.x.x:8080  # Tailscale IP
LLM_MODEL=llama-3.1-8b-instruct-q4
WHISPER_MODEL=base
TURTLEBOT_NAMESPACE=turtlebot3
HOME_POSE_X=0.0
HOME_POSE_Y=0.0
DROPOFF_POSE_X=3.0
DROPOFF_POSE_Y=2.0
DEFECT_COUNT_THRESHOLD=5
```

## 의존성 고정

운영 안정성을 위해 주요 라이브러리는 정확한 버전을 명시한다.

- 노트북 Python: `requirements.txt` (`uv pip compile`로 lockfile 생성)
- 라즈베리파이: 같은 방식
- 프론트엔드: `pnpm-lock.yaml`

## 도커 사용 여부

본 프로젝트에서는 **사용하지 않는다**. 이유:

- ROS2 + USB 카메라 + GPIO + Wi-Fi 멀티캐스트 모두 도커에선 추가 설정 부담
- 학습 프로젝트 4주 일정에서 도커 디버깅 비용이 큼
- 노트북은 단일 사용 환경이라 시스템 직접 설치로 충분

향후 발전 시 docker-compose로 Server + DB만 컨테이너화하는 것은 검토 가능.

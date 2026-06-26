# AQIS 문서 인덱스

이 디렉터리는 AQIS 프로젝트의 상세 문서를 모읍니다. 현재 기준 문서는 실제 장비 흐름입니다.

## 먼저 읽을 문서

| 문서 | 내용 |
|---|---|
| [../README.md](../README.md) | 한국어 메인 README, 설치/실행 요약 |
| [../README.en.md](../README.en.md) | English README |
| [real-hardware-startup.md](./real-hardware-startup.md) | 실제 장비 시작 순서와 터미널별 명령 |

## 현재 코드 구조

| 경로 | 내용 |
|---|---|
| `aqis_ws/src/integrate_prac` | AQIS 소유 ROS2 패키지. RealSense YOLO, ROI, Detection topic, Dobot 보조 노드 |
| `server` | FastAPI backend, ROS2 bridge, WebSocket, LLM proxy, process control |
| `AQIS-real` | 실제 장비 웹 UI, 컨베이어 HTTP 서버, Dobot pick/place 스크립트 |
| `AQIS-sim` | RoboDK 시뮬레이션 |
| `maps` | Nav2/SLAM 지도 |
| `config/nav2` | Nav2/AMCL 파라미터 |

## 설계/기획 문서

아래 문서는 프로젝트 초기 기획과 시뮬레이션 단계의 맥락을 포함합니다. 현재 실제 장비 흐름과 다른 내용이 있으면 `README.md`와 `real-hardware-startup.md`를 우선합니다.

| # | 문서 | 내용 |
|---|---|---|
| 01 | [01-overview.md](./01-overview.md) | 초기 프로젝트 개요와 단계별 목표 |
| 02 | [02-architecture.md](./02-architecture.md) | 통신 구조와 데이터 흐름 |
| 03 | [03-hardware.md](./03-hardware.md) | 하드웨어 목록 |
| 04 | [04-tech-stack.md](./04-tech-stack.md) | 기술 스택과 환경 변수 |
| 05 | [05-data-model.md](./05-data-model.md) | DB/ROS/WebSocket 데이터 모델 |
| 06 | [06-stages.md](./06-stages.md) | 단계별 개발 계획 |
| 07 | [07-roles-and-schedule.md](./07-roles-and-schedule.md) | 역할과 일정 |
| 08 | [08-stt-llm-tts.md](./08-stt-llm-tts.md) | LLM/음성 인터페이스 계획 |
| 09 | [09-demo-scenario.md](./09-demo-scenario.md) | 데모 시나리오 |
| 10 | [10-risks.md](./10-risks.md) | 리스크와 검증 항목 |
| 11 | [11-interfaces.md](./11-interfaces.md) | 인터페이스 합의서 |

## 문서 갱신 원칙

- 실제 장비 실행 방법이 바뀌면 `real-hardware-startup.md`를 먼저 갱신합니다.
- 클론 후 재현에 필요한 파일은 repo 안으로 옮기고, 외부 의존성은 README에 명시합니다.
- 비밀값은 `server/.env`에만 두고 Git에는 올리지 않습니다.

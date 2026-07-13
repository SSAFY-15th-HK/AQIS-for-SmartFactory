# AQIS 문서 인덱스

이 디렉터리에는 **현재 실행 기준 문서**와 **2026-05-08에 작성된 초기 기획 문서**가 함께 있습니다. 구현 상태를 확인할 때는 아래 우선순위를 따릅니다.

## 현재 구현의 기준 문서

| 우선순위 | 문서 | 용도 |
|---|---|---|
| 1 | [../README.md](../README.md) | 프로젝트 범위, 구현 기능, 검증 범위, 설치 요약 |
| 2 | [real-hardware-startup.md](./real-hardware-startup.md) | 실제 장비 실행 순서와 환경 변수 |
| 3 | [../AQIS-real/README.md](../AQIS-real/README.md) | 실제 장비 UI·컨베이어·Dobot 구성 |
| 4 | [../AQIS-sim/README.md](../AQIS-sim/README.md) | RoboDK 디지털 트윈과 Simulation UI |
| 5 | [07-roles-and-schedule.md](./07-roles-and-schedule.md) | 실제 팀 구성, 기여, 일정과 계획 대비 결과 |
| 6 | [interfaces.md](./interfaces.md) | 현재 서버·장비 인터페이스 메모 |

## 현재 코드 구조

| 경로 | 내용 |
|---|---|
| `aqis_ws/src/integrate_prac` | RealSense YOLO, ROI, depth 3D point, detection ROS2 node |
| `server` | FastAPI, ROS2 bridge, WebSocket, LLM proxy, 공정 제어 |
| `AQIS-real` | RealOps UI, 컨베이어 HTTP 서버, Dobot 실행 스크립트 |
| `AQIS-sim` | RoboDK 디지털 트윈과 Simulation Dashboard |
| `maps` | Nav2/SLAM 지도 |
| `config/nav2` | Nav2/AMCL 파라미터 |

## 초기 기획 문서

> [!IMPORTANT]
> 아래 문서는 초기 계획과 설계 의사결정을 보존한 자료입니다. 완료 명세가 아니며, HSV 검출·SQLite·STT/TTS·TurtleBot 자동 출동 등 현재 코드와 다른 내용이 포함되어 있습니다. 체크박스와 목표 수치를 최종 성과로 해석하지 마세요. `07-roles-and-schedule.md`는 최종 발표와 Git 이력에 맞춰 별도로 갱신했습니다.

| # | 문서 | 초기 기획 내용 |
|---|---|---|
| 01 | [01-overview.md](./01-overview.md) | 프로젝트 개요와 단계별 목표 |
| 02 | [02-architecture.md](./02-architecture.md) | 통신 구조와 데이터 흐름 |
| 03 | [03-hardware.md](./03-hardware.md) | 하드웨어 목록 |
| 04 | [04-tech-stack.md](./04-tech-stack.md) | 기술 스택과 환경 계획 |
| 05 | [05-data-model.md](./05-data-model.md) | DB/ROS/WebSocket 데이터 모델 계획 |
| 06 | [06-stages.md](./06-stages.md) | 단계별 개발 계획과 목표 수치 |
| 08 | [08-stt-llm-tts.md](./08-stt-llm-tts.md) | LLM·음성 인터페이스 계획 |
| 09 | [09-demo-scenario.md](./09-demo-scenario.md) | 초기 데모 시나리오 |
| 10 | [10-risks.md](./10-risks.md) | 리스크와 검증 항목 |
| 11 | [11-interfaces.md](./11-interfaces.md) | 초기 인터페이스 합의안 |

## 문서 갱신 원칙

- 실제 장비 실행 방법이 바뀌면 `real-hardware-startup.md`를 먼저 갱신합니다.
- 구현 범위가 바뀌면 루트 `README.md`의 완료·검증 범위를 함께 갱신합니다.
- 초기 기획 문서는 역사 자료로 보존하되, 현재 구현처럼 표현하지 않습니다.
- 외부 패키지는 `ros2.repos` 또는 설치 문서로 재현하고 빌드 결과를 커밋하지 않습니다.
- 비밀값은 `server/.env`에만 저장하고 Git에는 올리지 않습니다.

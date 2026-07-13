# 07. 팀 구성, 실제 기여 및 일정

이 문서는 초기 `개발자 A/B` 분업 계획을 최종 발표 자료와 Git 이력에 맞춰 갱신한 기록입니다.

## 프로젝트 개요

- 팀: SSAFY 15기 광주 4반 3조
- 인원: 2명
- 초기 기획: 2026-05-08
- 본 개발 및 최종 정리: 2026-06-01–2026-06-26, 약 4주
- 초기 계획 투입량: 1인당 하루 3–4시간, 약 196 man-hours

## 팀원별 실제 기여

### [공세민](https://github.com/SeMinKong) — 팀장

**Full-stack / Robot Integration**

- RealOps Dashboard 구성
  - 공정 상태 카드, 검사·불량 통계, 이벤트 로그
  - Start, Stop, E-Stop 제어 UI
  - RealSense·TurtleBot 영상, 맵, Dobot 3D·joint·TCP 상태
- FastAPI 서버 구조와 REST API·WebSocket 이벤트 처리
- ROS2 bridge와 서버–프론트 이벤트 흐름
- Raspberry Pi 컨베이어 HTTP 서버 연동
- 불량 검출 이후 Dobot Pick & Place와 공정 재개 흐름 구현·시연
- LLM 서버 연동, 의도 분류, 장애 시 키워드 fallback
- 실제 장비 실행 문서와 저장소 재구성

### [현은빈](https://github.com/eunbin-hyun) — 팀원

**Simulation / AI / 3D**

- Mock 데이터 기반 Simulation Dashboard 선개발
- RoboDK 디지털 트윈 공정 구성
  - UR5, 진공 그리퍼, 컨베이어, TurtleBot, 분류함
  - 검사→Pick & Place→운반 시나리오
- RoboDK 공정 스크립트와 3D 시각 자산
- Onshape 기반 부품 설계와 3D 프린팅
- Roboflow 학습 데이터 생성·라벨링
- YOLO 모델 학습과 캔 뚜껑 정상·불량 자산 제작
- 시뮬레이션·실제 장비 시연 자료 제작

> Onshape·Roboflow·YOLO 학습 역할은 최종 발표자료의 팀원 소개를 근거로 합니다. 외부 학습 산출물이 한 계정으로 커밋됐더라도 이를 실제 담당자 기록으로 단정하지 않습니다.

### 공동 작업

- ROS2–FastAPI–React–장비 통합 테스트
- 실제 장비와 디지털 트윈 인터페이스 조율
- 데모 시나리오, 영상 촬영, 최종 발표 자료
- 초기 계획 대비 구현 범위 조정과 문서화

## 진행 흐름

| 시기 | 내용 |
|---|---|
| 2026-05-08 | 스마트팩토리 통합 공정 초기 기획과 인터페이스 설계 |
| 2026-06 초 | Mock-first 서버·웹 구조와 YOLO/ROS2 기반 구현 시작 |
| 2026-06 중 | RoboDK 디지털 트윈, RealOps UI, 실제 장비 연동 확장 |
| 2026-06 말 | YOLO→컨베이어 정지→Dobot Pick & Place 통합, SLAM 시연, 발표·문서 정리 |

## 계획 대비 최종 범위

| 영역 | 초기 계획 | 최종 확인 범위 |
|---|---|---|
| 품질 검사 | HSV 색상 검출 중심 | YOLOv5 + RealSense + ROI + depth 3D point |
| 분류 | 서보 분류, Dobot은 추가 목표 | Dobot suction Pick & Place 구현 |
| 웹 | 프레임워크 후보 상태 | React/Vite 기반 RealOps·Simulation Dashboard |
| 서버 | FastAPI, ROS2, DB 계획 | FastAPI, ROS2 bridge, REST, WebSocket 구현 |
| 데이터 | SQLite/SQLAlchemy 이력 저장 | 런타임 메모리 통계, 영속 DB는 후속 과제 |
| LLM/음성 | STT–LLM–TTS 전체 흐름 | LLM 텍스트 명령과 키워드 fallback |
| TurtleBot | 자동 출동·Nav2 goal | 카메라·pose·map 모니터링과 SLAM 시연, 자동 임무는 후속 과제 |
| 디지털 트윈 | 보조 시뮬레이션 | RoboDK 공정과 Simulation Dashboard 구현 |

## 협업 원칙

- 인터페이스 변경은 ROS2 topic, REST, WebSocket 소비자를 함께 확인합니다.
- 실제 장비 의존 기능은 mock 또는 simulation 경로를 먼저 준비합니다.
- 초기 목표 수치와 완료된 검증 결과를 구분해 문서화합니다.
- 실행 환경·좌표·모델이 바뀌면 루트 README와 실제 장비 가이드를 함께 갱신합니다.

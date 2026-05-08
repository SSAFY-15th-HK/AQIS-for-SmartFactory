# 02. 시스템 아키텍처

## 설계 철학

본 시스템은 **3개의 통신 레이어를 분리**하는 구조를 따른다. 한 채널에 모든 데이터를 통합하면 영상 같은 큰 페이로드가 명령 채널을 막아 시스템 전체가 느려진다. 따라서 의미가 다른 트래픽은 처음부터 별개 채널로 분리한다.

또한 **중앙 제어형(Server-centric)** 아키텍처를 채택한다. Server가 시스템의 두뇌 역할을 하며 모든 판단과 명령 디스패치를 담당하고, 각 노드는 단순 실행 단위로 동작한다. 브로커형 대비 장점은 다음과 같다:

- 상태 관리가 한 곳에 모여 있어 디버깅이 쉬움
- 비전 결과 → 판단 → 분류기 명령의 흐름이 코드 한 곳에서 추적됨
- 각 ROS2 노드는 가벼워져 단일 책임 원칙을 지킴

## 통신 레이어 구조

시스템은 다음 3개 레이어로 분리된다:

### 레이어 1 — 사용자 ↔ Server (WebSocket + REST)

브라우저는 ROS2 토픽을 직접 구독할 수 없으므로 WebSocket을 경유한다. JSON 메시지 단위의 가벼운 양방향 통신.

- **WebSocket** (`ws://localhost:8000/ws`): 실시간 이벤트 푸시 (검출 결과, 터틀봇 위치, 상태 변화)
- **REST API** (`http://localhost:8000/api/...`): 비실시간 요청 (이력 조회, 음성 입력 업로드, 설정 변경)
- **MJPEG HTTP** (`http://laptop:8080/stream`): 컨베이어 영상 스트림 (별도 채널)

### 레이어 2 — Server ↔ ROS2 (rclpy 같은 프로세스)

Server는 Python으로 구현되며 `rclpy` 라이브러리로 ROS2 노드 역할을 동시에 수행한다. 즉 Server 자체가 ROS2 네트워크의 일원으로서 토픽을 publish/subscribe한다. 별도 브릿지 없이 하나의 프로세스 안에서 "웹에서 받은 명령 → ROS2 토픽 발행"이 가능하다.

### 레이어 3 — ROS2 노드 간 통신 (DDS)

ROS2의 기본 미들웨어인 DDS가 분산 통신을 자동으로 처리한다. 같은 Wi-Fi 네트워크 + 같은 `ROS_DOMAIN_ID`를 가진 모든 노드가 자동으로 서로를 발견한다.

## 머신 구성 (3PC 분산)

세 대의 컴퓨터가 같은 Wi-Fi에 연결되어 ROS2 네트워크를 구성한다.

| 머신 | 역할 | 실행 컴포넌트 |
|---|---|---|
| 노트북 (Ubuntu 22.04) | 시스템 두뇌 | Browser UI, FastAPI Server, SQLite, Whisper STT, Vision Node, Dobot Node, MJPEG 서버 |
| 컨베이어 라즈베리파이 5 | 모터·서보 슬레이브 | Flask HTTP 서버 + gpiozero (ROS2 미사용) |
| 터틀봇3 와플 (라즈베리파이) | 모바일 로봇 | turtlebot3_bringup, Nav2, slam_toolbox |

추가로 **집 데스크톱**이 Tailscale 터널을 통해 LLM 서비스를 제공한다. 이 데스크톱은 ROS2 네트워크와 무관하며 순수하게 외부 API처럼 호출된다.

## 데이터 흐름 패턴

### 패턴 A — 검출 이벤트 흐름 (실시간, 빈도 높음)

```
RealSense (USB) → Vision Node (노트북, ROS2)
  → /defect/detection 토픽 발행
  → Server가 토픽 구독, 상태 업데이트
  → SQLite에 detections row 추가
  → WebSocket으로 UI에 push
  → 동시에 HTTP 호출로 컨베이어 라즈파이에 분류 명령 (/sort/normal 또는 /sort/defect)
```

이 흐름은 컨베이어 동작 중 지속적으로 발생한다. 메시지 크기가 작아(JSON 수백 바이트) 부담 없음.

### 패턴 B — 영상 스트림 흐름 (별도 채널)

```
RealSense (USB) → Vision Node (노트북)
  → MJPEG HTTP 서버 (localhost:8080)
  → Browser <img src=...> 직접 연결
```

영상은 ROS2 토픽이나 WebSocket을 거치지 않는다. Vision Node가 검출 박스를 그린 프레임을 MJPEG으로 스트리밍하면 브라우저가 직접 받는다. 이렇게 분리하면 영상 트래픽이 명령/이벤트 채널을 점유하지 않는다.

### 패턴 C — 음성 명령 흐름 (이벤트 기반)

```
Browser 마이크 → 녹음 → REST API로 Server에 전송
  → Whisper STT (서버 측 또는 노트북 GPU)
  → 텍스트 + 안전 키워드 매칭 (정지/stop은 LLM 우회)
  → Tailscale → 집 Desktop의 llama.cpp → 의도 + 파라미터 JSON
  → Server가 의도 → ROS2 명령 매핑
  → 응답 텍스트 (LLM이 생성) → pyttsx3 TTS → 음성 출력
```

마지막 단계의 음성 출력은 사용자에게 들리는 형태로, 노트북 스피커로 출력하거나 WebSocket으로 브라우저에 텍스트만 전달하고 브라우저 TTS 사용도 가능. 구현 시점에 결정.

### 패턴 D — 터틀봇 미션 흐름 (이벤트 기반)

```
Server (출동 트리거 감지: 카운트 임계 또는 음성 명령)
  → /turtlebot/goal 토픽 또는 Nav2 액션 클라이언트 호출
  → 터틀봇 와플의 Nav2가 경로 계획 + 주행
  → /amcl_pose 토픽으로 위치 publish (Server 구독)
  → 도착 시 Server가 미션 상태 업데이트, UI에 알림
  → 일정 시간 또는 명령 후 home 복귀 (역방향 goal)
```

## 안전 장치 흐름 (LLM 우회)

긴급 정지는 LLM과 네트워크 의존을 모두 우회하는 별도 경로를 갖는다.

- **웹 UI 빨간 STOP 버튼**: 클릭 → REST API `/api/emergency_stop` → Server가 즉시 모든 ROS2 노드에 정지 명령
- **STT 결과 단어 매칭**: Whisper 출력에 "정지", "stop" 포함 시 LLM 호출 전 가로채기 → 즉시 정지
- **컨베이어 보드의 물리 버튼**: SWITCH1/SWITCH2 중 하나를 비상 정지에 할당 (라즈베리파이 GPIO 인터럽트로 즉시 모터 정지)

이 세 경로는 어떤 상황에서도 동작해야 한다. 예: Tailscale 끊김, llama.cpp 다운, Wi-Fi 약함 등.

## 인증과 보안

본 프로젝트는 **로컬 신뢰 환경**을 가정한다. 다음은 명시적으로 다루지 않는다:

- 사용자 인증 (단일 사용자 가정)
- API 키 관리 (LLM은 Tailscale 내부망)
- HTTPS/TLS (HTTP만 사용)
- WebSocket 인증

학습 프로젝트의 범위에 집중하기 위함이다.

## 확장 가능성 (이번엔 안 하지만 구조상 가능)

- 멀티 적재장: Server에 적재장 좌표 테이블 추가, Nav2 goal에 다른 좌표만 넘기면 됨
- 다중 터틀봇: 토픽 네임스페이스 (`/turtlebot1/`, `/turtlebot2/`) 추가
- YOLO 검출 교체: Vision Node의 검출 함수만 교체 (인터페이스 동일 유지)
- 클라우드 LLM: llama.cpp 호출 부분만 OpenAI/Anthropic API로 교체

## 다이어그램 (별도 PNG/SVG 첨부)

본 문서에 첨부될 다이어그램:

- 통신 아키텍처 전체도 (3 레이어 + 머신 구성)
- 데이터 흐름 시퀀스 다이어그램 (검출 → 분류 → DB → UI)
- 음성 명령 처리 흐름도

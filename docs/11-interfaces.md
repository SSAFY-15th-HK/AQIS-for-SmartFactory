# 11. 인터페이스 합의서

본 문서는 두 개발자가 만지는 코드 사이의 모든 인터페이스를 정의한다. **W1 D1-2 안에 두 사람이 합의하여 채우고**, 이후 변경은 양쪽 동의 필요.

상세 메시지 포맷은 `05-data-model.md`를 참조하며, 본 문서는 책임 경계와 합의 절차에 집중한다.

## 책임 경계

### A 담당 컴포넌트가 노출하는 인터페이스

| 인터페이스 | 사용자(B 담당이 호출) | 정의 위치 |
|---|---|---|
| WebSocket 서버 (`/ws`) | UI에서 구독 | 05-data-model.md §WebSocket |
| REST API (`/api/...`) | UI에서 호출 | 05-data-model.md §REST |
| ROS2 토픽 `/conveyor/status` | UI 상태 표시 | 05-data-model.md §ROS2 |
| ROS2 토픽 `/turtlebot/mission_status` | UI 상태 표시 | 05-data-model.md §ROS2 |
| MJPEG 스트림 URL (`http://localhost:8080/stream`) 게시 | UI에서 `<img>` src로 사용 | 04-tech-stack.md |

### B 담당 컴포넌트가 노출하는 인터페이스

| 인터페이스 | 사용자(A 담당이 호출) | 정의 위치 |
|---|---|---|
| ROS2 토픽 `/defect/detection` 발행 | A의 Server가 구독 | 05-data-model.md §ROS2 |
| MJPEG 스트림 게시 | A는 게시만 알면 됨 | 04-tech-stack.md |
| 터틀봇 ROS2 표준 토픽 (Nav2) | A의 Server가 goal 발행 | Nav2 표준 |

### 외부 인터페이스 (양쪽 모두 호출)

- **컨베이어 HTTP 슬레이브** (`http://<rpi-ip>:5000/...`): A가 구현, A의 Server에서만 호출하므로 B는 직접 호출하지 않음
- **llama.cpp**: A가 통합, B는 의도 → 동작이 잘 매핑되는지 시연 시점에만 확인
- **Tailscale**: A 셋업

## 환경 변수 합의

`.env` 파일에 들어갈 값은 두 분 모두 같은 키를 사용. 04-tech-stack.md의 `.env` 예시를 그대로 사용.

특히 다음은 시연 환경 의존이라 W3에 확정:

- `HOME_POSE_X`, `HOME_POSE_Y` — 매핑 후 RViz에서 측정
- `DROPOFF_POSE_X`, `DROPOFF_POSE_Y` — 매핑 후 측정
- `DEFECT_COUNT_THRESHOLD` — 시연 흐름 따라 조정 (3~5 정도)

## ROS2 메시지 변경 절차

ROS2 토픽 메시지 페이로드 변경 시:

1. 필요한 사람이 PR 작성
2. 다른 한 사람의 리뷰 후 머지
3. 머지 후 1시간 안에 둘 다 양쪽 코드 업데이트
4. 통합 테스트 (양쪽 노드 동시 실행)

작은 필드 추가는 문제 없지만, **필드 이름 변경/제거는 반드시 사전 합의**.

## WebSocket 메시지 추가 절차

UI에 새 정보가 필요할 때:

1. B가 필요한 데이터를 A에게 요청 (Slack/이슈)
2. A가 메시지 type 추가, 발행 시점 정의
3. 05-data-model.md 업데이트
4. B가 UI 구독 코드 추가

## REST API 추가 절차

같은 절차. 05-data-model.md 표 업데이트 필수.

## 코드 베이스 구조

```
/repo
  /server               # A 주도
    /factory_server     # FastAPI + rclpy 통합 패키지
      /ros_nodes        # ROS2 노드들
      /api              # REST 라우터
      /ws               # WebSocket 핸들러
      /db               # SQLAlchemy 모델
      /voice            # STT, LLM 클라이언트, TTS
    pyproject.toml
    requirements.txt
  /web                  # B 주도
    /src
      /components
      /pages
      /lib              # WebSocket 클라이언트, API 호출
    package.json
    pnpm-lock.yaml
  /vision               # B 주도 (ROS2 Vision Node)
    /vision_node
      detector.py
      mjpeg_server.py
    package.xml
  /conveyor-rpi         # A 주도
    server.py           # Flask
    motor_control.py
    requirements.txt
    install.sh          # systemd 등록
  /docs                 # 양쪽
  /scripts              # 공통 (실행 스크립트)
  /maps                 # B 주도 (SLAM 결과물)
  README.md
  .env.example
  .gitignore
```

각자 주도 영역 내부 파일 구조는 자유. 공유 인터페이스(05-data-model.md)만 일치하면 됨.

## Git 운영

- `main`: 시연 가능한 안정 상태만 머지
- `dev`: 통합 작업 브랜치
- `feature/<영역>-<짧은이름>`: 개인 작업

PR 머지 조건:

- 본인 외 1명 리뷰 (해당 영역 책임자 제외하고 다른 한 명)
- 빌드 통과 (CI 있으면)
- 테스트 동작 확인

커밋 메시지는 Conventional Commits 권장 (`feat:`, `fix:`, `docs:`, `refactor:`).

## 통신 채널

- 코드/이슈: GitHub
- 일상 동기화: 카카오톡/Slack/Discord (둘이 합의)
- 화면 공유 디버깅: Discord 또는 Zoom
- 파일 공유 (영상, 사진 등): GitHub LFS 또는 Google Drive

## 정기 미팅

- 평일 매일: 5분 동기화 (시작 시 또는 종료 시)
- 매 주말: 30분 회고 + 다음 주 계획

## 의사결정 절차

- **하루 안에 결정 가능한 작은 사안**: 둘이 채팅으로 합의 후 문서/코드 업데이트
- **여파가 큰 결정 (스케줄, 범위, 기술 스택 변경)**: 동기 미팅 후 문서 업데이트, 양쪽 명시 동의
- **막혔을 때**: 2시간 룰 적용. 한 문제에 2시간 이상 못 풀면 상대에게 공유

## 합의 완료 체크리스트 (W1 D2 종료까지)

- [ ] 코드 베이스 구조 합의, GitHub repo 초기 commit
- [ ] `.env.example` 합의, 각자 `.env` 작성
- [ ] ROS_DOMAIN_ID 결정 (예: 42)
- [ ] 노트북, 라즈베리파이 5, 터틀봇 와플 IP 주소 또는 hostname 정리
- [ ] 인터페이스(WebSocket/REST/ROS2 토픽) 초안이 05-data-model.md에 작성됨
- [ ] CI 또는 최소 빌드 스크립트 동작
- [ ] 매일 동기화 채널 결정
- [ ] 시연 환경 후보지 결정 (5m+ 가능 여부 포함)

위 모든 항목 통과 시 W1 D3부터 본격 모듈 개발 시작.

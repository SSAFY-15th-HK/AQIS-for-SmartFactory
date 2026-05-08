# 08. 음성 인터페이스 (STT / LLM / TTS)

## 전체 흐름

```
[Browser 마이크 녹음]
   ↓ POST /api/voice/upload (multipart)
[FastAPI Server]
   ↓
[Whisper STT] → 텍스트
   ↓
[안전 키워드 사전 검사] → 매칭 시 즉시 emergency_stop, 종료
   ↓
[Tailscale → 집 데스크톱 llama.cpp] → 의도 + 파라미터 JSON
   ↓
[Server: 의도 → ROS2 명령 매핑]
   ↓
[LLM 응답 생성] → 한국어 자연어 텍스트
   ↓
[pyttsx3 TTS] → 스피커 출력
   ↓ (병렬) WebSocket으로 UI에도 텍스트 표시
```

## 단계별 상세

### 1. 음성 입력 (Browser)

브라우저에서 마이크 권한 요청 후 녹음. 사용자가 "말하기" 버튼을 누르고 있는 동안 녹음, 떼면 종료(push-to-talk 방식). 또는 짧은 발화 후 자동 정지(VAD).

- 단순 구현: 녹음 시작/정지 버튼 두 개
- 권장: push-to-talk 방식 (오인식 줄임)
- 녹음 포맷: webm 또는 wav, 16kHz mono
- 길이 제한: 10초 (의도치 않은 긴 녹음 방지)

업로드 시 `multipart/form-data`로 `/api/voice/upload`에 전송.

### 2. STT (Whisper)

서버에서 faster-whisper로 처리.

```python
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cuda")  # GPU 없으면 "cpu"
segments, info = model.transcribe(audio_path, language="ko")
text = " ".join(segment.text for segment in segments)
```

- **모델 크기**: `base`로 시작 (한국어 정확도 적당, 빠름). 부정확하면 `small` 또는 `medium`
- **언어**: 한국어 고정 (`language="ko"`)
- **GPU**: 있으면 사용 (응답 시간 단축)

### 3. 안전 키워드 사전 검사

LLM 호출 전, STT 결과 텍스트에 다음 단어 중 하나라도 포함되면 즉시 emergency_stop을 호출하고 함수 종료.

```python
EMERGENCY_KEYWORDS = ["정지", "스톱", "stop", "멈춰", "멈춰줘"]

if any(kw in transcript for kw in EMERGENCY_KEYWORDS):
    trigger_emergency_stop()
    save_voice_log(transcript, intent="emergency_stop", response="시스템을 정지합니다")
    return {"transcript": transcript, "response": "시스템을 정지합니다"}
```

이 경로는 절대 LLM/Tailscale에 의존하지 않는다.

### 4. LLM 의도 추출

집 데스크톱의 llama.cpp 서버를 OpenAI 호환 API로 호출.

**시스템 프롬프트**

```
You are an intent classifier for a smart factory voice control system.

Given a user utterance in Korean, output ONLY a JSON object with these fields:
- intent: one of [start_conveyor, stop_conveyor, go_to_unload, return_home,
                  query_defect_rate, query_total_count, query_robot_location,
                  query_box_count, query_status, unknown]
- urgency: "normal" or "high"
- params: object with extracted parameters or {}

Output strict JSON. No explanations, no markdown.

Examples:
User: "컨베이어 시작해"
Output: {"intent": "start_conveyor", "urgency": "normal", "params": {}}

User: "불량품 좀 비워줘"
Output: {"intent": "go_to_unload", "urgency": "normal", "params": {}}

User: "지금 불량률 얼마야?"
Output: {"intent": "query_defect_rate", "urgency": "normal", "params": {}}
```

**호출 코드 예시**

```python
import requests

response = requests.post(
    f"{LLM_BASE_URL}/v1/chat/completions",
    json={
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        "temperature": 0.0,
        "max_tokens": 100,
    },
    timeout=5.0,  # Tailscale 끊김 대비
)
intent_json = json.loads(response.json()["choices"][0]["message"]["content"])
```

### 5. 의도 → ROS2 명령 매핑

```python
INTENT_HANDLERS = {
    "start_conveyor": handle_start_conveyor,
    "stop_conveyor": handle_stop_conveyor,
    "go_to_unload": handle_go_to_unload,
    "return_home": handle_return_home,
    "query_defect_rate": handle_query,
    "query_total_count": handle_query,
    # ...
}

handler = INTENT_HANDLERS.get(intent_json["intent"], handle_unknown)
state_for_response = handler(intent_json["params"])
```

### 6. LLM 응답 생성

상태 데이터를 LLM에 같이 전달하여 자연스러운 한국어 응답 생성.

**시스템 프롬프트**

```
You are a voice assistant for a smart factory system. Given the current state
and the user question (both in Korean), generate a brief natural Korean response
in 1-2 sentences using polite formal speech (해요체 또는 합니다체).

Use the data from the current session unless the user explicitly asks about
all-time data. Keep responses concise and factual. No emojis.
```

**호출**

```python
response_text = call_llm(
    system=RESPONSE_SYSTEM_PROMPT,
    user=f"State: {state_json}\nQuestion: {transcript}",
)
```

명령 처리(시작/정지/출동 등) 결과는 짧은 확인 응답으로 충분하므로 LLM 호출 생략 가능. 템플릿 문자열로 처리:

```python
ACK_TEMPLATES = {
    "start_conveyor": "컨베이어를 시작합니다",
    "stop_conveyor": "컨베이어를 정지합니다",
    "go_to_unload": "터틀봇이 적재장으로 출발합니다",
    "return_home": "터틀봇이 복귀합니다",
}
```

질문(query_*) 의도일 때만 LLM 응답 생성을 거친다.

### 7. TTS 출력

```python
import pyttsx3

engine = pyttsx3.init()
engine.setProperty('rate', 180)
engine.setProperty('voice', korean_voice_id)  # 시스템에 한국어 voice 설치 필요
engine.say(response_text)
engine.runAndWait()
```

pyttsx3 한국어 음질이 부족하면 다음을 검토:

- Edge TTS (`edge-tts` 패키지, 무료, 음질 매우 좋음)
- Google Cloud TTS (유료지만 정확)
- 클라이언트 측 SpeechSynthesis API (브라우저)

학습 프로젝트엔 **Edge TTS 추천** — 무료에 자연스러움.

## 명령 카탈로그 (구현 시 점진 확장)

W2 시점에 우선 다음 핵심 명령만 동작하면 됨.

| 의도 | 발화 예시 | 처리 방식 |
|---|---|---|
| start_conveyor | "컨베이어 시작", "벨트 켜줘" | HTTP POST /api/conveyor/start |
| stop_conveyor | "컨베이어 정지", "멈춰" (단, 정지/멈춰는 키워드 매칭으로 emergency_stop) | HTTP POST /api/conveyor/stop |
| go_to_unload | "불량품 비워줘", "출동해" | Nav2 send_goal(dropoff) |
| return_home | "복귀해", "돌아와" | Nav2 send_goal(home) |
| emergency_stop | "정지", "스톱" | LLM 우회, 즉시 정지 |

W3 이후 query_* 카탈로그 확장:

| 의도 | 발화 예시 | 응답 데이터 |
|---|---|---|
| query_defect_rate | "지금 불량률 얼마야?" | session_total, session_defects, defect_rate |
| query_total_count | "몇 개 검사했어?" | session_total |
| query_robot_location | "터틀봇 어디 있어?" | robot_pose, robot_status |
| query_box_count | "박스에 몇 개 있어?" | box_count |
| query_status | "상태 알려줘" | 종합 |

## 폴백 전략 (W4 이후 시간 여유 시)

LLM 호출 실패 시 키워드 매칭으로 우회:

```python
KEYWORD_MAP = {
    "시작": "start_conveyor",
    "출동": "go_to_unload",
    "비워": "go_to_unload",
    "복귀": "return_home",
    "돌아": "return_home",
    "불량률": "query_defect_rate",
    "몇 개": "query_total_count",
    # ...
}

def keyword_fallback(text):
    for kw, intent in KEYWORD_MAP.items():
        if kw in text:
            return {"intent": intent, "urgency": "normal", "params": {}}
    return {"intent": "unknown", ...}
```

LLM 타임아웃(5초) 또는 connection error 시 자동으로 fallback.

## 응답 시간 예산

엔드 투 엔드 음성 명령 처리 시간 목표:

| 단계 | 예상 시간 |
|---|---|
| 녹음 → 업로드 | 0.3초 (녹음 끝나는 즉시) |
| Whisper STT | 0.5~1.5초 (CPU 기준) |
| 안전 키워드 검사 | 즉시 |
| LLM 의도 추출 | 0.5~2초 (네트워크 + 추론) |
| ROS2 명령 발행 | 즉시 |
| LLM 응답 생성 (질문일 때만) | 1~2초 |
| TTS | 0.3~1초 |
| **합계 (명령)** | **1~3초** |
| **합계 (질문)** | **2~6초** |

3초 이상 걸리면 사용자 체감 답답. 다음 최적화 가능:

- 응답 생성에 LLM 안 쓰고 템플릿만 사용 (-1~2초)
- Whisper 모델을 `tiny`로 (-0.5초, 정확도 손실)
- 응답 시작 시 "처리 중입니다" 짧은 음성을 먼저 재생 (체감 시간 단축)

## 디버깅 도구

- 모든 voice_logs 행은 transcript, intent, response를 포함하므로 W3 이후 UI에 음성 이력 페이지 추가
- LLM 응답이 JSON parse 실패 시 raw 응답을 로그에 남김
- STT 결과를 콘솔에 출력하면 키워드 매칭 누락 여부 즉시 확인 가능

## 시연 시 주의

- 시연 환경 마이크 노이즈 사전 점검
- 발표장 인터넷 불안정 가능 → Tailscale 끊김 대비 미리 폴백 동작 확인
- 시연 직전 STT 정확도 한 번 확인 (Whisper 모델이 환경 적응 안 됨, 입력 마이크 음량 영향 큼)

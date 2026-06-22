from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


INTENT_ALIASES = {
    "start_aqis": "START_AQIS",
    "start_process": "START_AQIS",
    "start_conveyor": "START_AQIS",
    "stop_aqis": "STOP_AQIS",
    "stop_process": "STOP_AQIS",
    "query_status": "QUERY_STATUS",
    "query_defects": "QUERY_DEFECT_RATE",
    "query_defect_rate": "QUERY_DEFECT_RATE",
    "query_total_count": "QUERY_TOTAL_COUNT",
    "query_dobot": "QUERY_DOBOT",
    "query_turtlebot_pose": "QUERY_TURTLEBOT_POSE",
    "query_robot_location": "QUERY_TURTLEBOT_POSE",
    "dispatch_turtlebot": "DISPATCH_AGV",
    "go_to_unload": "DISPATCH_AGV",
    "unknown": "UNKNOWN",
}

EMERGENCY_KEYWORDS = ["emergency", "e-stop", "estop", "긴급", "비상", "정지", "스톱", "stop", "멈춰"]

SYSTEM_PROMPT = """
You are an intent classifier for an AQIS smart factory monitoring dashboard.
Output ONLY a JSON object with:
- intent: one of [start_aqis, stop_aqis, query_status, query_defects,
  query_total_count, query_dobot, query_turtlebot_pose, dispatch_turtlebot, unknown]
- urgency: one of [normal, high]
- params: object
No markdown. No explanation.
""".strip()


class LlmCommandService:
    def __init__(self, base_url: str, api_key: str, model: str, timeout_sec: float = 8.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_sec = timeout_sec

    def classify(self, text: str) -> dict:
        normalized = text.strip().lower()
        if any(keyword in normalized for keyword in EMERGENCY_KEYWORDS):
            return {"intent": "EMERGENCY_STOP", "urgency": "high", "params": {}, "source": "safety_keyword"}

        fallback = self.keyword_fallback(normalized)
        if not self.base_url or not self.api_key:
            return {**fallback, "source": "keyword_no_llm"}

        try:
            llm_result = self.call_llm(text)
            intent = str(llm_result.get("intent", "unknown")).lower()
            return {
                "intent": INTENT_ALIASES.get(intent, "UNKNOWN"),
                "urgency": llm_result.get("urgency", "normal"),
                "params": llm_result.get("params", {}),
                "source": "llm",
            }
        except Exception as exc:
            return {**fallback, "source": "keyword_after_llm_error", "llm_error": str(exc)}

    def call_llm(self, text: str) -> dict:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": 120,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
            body = json.loads(response.read().decode("utf-8"))

        content = body["choices"][0]["message"]["content"].strip()
        return self.extract_json(content)

    def extract_json(self, content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                return json.loads(content[start : end + 1])
            raise

    def keyword_fallback(self, text: str) -> dict:
        if any(keyword in text for keyword in ["불량률", "defect rate"]):
            return {"intent": "QUERY_DEFECT_RATE", "urgency": "normal", "params": {}}
        if any(keyword in text for keyword in ["몇 개", "total", "count", "검사"]):
            return {"intent": "QUERY_TOTAL_COUNT", "urgency": "normal", "params": {}}
        if any(keyword in text for keyword in ["dobot", "도봇", "joint", "조인트"]):
            return {"intent": "QUERY_DOBOT", "urgency": "normal", "params": {}}
        if any(keyword in text for keyword in ["turtlebot", "터틀봇", "위치", "pose"]):
            return {"intent": "QUERY_TURTLEBOT_POSE", "urgency": "normal", "params": {}}
        if any(keyword in text for keyword in ["status", "상태"]):
            return {"intent": "QUERY_STATUS", "urgency": "normal", "params": {}}
        if any(keyword in text for keyword in ["dispatch", "출동", "수거", "비워"]):
            return {"intent": "DISPATCH_AGV", "urgency": "normal", "params": {}}
        if any(keyword in text for keyword in ["start", "시작", "실행", "aqis"]):
            return {"intent": "START_AQIS", "urgency": "normal", "params": {}}
        return {"intent": "UNKNOWN", "urgency": "normal", "params": {}}


def command_message(intent: str, state: dict[str, Any], *, action_status: str | None = None) -> str:
    stats = state.get("stats", {})
    dobot = state.get("dobot", {})
    turtlebot = state.get("turtlebot_pose")
    process = state.get("process", {})

    if intent == "START_AQIS":
        return "AQIS 프로세스를 시작했습니다." if action_status != "already_running" else "AQIS 프로세스가 이미 실행 중입니다."
    if intent == "STOP_AQIS":
        return "AQIS 프로세스를 정지했습니다."
    if intent == "EMERGENCY_STOP":
        return "비상 정지를 실행했습니다."
    if intent == "QUERY_DEFECT_RATE":
        rate = float(stats.get("defect_rate", 0)) * 100
        return f"현재 총 {stats.get('session_total', 0)}개 중 불량은 {stats.get('session_defects', 0)}개이고, 불량률은 {rate:.1f}%입니다."
    if intent == "QUERY_TOTAL_COUNT":
        return f"현재 세션에서 총 {stats.get('session_total', 0)}개를 검사했습니다."
    if intent == "QUERY_DOBOT":
        joints = dobot.get("joints", [])
        alarm_count = len(dobot.get("alarms", []))
        return f"도봇 조인트 {len(joints)}개가 수신 중이고, 알람은 {alarm_count}개입니다."
    if intent == "QUERY_TURTLEBOT_POSE":
        if not turtlebot:
            return "아직 터틀봇 위치 데이터가 수신되지 않았습니다."
        return f"터틀봇 위치는 x {turtlebot.get('x', 0):.2f}, y {turtlebot.get('y', 0):.2f}, yaw {turtlebot.get('yaw', 0):.2f}입니다."
    if intent == "QUERY_STATUS":
        running = "실행 중" if process.get("running") else "정지 상태"
        return f"AQIS는 {running}이고, 시스템 상태는 {stats.get('system_status', 'UNKNOWN')}입니다."
    if intent == "DISPATCH_AGV":
        return "터틀봇 수거 미션을 요청했습니다." if action_status != "blocked" else "현재 수거할 불량품이 없습니다."
    return "이해하지 못한 명령입니다. 시작, 상태 조회, 불량률 조회, 도봇 상태, 터틀봇 위치를 사용할 수 있습니다."

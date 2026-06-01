from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

Color = Literal["red", "green", "blue", "yellow"]
EventType = Literal[
    "detection",
    "conveyor_status",
    "mission_update",
    "voice_response",
    "system_status",
    "error",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DetectionData(BaseModel):
    id: int
    timestamp: str = Field(default_factory=utc_now_iso)
    color: Color
    is_defect: bool
    confidence: float
    bbox: list[int]
    session_total: int
    session_defects: int
    defect_rate: float


class Event(BaseModel):
    type: EventType
    data: dict

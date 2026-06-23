from __future__ import annotations

import math
import time
from collections.abc import Callable


class DetectionDeduper:
    def __init__(
        self,
        *,
        window_sec: float = 2.0,
        iou_threshold: float = 0.5,
        center_distance_px: float = 70.0,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self.window_sec = window_sec
        self.iou_threshold = iou_threshold
        self.center_distance_px = center_distance_px
        self.time_fn = time_fn
        self._recent: list[dict] = []

    def reset(self) -> None:
        self._recent.clear()

    def should_accept(self, payload: dict) -> bool:
        now = self.time_fn()
        self._recent = [item for item in self._recent if now - item["stamp"] <= self.window_sec]

        candidate = self._candidate(payload, now)
        for previous in self._recent:
            if self._same_detection(candidate, previous):
                previous.update(
                    {
                        "stamp": now,
                        "bbox": candidate["bbox"] or previous["bbox"],
                        "center": candidate["center"] or previous["center"],
                    }
                )
                return False

        self._recent.append(candidate)
        return True

    def _candidate(self, payload: dict, stamp: float) -> dict:
        bbox = self._bbox(payload)
        center = self._center(payload, bbox)
        explicit_id = next(
            (
                str(payload[key])
                for key in ("track_id", "detection_id", "object_id", "part_id")
                if payload.get(key) not in {None, ""}
            ),
            None,
        )
        return {
            "stamp": stamp,
            "explicit_id": explicit_id,
            "signature": self._signature(payload),
            "bbox": bbox,
            "center": center,
        }

    def _same_detection(self, candidate: dict, previous: dict) -> bool:
        if candidate["signature"] != previous["signature"]:
            return False

        if candidate["explicit_id"] and candidate["explicit_id"] == previous["explicit_id"]:
            return True

        if candidate["bbox"] and previous["bbox"]:
            if self._iou(candidate["bbox"], previous["bbox"]) >= self.iou_threshold:
                return True

        if candidate["center"] and previous["center"]:
            if self._distance(candidate["center"], previous["center"]) <= self.center_distance_px:
                return True

        if candidate["signature"][2] and not any(
            (candidate["bbox"], previous["bbox"], candidate["center"], previous["center"])
        ):
            return True

        return False

    @staticmethod
    def _signature(payload: dict) -> tuple[str, str, bool]:
        label = str(payload.get("label") or payload.get("defect_class") or payload.get("color") or "").lower()
        result = str(payload.get("result") or "").lower()
        is_defect = bool(payload.get("is_defect"))
        return label, result, is_defect

    @staticmethod
    def _bbox(payload: dict) -> tuple[float, float, float, float] | None:
        bbox = payload.get("bbox")
        if not isinstance(bbox, list) or len(bbox) < 4:
            return None
        try:
            x, y, w, h = [float(value) for value in bbox[:4]]
        except (TypeError, ValueError):
            return None
        if payload.get("bbox_format") == "xyxy":
            w -= x
            h -= y
        if w <= 0 or h <= 0:
            return None
        return x, y, w, h

    @staticmethod
    def _center(payload: dict, bbox: tuple[float, float, float, float] | None) -> tuple[float, float] | None:
        center = payload.get("center")
        if isinstance(center, list) and len(center) >= 2:
            try:
                return float(center[0]), float(center[1])
            except (TypeError, ValueError):
                return None
        if bbox:
            x, y, w, h = bbox
            return x + w / 2.0, y + h / 2.0
        return None

    @staticmethod
    def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        left = max(ax, bx)
        top = max(ay, by)
        right = min(ax + aw, bx + bw)
        bottom = min(ay + ah, by + bh)
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        union = aw * ah + bw * bh - intersection
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

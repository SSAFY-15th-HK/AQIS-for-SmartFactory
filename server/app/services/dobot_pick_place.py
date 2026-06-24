from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any

from app.config import settings


class DobotPickPlaceService:
    def __init__(self, mode: str, command: str, *, resume_callback: Callable[[], dict] | None = None) -> None:
        self.mode = mode
        self.command = command
        self.resume_callback = resume_callback
        self.enabled = mode == "real"
        self.running = False
        self.last_error: str | None = None
        self.last_trigger: dict[str, Any] | None = None
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.returncode: int | None = None
        self._process: subprocess.Popen | None = None
        self._lock = threading.RLock()

    def status(self) -> dict:
        with self._lock:
            if self._process and self._process.poll() is not None:
                self.running = False
                self.returncode = self._process.returncode
            return {
                "enabled": self.enabled,
                "mode": self.mode,
                "running": self.running,
                "command": self.command,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "returncode": self.returncode,
                "last_error": self.last_error,
                "last_trigger": self.last_trigger,
            }

    def trigger(self, detection: dict | None = None) -> dict:
        with self._lock:
            if self.running:
                return {"status": "already_running", "data": self.status()}

            detection_payload = detection or {}
            dynamic_pick = self._dynamic_pick_pose(detection_payload)
            self.last_trigger = dict(detection_payload)
            if dynamic_pick:
                self.last_trigger["dobot_pick_pose"] = dynamic_pick
            self.last_error = None
            self.returncode = None
            self.started_at = time.time()
            self.finished_at = None

            if not self.enabled:
                self.running = True
                thread = threading.Thread(target=self._finish_mock, name="aqis-dobot-mock", daemon=True)
                thread.start()
                return {"status": "started", "data": self.status()}

            try:
                env = os.environ.copy()
                env.update(self._script_env(dynamic_pick))
                self._process = subprocess.Popen(
                    ["bash", "-lc", self.command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    text=True,
                    env=env,
                )
                self.running = True
                thread = threading.Thread(target=self._wait_for_process, name="aqis-dobot-pick-place", daemon=True)
                thread.start()
                return {"status": "started", "data": self.status()}
            except Exception as exc:
                self.running = False
                self.finished_at = time.time()
                self.last_error = str(exc)
                return {"status": "error", "data": self.status()}

    def stop(self, timeout_sec: float = 2.0) -> dict:
        with self._lock:
            process = self._process
            if not process or process.poll() is not None:
                self.running = False
                self.finished_at = self.finished_at or time.time()
                return {"status": "not_running", "data": self.status()}

            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=2.0)
            except Exception as exc:
                self.last_error = str(exc)
                return {"status": "error", "data": self.status()}

            self.running = False
            self.finished_at = time.time()
            self.returncode = process.returncode
            return {"status": "stopped", "data": self.status()}

    def _finish_mock(self) -> None:
        time.sleep(0.05)
        if settings.dobot_resume_conveyor_after_pick and self.resume_callback:
            self.resume_callback()
        with self._lock:
            self.running = False
            self.finished_at = time.time()
            self.returncode = 0

    def _wait_for_process(self) -> None:
        process = self._process
        if not process:
            return
        output = ""
        try:
            if process.stdout:
                output = process.stdout.read()[-1200:]
            returncode = process.wait()
            if returncode != 0:
                self.last_error = output or f"Dobot pick/place exited with code {returncode}"
            elif settings.dobot_resume_conveyor_after_pick and self.resume_callback:
                self.resume_callback()
        except Exception as exc:
            returncode = process.poll()
            self.last_error = str(exc)

        with self._lock:
            self.running = False
            self.finished_at = time.time()
            self.returncode = returncode

    def _dynamic_pick_pose(self, detection: dict) -> dict[str, float] | None:
        if not settings.dobot_dynamic_pick_enabled:
            return None
        if detection.get("has_depth") is False:
            return None

        camera_point = detection.get("camera_point_m")
        if not isinstance(camera_point, list) or len(camera_point) < 2:
            return None
        try:
            cam_x = float(camera_point[0])
            cam_y = float(camera_point[1])
        except (TypeError, ValueError):
            return None

        dobot_x_m = (
            settings.dobot_camera_to_dobot_x_cam_x * cam_x
            + settings.dobot_camera_to_dobot_x_cam_y * cam_y
            + settings.dobot_camera_to_dobot_x_bias
        )
        dobot_y_m = (
            settings.dobot_camera_to_dobot_y_cam_x * cam_x
            + settings.dobot_camera_to_dobot_y_cam_y * cam_y
            + settings.dobot_camera_to_dobot_y_bias
        )
        dobot_z_m = (
            settings.dobot_camera_to_dobot_z_cam_x * cam_x
            + settings.dobot_camera_to_dobot_z_cam_y * cam_y
            + settings.dobot_camera_to_dobot_z_bias
            if settings.dobot_dynamic_z_enabled
            else settings.dobot_dynamic_pick_z / 1000.0
        )
        return {
            "x": round(dobot_x_m * 1000.0, 3),
            "y": round(dobot_y_m * 1000.0, 3),
            "z": round(dobot_z_m * 1000.0, 3),
            "r": settings.dobot_dynamic_tool_r,
            "camera_x": cam_x,
            "camera_y": cam_y,
        }

    def _script_env(self, dynamic_pick: dict[str, float] | None = None) -> dict[str, str]:
        env = {
            "DOBOT_PICK_X": str(settings.dobot_pick_x),
            "DOBOT_PICK_Y": str(settings.dobot_pick_y),
            "DOBOT_PICK_Z": str(settings.dobot_pick_z),
            "DOBOT_PLACE_X": str(settings.dobot_place_x),
            "DOBOT_PLACE_Y": str(settings.dobot_place_y),
            "DOBOT_PLACE_Z": str(settings.dobot_place_z),
            "DOBOT_SAFE_Z": str(settings.dobot_safe_z),
            "DOBOT_HOME_X": str(settings.dobot_home_x),
            "DOBOT_HOME_Y": str(settings.dobot_home_y),
            "DOBOT_HOME_Z": str(settings.dobot_home_z),
            "DOBOT_TOOL_R": str(settings.dobot_tool_r),
            "DOBOT_MOTION_TYPE": str(settings.dobot_motion_type),
            "DOBOT_VELOCITY_RATIO": str(settings.dobot_velocity_ratio),
            "DOBOT_ACCELERATION_RATIO": str(settings.dobot_acceleration_ratio),
            "DOBOT_SUCTION_SETTLE_SEC": str(settings.dobot_suction_settle_sec),
        }
        if dynamic_pick:
            env.update(
                {
                    "DOBOT_PICK_X": str(dynamic_pick["x"]),
                    "DOBOT_PICK_Y": str(dynamic_pick["y"]),
                    "DOBOT_PICK_Z": str(dynamic_pick["z"]),
                    "DOBOT_TOOL_R": str(dynamic_pick["r"]),
                    "DOBOT_DYNAMIC_PICK": "true",
                    "DOBOT_DYNAMIC_PICK_CAMERA_X": str(dynamic_pick["camera_x"]),
                    "DOBOT_DYNAMIC_PICK_CAMERA_Y": str(dynamic_pick["camera_y"]),
                }
            )
        return env

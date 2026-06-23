#!/usr/bin/env python3
from __future__ import annotations

import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gpiod


DIR_PIN = 17
STEP_PIN = 27
ENABLE_PIN = 22
SERVO_PIN = 18

STEP_DELAY = 0.0005
ENABLE_ON = 0
ENABLE_OFF = 1
CONVEYOR_DIRECTION = 0

SERVO_RANGE = 270
SERVO_MIN_PULSE = 0.0005
SERVO_MAX_PULSE = 0.0025
SERVO_NEUTRAL_ANGLE = 135
SERVO_NORMAL_ANGLE = 95
SERVO_DEFECT_ANGLE = 175


class ConveyorController:
    def __init__(self) -> None:
        self.chip = gpiod.Chip("gpiochip0")
        self.dir_line = self.chip.get_line(DIR_PIN)
        self.step_line = self.chip.get_line(STEP_PIN)
        self.enable_line = self.chip.get_line(ENABLE_PIN)
        self.servo_line = self.chip.get_line(SERVO_PIN)

        self.dir_line.request(consumer="aqis-dir", type=gpiod.LINE_REQ_DIR_OUT)
        self.step_line.request(consumer="aqis-step", type=gpiod.LINE_REQ_DIR_OUT)
        self.enable_line.request(consumer="aqis-enable", type=gpiod.LINE_REQ_DIR_OUT)
        self.servo_line.request(consumer="aqis-servo", type=gpiod.LINE_REQ_DIR_OUT)

        self.lock = threading.Lock()
        self.running = False
        self.shutdown = False
        self.sorter_position = "normal"
        self.servo_angle = SERVO_NEUTRAL_ANGLE

        self.dir_line.set_value(CONVEYOR_DIRECTION)
        self.enable_line.set_value(ENABLE_OFF)

        self.step_thread = threading.Thread(target=self._step_loop, daemon=True)
        self.servo_thread = threading.Thread(target=self._servo_loop, daemon=True)
        self.step_thread.start()
        self.servo_thread.start()
        self.set_sorter("normal")

    def _step_loop(self) -> None:
        while not self.shutdown:
            with self.lock:
                active = self.running
            if active:
                self.step_line.set_value(1)
                time.sleep(STEP_DELAY)
                self.step_line.set_value(0)
                time.sleep(STEP_DELAY)
            else:
                time.sleep(0.02)

    def _servo_loop(self) -> None:
        while not self.shutdown:
            with self.lock:
                angle = self.servo_angle
            pulse_width = self._angle_to_pulse(angle)
            self.servo_line.set_value(1)
            time.sleep(pulse_width)
            self.servo_line.set_value(0)
            time.sleep(max(0.001, 0.02 - pulse_width))

    def _angle_to_pulse(self, angle: float) -> float:
        return (angle / SERVO_RANGE) * (SERVO_MAX_PULSE - SERVO_MIN_PULSE) + SERVO_MIN_PULSE

    def start(self) -> dict:
        with self.lock:
            self.dir_line.set_value(CONVEYOR_DIRECTION)
            self.enable_line.set_value(ENABLE_ON)
            self.running = True
        return self.status()

    def stop(self) -> dict:
        with self.lock:
            self.running = False
            self.enable_line.set_value(ENABLE_OFF)
        return self.status()

    def set_sorter(self, position: str) -> dict:
        if position not in {"normal", "defect"}:
            raise ValueError(f"unknown sorter position: {position}")
        with self.lock:
            self.sorter_position = position
            self.servo_angle = SERVO_DEFECT_ANGLE if position == "defect" else SERVO_NORMAL_ANGLE
        return self.status()

    def emergency_stop(self) -> dict:
        with self.lock:
            self.running = False
            self.sorter_position = "normal"
            self.servo_angle = SERVO_NEUTRAL_ANGLE
            self.enable_line.set_value(ENABLE_OFF)
            self.step_line.set_value(0)
        return self.status()

    def status(self) -> dict:
        with self.lock:
            return {
                "status": "ok",
                "running": self.running,
                "sorter_position": self.sorter_position,
                "servo_angle": self.servo_angle,
                "speed": 1.0 / max(STEP_DELAY * 2.0, 0.0001),
            }

    def close(self) -> None:
        self.shutdown = True
        time.sleep(0.1)
        self.emergency_stop()
        self.dir_line.release()
        self.step_line.release()
        self.enable_line.release()
        self.servo_line.release()
        self.chip.close()


controller = ConveyorController()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/status":
            self._send_json(controller.status())
            return
        self._send_json({"status": "error", "message": "not found"}, status=404)

    def do_POST(self) -> None:
        try:
            if self.path == "/conveyor/start":
                payload = controller.start()
            elif self.path == "/conveyor/stop":
                payload = controller.stop()
            elif self.path == "/sort/normal":
                payload = controller.set_sorter("normal")
            elif self.path == "/sort/defect":
                payload = controller.set_sorter("defect")
            elif self.path == "/emergency_stop":
                payload = controller.emergency_stop()
            else:
                self._send_json({"status": "error", "message": "not found"}, status=404)
                return
            self._send_json(payload)
        except Exception as exc:
            self._send_json({"status": "error", "message": str(exc)}, status=500)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 5000), Handler)

    def stop_server(signum, frame) -> None:
        server.shutdown()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)

    try:
        print("AQIS conveyor HTTP server listening on http://0.0.0.0:5000")
        server.serve_forever()
    finally:
        server.server_close()
        controller.close()


if __name__ == "__main__":
    main()

from collections import deque
from threading import RLock

from app.config import settings


class MockRoboDKAdapter:
    """Small server-side bridge used by the Web UI and the RoboDK Python script.

    The Web UI posts control requests to FastAPI. FastAPI stores the latest command
    here, and the RoboDK script polls /api/robodk/command to consume it. The script
    also posts runtime status back through /api/robodk/status.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.connected = False
        self.running = False
        self.stage = "IDLE"
        self.message = "RoboDK script has not reported yet."
        self.red_x: float | None = None
        self.active_script_id: str | None = None
        self.last_command: str | None = None
        self.pending_commands: deque[str] = deque()

    def status(self) -> dict:
        with self._lock:
            return {
                "connected": self.connected,
                "running": self.running,
                "stage": self.stage,
                "message": self.message,
                "red_x": self.red_x,
                "active_script_id": self.active_script_id,
                "last_command": self.last_command,
                "pending_command": self.pending_commands[0] if self.pending_commands else None,
                "pending_commands": list(self.pending_commands),
                "mode": getattr(settings, "robot_mode", "mock"),
            }

    def _enqueue(self, command: str) -> dict:
        with self._lock:
            self.pending_commands.append(command)
            self.last_command = command
        return self.status()

    def consume_command(self, script_id: str | None = None) -> str | None:
        with self._lock:
            if self.active_script_id and script_id != self.active_script_id:
                return None
            if not self.pending_commands:
                return None
            return self.pending_commands.popleft()

    def update_status(
        self,
        *,
        connected: bool | None = None,
        running: bool | None = None,
        stage: str | None = None,
        message: str | None = None,
        red_x: float | None = None,
        script_id: str | None = None,
    ) -> dict:
        with self._lock:
            if script_id:
                self.active_script_id = script_id
            if connected is not None:
                self.connected = connected
            else:
                self.connected = True
            if running is not None:
                self.running = running
            if stage is not None:
                self.stage = stage
            if message is not None:
                self.message = message
            if red_x is not None:
                self.red_x = red_x
        return self.status()

    def start_simulation(self) -> dict:
        self.running = True
        return self._enqueue("START")

    def pause_simulation(self) -> dict:
        self.running = False
        return self._enqueue("PAUSE")

    def stop_simulation(self) -> dict:
        self.running = False
        return self._enqueue("STOP")

    def reset_simulation(self) -> dict:
        self.running = False
        self.stage = "RESET_REQUESTED"
        return self._enqueue("RESET")

    def dispatch_agv(self) -> dict:
        return self._enqueue("DISPATCH_AGV")


robodk = MockRoboDKAdapter()

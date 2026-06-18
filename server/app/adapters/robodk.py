from app.config import settings


class MockRoboDKAdapter:
    """Small server-side bridge used by the Web UI and the RoboDK Python script.

    The Web UI posts control requests to FastAPI. FastAPI stores the latest command
    here, and the RoboDK script polls /api/robodk/command to consume it. The script
    also posts runtime status back through /api/robodk/status.
    """

    def __init__(self) -> None:
        self.connected = False
        self.running = False
        self.stage = "IDLE"
        self.message = "RoboDK script has not reported yet."
        self.red_x: float | None = None
        self.last_command: str | None = None
        self.pending_command: str | None = None

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "running": self.running,
            "stage": self.stage,
            "message": self.message,
            "red_x": self.red_x,
            "last_command": self.last_command,
            "pending_command": self.pending_command,
            "mode": getattr(settings, "robot_mode", "mock"),
        }

    def _enqueue(self, command: str) -> dict:
        self.pending_command = command
        self.last_command = command
        self.connected = True
        return self.status()

    def consume_command(self) -> str | None:
        command = self.pending_command
        self.pending_command = None
        return command

    def update_status(
        self,
        *,
        connected: bool | None = None,
        running: bool | None = None,
        stage: str | None = None,
        message: str | None = None,
        red_x: float | None = None,
    ) -> dict:
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

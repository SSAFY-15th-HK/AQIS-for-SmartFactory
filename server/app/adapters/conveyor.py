import json
import urllib.error
import urllib.request

from app.config import settings


class MockConveyorAdapter:
    def __init__(self) -> None:
        self.running = False
        self.sorter_position = "normal"
        self.speed = 0.5
        self.last_error: str | None = None
        self.last_command_ok = True

    def status(self) -> dict:
        return {
            "running": self.running,
            "mode": settings.conveyor_mode,
            "sorter_position": self.sorter_position,
            "speed": self.speed,
            "last_error": self.last_error,
            "command_ok": self.last_command_ok,
        }

    def start(self) -> dict:
        self.running = True
        self.last_command_ok = True
        return self.status()

    def stop(self) -> dict:
        self.running = False
        self.last_command_ok = True
        return self.status()

    def sort_normal(self) -> dict:
        self.sorter_position = "normal"
        self.last_command_ok = True
        return self.status()

    def sort_defect(self) -> dict:
        self.sorter_position = "defect"
        self.last_command_ok = True
        return self.status()

    def emergency_stop(self) -> dict:
        self.running = False
        self.sorter_position = "normal"
        self.last_command_ok = True
        return self.status()


class RealConveyorAdapter(MockConveyorAdapter):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str) -> bool:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=0.8) as response:
                response.read()
            self.last_error = None
            self.last_command_ok = True
            return True
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            self.last_error = str(exc)
            self.last_command_ok = False
            return False

    def _get_status(self) -> dict | None:
        try:
            with urllib.request.urlopen(f"{self.base_url}/status", timeout=0.8) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            self.last_error = str(exc)
            return None

    def status(self) -> dict:
        remote = self._get_status()
        local = super().status()
        if isinstance(remote, dict):
            local.update(remote)
            local["mode"] = settings.conveyor_mode
            local["last_error"] = None
        return local

    def start(self) -> dict:
        self.running = True
        self._post("/conveyor/start")
        return super().status()

    def stop(self) -> dict:
        self.running = False
        self._post("/conveyor/stop")
        return super().status()

    def sort_normal(self) -> dict:
        self.sorter_position = "normal"
        self._post("/sort/normal")
        return super().status()

    def sort_defect(self) -> dict:
        self.sorter_position = "defect"
        self._post("/sort/defect")
        return super().status()

    def emergency_stop(self) -> dict:
        self.running = False
        self.sorter_position = "normal"
        self._post("/emergency_stop")
        return super().status()


conveyor = RealConveyorAdapter(settings.rpi_base_url) if settings.conveyor_mode == "real" else MockConveyorAdapter()

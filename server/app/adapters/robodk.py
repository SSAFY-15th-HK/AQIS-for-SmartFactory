from app.config import settings


class MockRoboDKAdapter:
    def __init__(self) -> None:
        self.connected = True
        self.running = False

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "running": self.running,
            "mode": getattr(settings, "robot_mode", "mock"),
        }

    def start_simulation(self) -> dict:
        self.running = True
        return self.status()

    def pause_simulation(self) -> dict:
        self.running = False
        return self.status()

    def stop_simulation(self) -> dict:
        self.running = False
        return self.status()

    def reset_simulation(self) -> dict:
        self.running = False
        return self.status()

    def dispatch_agv(self) -> dict:
        return {**self.status(), "program": "agv_dispatch", "started": True}


robodk = MockRoboDKAdapter()

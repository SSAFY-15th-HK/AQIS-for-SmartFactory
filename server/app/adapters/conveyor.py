from app.config import settings


class MockConveyorAdapter:
    def __init__(self) -> None:
        self.running = False
        self.sorter_position = "normal"
        self.speed = 0.5

    def status(self) -> dict:
        return {
            "running": self.running,
            "mode": settings.conveyor_mode,
            "sorter_position": self.sorter_position,
            "speed": self.speed,
        }

    def start(self) -> dict:
        self.running = True
        return self.status()

    def stop(self) -> dict:
        self.running = False
        return self.status()

    def sort_normal(self) -> dict:
        self.sorter_position = "normal"
        return self.status()

    def sort_defect(self) -> dict:
        self.sorter_position = "defect"
        return self.status()


conveyor = MockConveyorAdapter()

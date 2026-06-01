import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    conveyor_mode: str = os.getenv("CONVEYOR_MODE", "mock")
    vision_mode: str = os.getenv("VISION_MODE", "mock")
    robot_mode: str = os.getenv("ROBOT_MODE", "mock")
    voice_mode: str = os.getenv("VOICE_MODE", "text")
    defect_count_threshold: int = int(os.getenv("DEFECT_COUNT_THRESHOLD", "5"))
    rpi_base_url: str = os.getenv("RPI_BASE_URL", "http://192.168.0.10:5000")
    mjpeg_stream_url: str = os.getenv("MJPEG_STREAM_URL", "http://localhost:8080/stream")

    @property
    def mode(self) -> dict[str, str]:
        return {
            "conveyor": self.conveyor_mode,
            "vision": self.vision_mode,
            "robot": self.robot_mode,
            "voice": self.voice_mode,
        }


settings = Settings()

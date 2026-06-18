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
    realsense_stream_url: str = os.getenv("REALSENSE_STREAM_URL", os.getenv("MJPEG_STREAM_URL", "http://localhost:8080/stream"))
    turtlebot_view_url: str = os.getenv("TURTLEBOT_VIEW_URL", "http://localhost:8081/stream")
    ros_enabled: bool = os.getenv("ROS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    ros_domain_id: str = os.getenv("ROS_DOMAIN_ID", "42")
    turtlebot_namespace: str = os.getenv("TURTLEBOT_NAMESPACE", "")
    aqis_start_command: str = os.getenv(
        "AQIS_START_COMMAND",
        "source /opt/ros/humble/setup.bash && "
        "source /home/ssafy/magician_ros2_control_system_ws/install/setup.bash && "
        "source /home/ssafy/ssafy_ws/install/setup.bash && "
        "ros2 launch integrate_prac integrate.launch.py",
    )
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "Qwen3.6-35B-A3B-UD-IQ2_M")
    llm_timeout_sec: float = float(os.getenv("LLM_TIMEOUT_SEC", "8"))

    @property
    def mode(self) -> dict[str, str]:
        return {
            "conveyor": self.conveyor_mode,
            "vision": self.vision_mode,
            "robot": self.robot_mode,
            "voice": self.voice_mode,
            "ros": "enabled" if self.ros_enabled else "disabled",
        }


settings = Settings()

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
    rpi_base_url: str = os.getenv("RPI_BASE_URL", "http://192.168.0.10:5000")
    mjpeg_stream_url: str = os.getenv("MJPEG_STREAM_URL", "http://localhost:8080/stream")
    realsense_stream_url: str = os.getenv("REALSENSE_STREAM_URL", os.getenv("MJPEG_STREAM_URL", "http://localhost:8080/stream"))
    turtlebot_view_url: str = os.getenv("TURTLEBOT_VIEW_URL", "http://localhost:8081/stream")
    ros_enabled: bool = os.getenv("ROS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    ros_domain_id: str = os.getenv("ROS_DOMAIN_ID", "42")
    turtlebot_namespace: str = os.getenv("TURTLEBOT_NAMESPACE", "")
    aqis_start_command: str = os.getenv(
        "AQIS_START_COMMAND",
        "bash ../AQIS-real/scripts/monitoring_session.sh",
    )
    dobot_pick_place_command: str = os.getenv(
        "DOBOT_PICK_PLACE_COMMAND",
        "python3 ../AQIS-real/scripts/dobot_pick_place_once.py",
    )
    dobot_pick_x: float = float(os.getenv("DOBOT_PICK_X", "125.0"))
    dobot_pick_y: float = float(os.getenv("DOBOT_PICK_Y", "-180.0"))
    dobot_pick_z: float = float(os.getenv("DOBOT_PICK_Z", "30.0"))
    dobot_place_x: float = float(os.getenv("DOBOT_PLACE_X", "150.0"))
    dobot_place_y: float = float(os.getenv("DOBOT_PLACE_Y", "190.0"))
    dobot_place_z: float = float(os.getenv("DOBOT_PLACE_Z", "20.0"))
    dobot_safe_z: float = float(os.getenv("DOBOT_SAFE_Z", "60.0"))
    dobot_home_x: float = float(os.getenv("DOBOT_HOME_X", "200.0"))
    dobot_home_y: float = float(os.getenv("DOBOT_HOME_Y", "0.0"))
    dobot_home_z: float = float(os.getenv("DOBOT_HOME_Z", "100.0"))
    dobot_tool_r: float = float(os.getenv("DOBOT_TOOL_R", "0.0"))
    dobot_motion_type: int = int(os.getenv("DOBOT_MOTION_TYPE", "1"))
    dobot_velocity_ratio: float = float(os.getenv("DOBOT_VELOCITY_RATIO", "1.0"))
    dobot_acceleration_ratio: float = float(os.getenv("DOBOT_ACCELERATION_RATIO", "1.0"))
    dobot_suction_settle_sec: float = float(os.getenv("DOBOT_SUCTION_SETTLE_SEC", "0.35"))
    dobot_resume_conveyor_after_pick: bool = os.getenv("DOBOT_RESUME_CONVEYOR_AFTER_PICK", "true").lower() in {"1", "true", "yes", "on"}
    dobot_pick_after_stop_delay_sec: float = float(os.getenv("DOBOT_PICK_AFTER_STOP_DELAY_SEC", "0.6"))
    dobot_pick_max_detection_age_sec: float = float(os.getenv("DOBOT_PICK_MAX_DETECTION_AGE_SEC", "3.0"))
    dobot_dynamic_pick_enabled: bool = os.getenv("DOBOT_DYNAMIC_PICK_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    dobot_dynamic_pick_z: float = float(os.getenv("DOBOT_DYNAMIC_PICK_Z", "-5.8"))
    dobot_dynamic_tool_r: float = float(os.getenv("DOBOT_DYNAMIC_TOOL_R", "7.0"))
    dobot_dynamic_pick_offset_x_mm: float = float(os.getenv("DOBOT_DYNAMIC_PICK_OFFSET_X_MM", "0.0"))
    dobot_dynamic_pick_offset_y_mm: float = float(os.getenv("DOBOT_DYNAMIC_PICK_OFFSET_Y_MM", "0.0"))
    dobot_dynamic_pick_offset_z_mm: float = float(os.getenv("DOBOT_DYNAMIC_PICK_OFFSET_Z_MM", "0.0"))
    dobot_camera_to_dobot_x_cam_x: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_X_CAM_X", "0.054765711"))
    dobot_camera_to_dobot_x_cam_y: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_X_CAM_Y", "0.911088412"))
    dobot_camera_to_dobot_x_bias: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_X_BIAS", "0.233068744"))
    dobot_camera_to_dobot_y_cam_x: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_Y_CAM_X", "0.833403365"))
    dobot_camera_to_dobot_y_cam_y: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_Y_CAM_Y", "-0.053993911"))
    dobot_camera_to_dobot_y_bias: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_Y_BIAS", "0.025758307"))
    dobot_dynamic_z_enabled: bool = os.getenv("DOBOT_DYNAMIC_Z_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    dobot_camera_to_dobot_z_cam_x: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_Z_CAM_X", "-0.02862024"))
    dobot_camera_to_dobot_z_cam_y: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_Z_CAM_Y", "0.05172572"))
    dobot_camera_to_dobot_z_bias: float = float(os.getenv("DOBOT_CAMERA_TO_DOBOT_Z_BIAS", "-0.00744611"))
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "Qwen3.6-35B-A3B-UD-IQ2_M")
    llm_timeout_sec: float = float(os.getenv("LLM_TIMEOUT_SEC", "8"))
    detection_dedupe_window_sec: float = float(os.getenv("DETECTION_DEDUPE_WINDOW_SEC", "8.0"))
    detection_dedupe_iou_threshold: float = float(os.getenv("DETECTION_DEDUPE_IOU_THRESHOLD", "0.5"))
    detection_dedupe_center_distance_px: float = float(os.getenv("DETECTION_DEDUPE_CENTER_DISTANCE_PX", "70"))

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

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.ros_converters import (
    alarms_to_partial,
    dobot_status_event,
    gripper_to_partial,
    joint_state_to_dobot_partial,
    occupancy_grid_to_event,
    pose_to_turtlebot_event,
    raw_pose_to_partial,
    tcp_pose_to_partial,
)

Broadcast = Callable[[dict], Awaitable[None]]
DetectionHandler = Callable[[dict], list[dict]]


class RosBridgeService:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.available = False
        self.running = False
        self.error: str | None = None
        self.latest_turtlebot_pose: dict | None = None
        self.latest_dobot_status: dict = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broadcast: Broadcast | None = None
        self._detection_handler: DetectionHandler | None = None
        self._thread: threading.Thread | None = None
        self._node: Any = None
        self._executor: Any = None
        self._rclpy: Any = None

    def start(self, broadcast: Broadcast, detection_handler: DetectionHandler | None = None) -> None:
        if not self.enabled or self.running:
            return

        self._loop = asyncio.get_running_loop()
        self._broadcast = broadcast
        self._detection_handler = detection_handler
        self._thread = threading.Thread(target=self._run, name="aqis-ros-bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        try:
            if self._executor:
                self._executor.shutdown()
            if self._node:
                self._node.destroy_node()
            if self._rclpy and self._rclpy.ok():
                self._rclpy.shutdown()
        except Exception as exc:
            self.error = str(exc)

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "available": self.available,
            "running": self.running,
            "error": self.error,
            "turtlebot_pose": self.latest_turtlebot_pose,
            "dobot_status": self.latest_dobot_status,
        }

    def _run(self) -> None:
        try:
            import rclpy
            from geometry_msgs.msg import PoseWithCovarianceStamped
            from nav_msgs.msg import OccupancyGrid, Odometry
            from rclpy.executors import MultiThreadedExecutor
            from sensor_msgs.msg import JointState
            from std_msgs.msg import Float64MultiArray, String

            from dobot_msgs.msg import DobotAlarmCodes, GripperStatus
            from geometry_msgs.msg import PoseStamped
        except Exception as exc:
            self.available = False
            self.running = False
            self.error = f"ROS imports failed: {exc}"
            return

        self._rclpy = rclpy
        try:
            rclpy.init(args=None)
            self._node = rclpy.create_node("aqis_web_bridge")
            self._executor = MultiThreadedExecutor()
            self._executor.add_node(self._node)

            self._node.create_subscription(OccupancyGrid, "/map", self._on_map, 10)
            self._node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl_pose, 10)
            self._node.create_subscription(Odometry, "/odom", self._on_odom, 10)
            self._node.create_subscription(String, "/defect/detection", self._on_detection, 10)
            self._node.create_subscription(JointState, "/dobot_joint_states", self._on_dobot_joints, 10)
            self._node.create_subscription(PoseStamped, "/dobot_TCP", self._on_dobot_tcp, 10)
            self._node.create_subscription(Float64MultiArray, "/dobot_pose_raw", self._on_dobot_raw, 10)
            self._node.create_subscription(DobotAlarmCodes, "/dobot_alarms", self._on_dobot_alarms, 10)
            self._node.create_subscription(GripperStatus, "/gripper_status_rviz", self._on_gripper, 10)

            self.available = True
            self.running = True
            self.error = None
            self._executor.spin()
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.running = False

    def _schedule(self, event: dict) -> None:
        if not self._loop or not self._broadcast:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(event), self._loop)

    def _on_map(self, msg: Any) -> None:
        self._schedule(occupancy_grid_to_event(msg))

    def _on_amcl_pose(self, msg: Any) -> None:
        event = pose_to_turtlebot_event(msg, "amcl_pose")
        self.latest_turtlebot_pose = event["data"]
        self._schedule(event)

    def _on_odom(self, msg: Any) -> None:
        if self.latest_turtlebot_pose and self.latest_turtlebot_pose.get("source") == "amcl_pose":
            return
        event = pose_to_turtlebot_event(msg, "odom")
        self.latest_turtlebot_pose = event["data"]
        self._schedule(event)

    def _on_detection(self, msg: Any) -> None:
        try:
            payload = json.loads(msg.data)
        except Exception:
            payload = {"raw": str(getattr(msg, "data", "")), "is_defect": False}

        if self._detection_handler:
            for event in self._detection_handler(payload):
                self._schedule(event)

    def _merge_dobot(self, partial: dict) -> None:
        self.latest_dobot_status = {**self.latest_dobot_status, **partial}
        self._schedule(dobot_status_event(self.latest_dobot_status))

    def _on_dobot_joints(self, msg: Any) -> None:
        self._merge_dobot(joint_state_to_dobot_partial(msg))

    def _on_dobot_tcp(self, msg: Any) -> None:
        self._merge_dobot(tcp_pose_to_partial(msg))

    def _on_dobot_raw(self, msg: Any) -> None:
        self._merge_dobot(raw_pose_to_partial(msg))

    def _on_dobot_alarms(self, msg: Any) -> None:
        self._merge_dobot(alarms_to_partial(msg))

    def _on_gripper(self, msg: Any) -> None:
        self._merge_dobot(gripper_to_partial(msg))

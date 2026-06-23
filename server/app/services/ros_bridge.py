from __future__ import annotations

import asyncio
import json
import threading
import time
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
    transform_to_turtlebot_event,
)

Broadcast = Callable[[dict], Awaitable[None]]
DetectionHandler = Callable[[dict], list[dict]]


class RosBridgeService:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.available = False
        self.running = False
        self.error: str | None = None
        self.latest_map_event: dict | None = None
        self.latest_turtlebot_pose: dict | None = None
        self.latest_dobot_status: dict = {}
        self._last_map_broadcast_at = 0.0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broadcast: Broadcast | None = None
        self._detection_handler: DetectionHandler | None = None
        self._thread: threading.Thread | None = None
        self._node: Any = None
        self._executor: Any = None
        self._rclpy: Any = None
        self._tf_buffer: Any = None
        self._tf_listener: Any = None
        self._tf_time_cls: Any = None
        self._tf_exception_cls: Any = None

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
        map_data = self.latest_map_event["data"] if self.latest_map_event else None
        return {
            "enabled": self.enabled,
            "available": self.available,
            "running": self.running,
            "error": self.error,
            "map": (
                {
                    key: value
                    for key, value in map_data.items()
                    if key != "image"
                }
                if map_data
                else None
            ),
            "turtlebot_pose": self.latest_turtlebot_pose,
            "dobot_status": self.latest_dobot_status,
        }

    def _run(self) -> None:
        try:
            import rclpy
            from geometry_msgs.msg import PoseWithCovarianceStamped
            from nav_msgs.msg import OccupancyGrid, Odometry
            from rclpy.executors import MultiThreadedExecutor
            from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
            from rclpy.time import Time
            from sensor_msgs.msg import JointState
            from std_msgs.msg import Float64MultiArray, String
            from tf2_ros import Buffer, TransformException, TransformListener

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
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, self._node)
            self._tf_time_cls = Time
            self._tf_exception_cls = TransformException

            transient_map_qos = QoSProfile(
                depth=1,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
                reliability=ReliabilityPolicy.RELIABLE,
            )
            self._node.create_subscription(OccupancyGrid, "/map", self._on_map, 10)
            self._node.create_subscription(OccupancyGrid, "/map", self._on_map, transient_map_qos)
            self._node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl_pose, 10)
            self._node.create_subscription(Odometry, "/odom", self._on_odom, 10)
            self._node.create_subscription(String, "/defect/detection", self._on_detection, 10)
            self._node.create_subscription(JointState, "/dobot_joint_states", self._on_dobot_joints, 10)
            self._node.create_subscription(PoseStamped, "/dobot_TCP", self._on_dobot_tcp, 10)
            self._node.create_subscription(Float64MultiArray, "/dobot_pose_raw", self._on_dobot_raw, 10)
            self._node.create_subscription(DobotAlarmCodes, "/dobot_alarms", self._on_dobot_alarms, 10)
            self._node.create_subscription(GripperStatus, "/gripper_status_rviz", self._on_gripper, 10)
            self._node.create_timer(0.1, self._on_tf_pose_timer)

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
        event = occupancy_grid_to_event(msg)
        self.latest_map_event = event
        now = time.time()
        if now - self._last_map_broadcast_at < 2.0:
            return
        self._last_map_broadcast_at = now
        self._schedule(event)

    def _on_amcl_pose(self, msg: Any) -> None:
        if self._has_fresh_tf_pose():
            return
        event = pose_to_turtlebot_event(msg, "amcl_pose")
        self.latest_turtlebot_pose = event["data"]
        self._schedule(event)

    def _on_odom(self, msg: Any) -> None:
        if self._has_fresh_tf_pose():
            return
        if (
            self.latest_turtlebot_pose
            and self.latest_turtlebot_pose.get("source") == "amcl_pose"
            and time.time() - float(self.latest_turtlebot_pose.get("stamp", 0)) < 2.5
        ):
            return
        event = pose_to_turtlebot_event(msg, "odom")
        self.latest_turtlebot_pose = event["data"]
        self._schedule(event)

    def _has_fresh_tf_pose(self) -> bool:
        return bool(
            self.latest_turtlebot_pose
            and self.latest_turtlebot_pose.get("source") in {"tf_map_base_footprint", "tf_map_base_link"}
            and time.time() - float(self.latest_turtlebot_pose.get("stamp", 0)) < 0.8
        )

    def _on_tf_pose_timer(self) -> None:
        if not self._tf_buffer:
            return
        for child_frame in ("base_footprint", "base_link"):
            try:
                transform = self._tf_buffer.lookup_transform("map", child_frame, self._tf_time_cls())
            except Exception as exc:
                if self._tf_exception_cls and isinstance(exc, self._tf_exception_cls):
                    continue
                continue
            event = transform_to_turtlebot_event(transform, f"tf_map_{child_frame}")
            self.latest_turtlebot_pose = event["data"]
            self._schedule(event)
            return

    def _on_detection(self, msg: Any) -> None:
        try:
            payload = json.loads(msg.data)
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        if self._detection_handler:
            try:
                events = self._detection_handler(payload)
            except Exception as exc:
                self.error = f"detection handler failed: {exc}"
                return
            for event in events:
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

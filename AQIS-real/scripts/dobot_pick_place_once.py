#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import sys
import time

import rclpy
from action_msgs.msg import GoalStatus
from dobot_msgs.action import PointToPoint
from dobot_msgs.srv import SuctionCupControl
from rclpy.action import ActionClient
from rclpy.node import Node


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class DobotPickPlaceOnce(Node):
    def __init__(self) -> None:
        super().__init__("aqis_dobot_pick_place_once")
        self.ptp = ActionClient(self, PointToPoint, "PTP_action")
        self.suction = self.create_client(SuctionCupControl, "dobot_suction_cup_service")
        self.motion_type = env_int("DOBOT_MOTION_TYPE", 1)
        self.velocity_ratio = env_float("DOBOT_VELOCITY_RATIO", 1.0)
        self.acceleration_ratio = env_float("DOBOT_ACCELERATION_RATIO", 1.0)
        self.suction_settle_sec = env_float("DOBOT_SUCTION_SETTLE_SEC", 0.35)
        self.current_goal_handle = None
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True
        try:
            if self.current_goal_handle is not None:
                cancel_future = self.current_goal_handle.cancel_goal_async()
                rclpy.spin_until_future_complete(self, cancel_future, timeout_sec=1.0)
            self.set_suction(False)
        except Exception as exc:
            self.get_logger().warning(f"Cleanup after stop failed: {exc}")

    def run(self) -> bool:
        pick_x = env_float("DOBOT_PICK_X", 125.0)
        pick_y = env_float("DOBOT_PICK_Y", -180.0)
        pick_z = env_float("DOBOT_PICK_Z", 30.0)
        place_x = env_float("DOBOT_PLACE_X", 150.0)
        place_y = env_float("DOBOT_PLACE_Y", 190.0)
        place_z = env_float("DOBOT_PLACE_Z", 20.0)
        safe_z = env_float("DOBOT_SAFE_Z", 60.0)
        home_x = env_float("DOBOT_HOME_X", 200.0)
        home_y = env_float("DOBOT_HOME_Y", 0.0)
        home_z = env_float("DOBOT_HOME_Z", 100.0)
        tool_r = env_float("DOBOT_TOOL_R", 0.0)

        tasks = [
            ("move", [pick_x, pick_y, safe_z, tool_r]),
            ("suction", False),
            ("move", [pick_x, pick_y, pick_z, tool_r]),
            ("suction", True),
            ("move", [pick_x, pick_y, safe_z, tool_r]),
            ("move", [place_x, place_y, safe_z, tool_r]),
            ("move", [place_x, place_y, place_z, tool_r]),
            ("suction", False),
            ("move", [place_x, place_y, safe_z, tool_r]),
            ("move", [home_x, home_y, home_z, tool_r]),
        ]

        if not self.ptp.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("PTP_action server is not available")
            return False
        if not self.suction.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("dobot_suction_cup_service is not available")
            return False

        for index, task in enumerate(tasks):
            if self.stop_requested:
                return False
            kind, value = task
            self.get_logger().info(f"Task {index + 1}/{len(tasks)}: {kind} {value}")
            ok = self.move(value) if kind == "move" else self.set_suction(bool(value))
            if not ok:
                return False
        return True

    def move(self, target_pose: list[float]) -> bool:
        goal = PointToPoint.Goal()
        goal.motion_type = self.motion_type
        goal.target_pose = target_pose
        goal.velocity_ratio = self.velocity_ratio
        goal.acceleration_ratio = self.acceleration_ratio

        send_future = self.ptp.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future, timeout_sec=5.0)
        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error(f"PTP goal rejected: {target_pose}")
            return False
        self.current_goal_handle = goal_handle

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=20.0)
        self.current_goal_handle = None
        result = result_future.result()
        if result is None or result.status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(f"PTP goal failed: {target_pose}")
            return False
        return True

    def set_suction(self, enabled: bool) -> bool:
        request = SuctionCupControl.Request()
        request.enable_suction = enabled
        future = self.suction.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        result = future.result()
        if result is None or not result.success:
            message = result.message if result is not None else "no service response"
            self.get_logger().error(f"Suction command failed: {message}")
            return False
        time.sleep(self.suction_settle_sec)
        return True


def main() -> int:
    rclpy.init(args=None)
    node = DobotPickPlaceOnce()

    def handle_signal(signum, frame) -> None:
        node.get_logger().warning(f"Received signal {signum}; stopping Dobot pick/place")
        node.request_stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    try:
        return 0 if node.run() else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())

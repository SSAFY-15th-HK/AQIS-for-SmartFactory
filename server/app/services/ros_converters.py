from __future__ import annotations

import base64
import math
import struct
import time
import zlib
from collections.abc import Sequence
from typing import Any


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def grayscale_png_base64(width: int, height: int, pixels: Sequence[int]) -> str:
    rows = bytearray()
    for row in range(height):
        rows.append(0)
        offset = row * width
        rows.extend(int(max(0, min(255, pixels[offset + col]))) for col in range(width))

    png = b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(bytes(rows), 9)),
            _chunk(b"IEND", b""),
        ]
    )
    return base64.b64encode(png).decode("ascii")


def occupancy_value_to_gray(value: int) -> int:
    if value < 0:
        return 190
    if value >= 65:
        return 36
    if value <= 20:
        return 245
    return 130


def occupancy_grid_to_event(msg: Any) -> dict:
    width = int(msg.info.width)
    height = int(msg.info.height)
    pixels = [occupancy_value_to_gray(int(value)) for value in msg.data]
    image = grayscale_png_base64(width, height, pixels)
    origin = msg.info.origin
    return {
        "type": "map_update",
        "data": {
            "image": f"data:image/png;base64,{image}",
            "width": width,
            "height": height,
            "resolution": float(msg.info.resolution),
            "origin": {
                "x": float(origin.position.x),
                "y": float(origin.position.y),
                "yaw": quaternion_to_yaw(origin.orientation),
            },
            "stamp": time.time(),
        },
    }


def quaternion_to_yaw(q: Any) -> float:
    siny_cosp = 2.0 * (float(q.w) * float(q.z) + float(q.x) * float(q.y))
    cosy_cosp = 1.0 - 2.0 * (float(q.y) * float(q.y) + float(q.z) * float(q.z))
    return math.atan2(siny_cosp, cosy_cosp)


def pose_to_turtlebot_event(msg: Any, source: str) -> dict:
    pose = getattr(msg, "pose", msg)
    if hasattr(pose, "pose"):
        pose = pose.pose
    if hasattr(pose, "pose"):
        pose = pose.pose

    return {
        "type": "turtlebot_pose",
        "data": {
            "source": source,
            "x": float(pose.position.x),
            "y": float(pose.position.y),
            "z": float(getattr(pose.position, "z", 0.0)),
            "yaw": quaternion_to_yaw(pose.orientation),
            "stamp": time.time(),
        },
    }


def joint_state_to_dobot_partial(msg: Any) -> dict:
    names = list(getattr(msg, "name", []))
    positions = list(getattr(msg, "position", []))
    velocities = list(getattr(msg, "velocity", []))
    efforts = list(getattr(msg, "effort", []))

    joints = []
    for index, name in enumerate(names):
        position = float(positions[index]) if index < len(positions) else 0.0
        joint = {
            "name": str(name),
            "position_rad": position,
            "position_deg": round(math.degrees(position), 3),
        }
        if index < len(velocities):
            joint["velocity"] = float(velocities[index])
        if index < len(efforts):
            joint["effort"] = float(efforts[index])
        joints.append(joint)

    return {"joints": joints, "stamp": time.time()}


def tcp_pose_to_partial(msg: Any) -> dict:
    pose = msg.pose
    return {
        "tcp_pose": {
            "x": float(pose.position.x),
            "y": float(pose.position.y),
            "z": float(pose.position.z),
            "yaw": quaternion_to_yaw(pose.orientation),
        },
        "stamp": time.time(),
    }


def raw_pose_to_partial(msg: Any) -> dict:
    data = list(getattr(msg, "data", []))
    return {
        "raw_pose": {
            "x": float(data[0]) if len(data) > 0 else None,
            "y": float(data[1]) if len(data) > 1 else None,
            "z": float(data[2]) if len(data) > 2 else None,
            "r": float(data[3]) if len(data) > 3 else None,
        },
        "stamp": time.time(),
    }


def alarms_to_partial(msg: Any) -> dict:
    return {"alarms": [int(code) for code in getattr(msg, "alarms_list", [])], "stamp": time.time()}


def gripper_to_partial(msg: Any) -> dict:
    return {"gripper_status": str(getattr(msg, "status", "unknown")), "stamp": time.time()}


def dobot_status_event(state: dict) -> dict:
    return {"type": "dobot_status", "data": {**state, "stamp": time.time()}}

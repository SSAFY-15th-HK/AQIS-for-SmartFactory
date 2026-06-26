import json
import os
import time
from collections import Counter, deque
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import cv2
import numpy as np
import rclpy
import torch
from cv_bridge import CvBridge
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String


class RealsenseYoloNode(Node):
    def __init__(self):
        super().__init__("realsense_yolo_node")

        self.declare_parameter("image_topic", "/camera/camera/color/image_raw")
        self.declare_parameter("depth_topic", "/camera/camera/aligned_depth_to_color/image_raw")
        self.declare_parameter("camera_info_topic", "/camera/camera/color/camera_info")
        self.declare_parameter("annotated_image_topic", "/detection_image")
        self.declare_parameter("legacy_results_topic", "/detection_results")
        self.declare_parameter("defect_detection_topic", "/defect/detection")
        self.declare_parameter("model_path", self.default_model_path())
        self.declare_parameter("yolov5_repo", os.getenv("AQIS_YOLOV5_REPO", str(Path.home() / "yolov5")))
        self.declare_parameter("confidence", 0.7)
        self.declare_parameter("defect_labels", "board panel,canlid_defective,canlid defective,canlid_abnormal,red,defect,abnormal,scratch,dent,crack")
        self.declare_parameter("normal_labels", "back panel,canlid_normal,canlid normal,blue,green,white,normal")
        self.declare_parameter("buffer_size", 12)
        self.declare_parameter("stable_threshold", 6)
        self.declare_parameter("event_cooldown_sec", 2.0)
        self.declare_parameter("max_inference_hz", 8.0)
        self.declare_parameter("roi_enabled", True)
        self.declare_parameter("roi_x_min", -1)
        self.declare_parameter("roi_y_min", -1)
        self.declare_parameter("roi_x_max", -1)
        self.declare_parameter("roi_y_max", -1)
        self.declare_parameter("roi_width", 220)
        self.declare_parameter("roi_height", 180)

        self.image_topic = self.get_parameter("image_topic").value
        self.depth_topic = self.get_parameter("depth_topic").value
        self.camera_info_topic = self.get_parameter("camera_info_topic").value
        self.annotated_image_topic = self.get_parameter("annotated_image_topic").value
        self.legacy_results_topic = self.get_parameter("legacy_results_topic").value
        self.defect_detection_topic = self.get_parameter("defect_detection_topic").value
        self.model_path = self.get_parameter("model_path").value
        self.yolov5_repo = self.get_parameter("yolov5_repo").value
        self.confidence = float(self.get_parameter("confidence").value)
        self.defect_labels = self.parse_label_set(self.get_parameter("defect_labels").value)
        self.normal_labels = self.parse_label_set(self.get_parameter("normal_labels").value)
        self.buffer_size = int(self.get_parameter("buffer_size").value)
        self.stable_threshold = int(self.get_parameter("stable_threshold").value)
        self.event_cooldown_sec = float(self.get_parameter("event_cooldown_sec").value)
        self.max_inference_hz = float(self.get_parameter("max_inference_hz").value)
        self.roi_enabled = self.parse_bool(self.get_parameter("roi_enabled").value)
        self.roi_x_min = int(self.get_parameter("roi_x_min").value)
        self.roi_y_min = int(self.get_parameter("roi_y_min").value)
        self.roi_x_max = int(self.get_parameter("roi_x_max").value)
        self.roi_y_max = int(self.get_parameter("roi_y_max").value)
        self.roi_width = int(self.get_parameter("roi_width").value)
        self.roi_height = int(self.get_parameter("roi_height").value)

        self.bridge = CvBridge()
        self.latest_depth = None
        self.latest_depth_encoding = ""
        self.fx = None
        self.fy = None
        self.cx = None
        self.cy = None
        self.frame_id = 0
        self.last_inference_at = 0.0
        self.last_event_at = 0.0
        self.last_event_key = ""
        self.detection_buffer = deque(maxlen=self.buffer_size)

        self.model = torch.hub.load(
            self.yolov5_repo,
            "custom",
            path=self.model_path,
            source="local",
        )
        self.model.conf = self.confidence

        self.image_subscriber = self.create_subscription(Image, self.image_topic, self.image_callback, 10)
        self.depth_subscriber = self.create_subscription(Image, self.depth_topic, self.depth_callback, 10)
        self.camera_info_subscriber = self.create_subscription(CameraInfo, self.camera_info_topic, self.camera_info_callback, 10)
        self.annotated_image_publisher = self.create_publisher(Image, self.annotated_image_topic, 10)
        self.legacy_results_publisher = self.create_publisher(String, self.legacy_results_topic, 10)
        self.defect_detection_publisher = self.create_publisher(String, self.defect_detection_topic, 10)

        self.get_logger().info(f"Loaded YOLO model: {self.model_path}")
        self.get_logger().info(f"Loaded YOLO classes: {self.model.names}")
        self.get_logger().info(f"Subscribing image: {self.image_topic}")
        self.get_logger().info(f"Subscribing depth: {self.depth_topic}")
        self.get_logger().info(f"Subscribing camera info: {self.camera_info_topic}")
        self.get_logger().info(f"Publishing annotated image: {self.annotated_image_topic}")
        self.get_logger().info(f"Publishing conveyor-compatible labels: {self.legacy_results_topic}")
        self.get_logger().info(f"Publishing web/backend detections: {self.defect_detection_topic}")
        self.get_logger().info(
            "ROI filtering: "
            f"enabled={self.roi_enabled}, "
            f"explicit=({self.roi_x_min}, {self.roi_y_min}, {self.roi_x_max}, {self.roi_y_max}), "
            f"center_size=({self.roi_width}x{self.roi_height})"
        )

    def default_model_path(self):
        try:
            package_model = str(Path(get_package_share_directory("integrate_prac")) / "models" / "best.pt")
        except Exception:
            package_model = ""
        candidates = [
            os.getenv("AQIS_YOLO_MODEL", ""),
            package_model,
            str(Path.cwd() / "models" / "best.pt"),
            str(Path.cwd() / "best.pt"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        return package_model or candidates[-1]

    def parse_label_set(self, value):
        return {item.strip().lower() for item in str(value).split(",") if item.strip()}

    def parse_bool(self, value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def depth_callback(self, msg):
        try:
            self.latest_depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            self.latest_depth_encoding = msg.encoding
        except Exception as exc:
            self.get_logger().error(f"Failed to convert depth image: {exc}")

    def camera_info_callback(self, msg):
        self.fx = float(msg.k[0])
        self.fy = float(msg.k[4])
        self.cx = float(msg.k[2])
        self.cy = float(msg.k[5])

    def image_callback(self, msg):
        now = time.time()
        min_interval = 1.0 / self.max_inference_hz if self.max_inference_hz > 0 else 0.0
        if now - self.last_inference_at < min_interval:
            return
        self.last_inference_at = now
        self.frame_id += 1

        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as exc:
            self.get_logger().error(f"Failed to convert image: {exc}")
            return

        roi = self.resolve_roi(cv_image)
        detections = self.detect(cv_image, roi)
        self.add_depth_positions(detections, cv_image.shape[1], cv_image.shape[0])
        self.publish_legacy_results(detections)
        self.publish_annotated_image(cv_image)
        self.maybe_publish_defect_event(detections, msg)

    def resolve_roi(self, cv_image):
        height, width = cv_image.shape[:2]
        if not self.roi_enabled:
            return (0, 0, width - 1, height - 1)

        has_explicit_roi = min(self.roi_x_min, self.roi_y_min, self.roi_x_max, self.roi_y_max) >= 0
        if has_explicit_roi:
            x_min = self.roi_x_min
            y_min = self.roi_y_min
            x_max = self.roi_x_max
            y_max = self.roi_y_max
        else:
            roi_width = min(max(1, self.roi_width), width)
            roi_height = min(max(1, self.roi_height), height)
            x_min = int((width - roi_width) / 2)
            y_min = int((height - roi_height) / 2)
            x_max = x_min + roi_width
            y_max = y_min + roi_height

        x_min = max(0, min(width - 1, int(x_min)))
        y_min = max(0, min(height - 1, int(y_min)))
        x_max = max(x_min + 1, min(width, int(x_max)))
        y_max = max(y_min + 1, min(height, int(y_max)))
        return (x_min, y_min, x_max, y_max)

    def center_in_roi(self, center_x, center_y, roi):
        x_min, y_min, x_max, y_max = roi
        return x_min <= center_x <= x_max and y_min <= center_y <= y_max

    def draw_roi(self, cv_image, roi):
        if not self.roi_enabled:
            return
        x_min, y_min, x_max, y_max = roi
        cv2.rectangle(cv_image, (x_min, y_min), (x_max, y_max), (0, 200, 255), 2)
        cv2.putText(
            cv_image,
            "PICK ROI",
            (x_min, max(20, y_min - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 200, 255),
            2,
        )

    def detect(self, cv_image, roi):
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        results = self.model(rgb_image)
        rows = results.pandas().xyxy[0]
        detections = []
        self.draw_roi(cv_image, roi)

        for _, row in rows.iterrows():
            label = str(row["name"])
            confidence = float(row["confidence"])
            xmin = int(row["xmin"])
            ymin = int(row["ymin"])
            xmax = int(row["xmax"])
            ymax = int(row["ymax"])
            center_x = int((xmin + xmax) / 2)
            center_y = int((ymin + ymax) / 2)
            label_key = label.lower()
            is_defect = label_key in self.defect_labels and label_key not in self.normal_labels
            roi_hit = self.center_in_roi(center_x, center_y, roi)

            detection = {
                "label": label,
                "confidence": round(confidence, 4),
                "bbox_xyxy": [xmin, ymin, xmax, ymax],
                "bbox": [xmin, ymin, xmax - xmin, ymax - ymin],
                "center": [center_x, center_y],
                "is_defect": is_defect,
                "roi_hit": roi_hit,
                "roi": list(roi),
            }

            if roi_hit:
                detections.append(detection)

            color = (0, 0, 255) if is_defect else (0, 180, 0)
            if not roi_hit:
                color = (150, 150, 150)
            cv2.rectangle(cv_image, (xmin, ymin), (xmax, ymax), color, 2)
            cv2.circle(cv_image, (center_x, center_y), 4, (255, 255, 255), -1)
            label_text = f"{label} {confidence:.2f}" if roi_hit else f"{label} {confidence:.2f} ignored"
            cv2.putText(
                cv_image,
                label_text,
                (xmin, max(20, ymin - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

        return detections

    def add_depth_positions(self, detections, image_width, image_height):
        for detection in detections:
            detection["has_depth"] = False
            depth_result = self.depth_at_color_center(detection["center"], image_width, image_height)
            if depth_result is None:
                continue

            depth_x, depth_y, depth_m = depth_result
            detection["depth_center"] = [depth_x, depth_y]
            detection["depth_m"] = round(float(depth_m), 4)

            camera_point = self.deproject_pixel(depth_x, depth_y, depth_m)
            if camera_point is None:
                continue

            detection["has_depth"] = True
            detection["camera_point_m"] = [round(float(value), 4) for value in camera_point]

    def depth_at_color_center(self, center, image_width, image_height):
        if self.latest_depth is None:
            return None

        depth = self.latest_depth
        depth_height, depth_width = depth.shape[:2]
        center_x, center_y = center
        depth_x = int(round(center_x * depth_width / max(1, image_width)))
        depth_y = int(round(center_y * depth_height / max(1, image_height)))

        if not (0 <= depth_x < depth_width and 0 <= depth_y < depth_height):
            return None

        x1 = max(0, depth_x - 3)
        y1 = max(0, depth_y - 3)
        x2 = min(depth_width, depth_x + 4)
        y2 = min(depth_height, depth_y + 4)
        patch = depth[y1:y2, x1:x2]
        valid = patch[np.isfinite(patch) & (patch > 0)]
        if valid.size == 0:
            return None

        depth_value = float(np.median(valid))
        depth_m = depth_value / 1000.0 if self.latest_depth_encoding == "16UC1" else depth_value
        return depth_x, depth_y, depth_m

    def deproject_pixel(self, depth_x, depth_y, depth_m):
        if None in (self.fx, self.fy, self.cx, self.cy):
            return None
        if not depth_m or depth_m <= 0:
            return None
        x_m = (depth_x - self.cx) * depth_m / self.fx
        y_m = (depth_y - self.cy) * depth_m / self.fy
        return [x_m, y_m, depth_m]

    def publish_legacy_results(self, detections):
        labels = [item["label"] for item in detections]
        msg = String()
        msg.data = ", ".join(labels) if labels else "none"
        self.legacy_results_publisher.publish(msg)

    def publish_annotated_image(self, cv_image):
        try:
            msg = self.bridge.cv2_to_imgmsg(cv_image, encoding="bgr8")
            self.annotated_image_publisher.publish(msg)
        except Exception as exc:
            self.get_logger().error(f"Failed to publish annotated image: {exc}")

    def maybe_publish_defect_event(self, detections, image_msg):
        if not detections:
            self.detection_buffer.append("none")
            return

        label_keys = [str(item["label"]).lower() for item in detections]
        self.detection_buffer.extend(label_keys)
        stable_labels = {
            label
            for label, count in Counter(self.detection_buffer).items()
            if label != "none" and count >= self.stable_threshold
        }
        stable_detections = [
            item for item in detections if str(item["label"]).lower() in stable_labels
        ]
        if not stable_detections:
            return

        event_key = "|".join(
            f"{item['label']}:{item['center'][0] // 25}:{item['center'][1] // 25}"
            for item in stable_detections
        )
        now = time.time()
        if event_key == self.last_event_key and now - self.last_event_at < self.event_cooldown_sec:
            return

        self.last_event_key = event_key
        self.last_event_at = now

        payload = {
            "frame_id": self.frame_id,
            "timestamp": now,
            "source": "realsense_yolo",
            "image_size": [int(image_msg.width), int(image_msg.height)],
            "detections": [
                {
                    "label": item["label"],
                    "is_defect": bool(item["is_defect"]),
                    "result": "defect" if item["is_defect"] else "normal",
                    "defect_class": item["label"],
                    "confidence": item["confidence"],
                    "bbox": item["bbox"],
                    "center": item["center"],
                    "roi_hit": item["roi_hit"],
                    "roi": item["roi"],
                    "has_depth": item.get("has_depth", False),
                    "depth_center": item.get("depth_center"),
                    "depth_m": item.get("depth_m"),
                    "camera_point_m": item.get("camera_point_m"),
                }
                for item in stable_detections
            ],
        }

        if len(stable_detections) == 1:
            single = stable_detections[0]
            payload.update(
                {
                    "label": single["label"],
                    "is_defect": bool(single["is_defect"]),
                    "result": "defect" if single["is_defect"] else "normal",
                    "defect_class": single["label"],
                    "confidence": single["confidence"],
                    "bbox": single["bbox"],
                    "center": single["center"],
                    "roi_hit": single["roi_hit"],
                    "roi": single["roi"],
                    "has_depth": single.get("has_depth", False),
                    "depth_center": single.get("depth_center"),
                    "depth_m": single.get("depth_m"),
                    "camera_point_m": single.get("camera_point_m"),
                }
            )

        msg = String()
        msg.data = json.dumps(payload)
        self.defect_detection_publisher.publish(msg)
        self.get_logger().info(f"Published detection event: {msg.data}")


def main(args=None):
    rclpy.init(args=args)
    node = RealsenseYoloNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

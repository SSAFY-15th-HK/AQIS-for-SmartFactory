import json

import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String


class DepthPositionNode(Node):
    def __init__(self):
        super().__init__('depth_position_node')

        self.declare_parameter('detections_topic', '/yolov5_results')
        self.declare_parameter('depth_topic', '/camera/camera/aligned_depth_to_color/image_raw')
        self.declare_parameter('camera_info_topic', '/camera/camera/color/camera_info')

        detections_topic = self.get_parameter('detections_topic').value
        depth_topic = self.get_parameter('depth_topic').value
        camera_info_topic = self.get_parameter('camera_info_topic').value

        self.bridge = CvBridge()
        self.latest_depth = None
        self.latest_depth_encoding = None
        self.fx = None
        self.fy = None
        self.cx = None
        self.cy = None

        self.create_subscription(String, detections_topic, self.detections_callback, 10)
        self.create_subscription(Image, depth_topic, self.depth_callback, 10)
        self.create_subscription(CameraInfo, camera_info_topic, self.camera_info_callback, 10)
        self.position_publisher = self.create_publisher(String, '/detected_objects_3d', 10)

        self.get_logger().info(
            'Depth position node started:\n'
            f'  detections = {detections_topic}\n'
            f'  depth      = {depth_topic}\n'
            f'  cameraInfo = {camera_info_topic}'
        )

    def depth_callback(self, msg):
        try:
            self.latest_depth = self.bridge.imgmsg_to_cv2(msg, desired_encoding='passthrough')
            self.latest_depth_encoding = msg.encoding
        except Exception as e:
            self.get_logger().error(f'Failed to convert depth image: {e}')

    def camera_info_callback(self, msg):
        self.fx = msg.k[0]
        self.fy = msg.k[4]
        self.cx = msg.k[2]
        self.cy = msg.k[5]

    def detections_callback(self, msg):
        if self.latest_depth is None:
            self.get_logger().warn('No depth image received yet.')
            return
        if None in (self.fx, self.fy, self.cx, self.cy):
            self.get_logger().warn('No camera info received yet.')
            return

        try:
            detections = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'Failed to parse YOLO detections JSON: {e}')
            return

        objects_3d = []
        for detection in detections:
            center_x = int(detection['center_x'])
            center_y = int(detection['center_y'])
            depth_m = self.sample_depth_m(center_x, center_y)
            if depth_m is None:
                continue

            x_m = (center_x - self.cx) * depth_m / self.fx
            y_m = (center_y - self.cy) * depth_m / self.fy

            objects_3d.append({
                'label': detection['label'],
                'confidence': detection['confidence'],
                'center_x': center_x,
                'center_y': center_y,
                'depth_m': round(depth_m, 4),
                'camera_x_m': round(float(x_m), 4),
                'camera_y_m': round(float(y_m), 4),
                'camera_z_m': round(float(depth_m), 4),
            })

        result = String()
        result.data = json.dumps(objects_3d)
        self.position_publisher.publish(result)

        if objects_3d:
            self.get_logger().info(result.data)

    def sample_depth_m(self, center_x, center_y):
        depth = self.latest_depth
        height, width = depth.shape[:2]

        if not (0 <= center_x < width and 0 <= center_y < height):
            self.get_logger().warn(f'Detection center outside depth image: ({center_x}, {center_y})')
            return None

        x1 = max(0, center_x - 3)
        y1 = max(0, center_y - 3)
        x2 = min(width, center_x + 4)
        y2 = min(height, center_y + 4)
        patch = depth[y1:y2, x1:x2]
        valid = patch[np.isfinite(patch) & (patch > 0)]

        if valid.size == 0:
            self.get_logger().warn(f'No valid depth near ({center_x}, {center_y})')
            return None

        depth_value = float(np.median(valid))
        if self.latest_depth_encoding == '16UC1':
            return depth_value / 1000.0
        return depth_value


def main(args=None):
    rclpy.init(args=args)
    node = DepthPositionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

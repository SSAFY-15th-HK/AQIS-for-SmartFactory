import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

import json
import os
from pathlib import Path
import torch

from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge
import cv2

class YOLOv5Publisher(Node):
    def __init__(self):
        super().__init__('yolov5_publisher')
        
        # Create publishers
        self.result_publisher = self.create_publisher(String, 'yolov5_results', 10)
        self.image_publisher = self.create_publisher(Image, 'yolov5_image_with_boxes', 10)
        
        # Subscribe to the image topic
        self.image_subscriber = self.create_subscription(Image, '/camera/camera/color/image_raw', self.image_callback, 10)
        
        # Load YOLOv5 model
        package_model = Path(get_package_share_directory('integrate_prac')) / 'models' / 'best.pt'
        self.model = torch.hub.load(
            os.getenv('AQIS_YOLOV5_REPO', str(Path.home() / 'yolov5')),
            'custom',
            path=os.getenv('AQIS_YOLO_MODEL', str(package_model)),
            source='local'
        )
        self.model.conf = 0.7
        self.get_logger().info(f"Loaded YOLO classes: {self.model.names}")
        self.get_logger().info(f"YOLO confidence threshold: {self.model.conf}")
        self.bridge = CvBridge()

    def image_callback(self, msg):
        # Convert ROS Image message to OpenCV image
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")

        except Exception as e:
            self.get_logger().error(f"Failed to convert image: {e}")
            return
        
        # YOLOv5 expects RGB input. ROS/OpenCV gives us BGR, which breaks color-based classes.
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        results = self.model(rgb_image)
        detections = results.pandas().xyxy[0]
        
        detection_data = []
        
        for _, row in detections.iterrows():
            label = row['name']
            confidence = float(row['confidence'])
            xmin, ymin, xmax, ymax = int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax'])
            center_x = int((xmin + xmax) / 2)
            center_y = int((ymin + ymax) / 2)
            
            detection_data.append({
                "label": label,
                "confidence": round(confidence, 4),
                "center_x": center_x,
                "center_y": center_y,
                "bbox": {
                    "xmin": xmin,
                    "ymin": ymin,
                    "xmax": xmax,
                    "ymax": ymax,
                },
            })

            # Draw bounding box and label on the image
            cv2.rectangle(cv_image, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
            cv2.circle(cv_image, (center_x, center_y), 4, (0, 0, 255), -1)
            cv2.putText(cv_image, f"{label} {confidence:.2f}", (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Publish detection results as text
        result_message = String()
        result_message.data = json.dumps(detection_data)
        self.result_publisher.publish(result_message)
        if detection_data:
            self.get_logger().info(f"Published {len(detection_data)} YOLO detection(s).")
        
        # Convert the modified image to ROS Image message and publish
        try:
            boxed_image_msg = self.bridge.cv2_to_imgmsg(cv_image, encoding="bgr8")
            self.image_publisher.publish(boxed_image_msg)
            self.get_logger().info("Published image with bounding boxes.")
        except Exception as e:
            self.get_logger().error(f"Failed to publish image: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = YOLOv5Publisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

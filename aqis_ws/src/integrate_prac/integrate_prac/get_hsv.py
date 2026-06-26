import rclpy
from rclpy.node import Node

import cv2
import numpy as np

import pyrealsense2 as rs

from cv_bridge import CvBridge


class RealSenseYoloNode(Node):
    def __init__(self):
        super().__init__('realsense_yolov5_node')
        
        # RealSense camera setup
        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        self.pipeline.start(config)
       
        self.bridge = CvBridge()
        self.timer = self.create_timer(0.1, self.timer_callback)
    
        cv2.namedWindow('frame')
        cv2.setMouseCallback('frame', self.get_hsv)
    
    def get_hsv(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:  # 왼쪽 마우스 버튼 클릭 시
            hsv = cv2.cvtColor(self.color_image, cv2.COLOR_BGR2HSV)
            print(f"HSV Value at ({x},{y}): {hsv[y,x]}")
    
    def timer_callback(self):
        # Get RealSense frames
        frames = self.pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()
        
        if not color_frame:
            return

        # Convert to numpy array
        self.color_image = np.asanyarray(color_frame.get_data())
  
        # Show the image
        cv2.imshow('frame', self.color_image)
        cv2.waitKey(1)

    def destroy_node(self):
        self.pipeline.stop()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = RealSenseYoloNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()

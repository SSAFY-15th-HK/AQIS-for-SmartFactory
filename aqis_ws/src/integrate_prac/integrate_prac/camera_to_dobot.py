import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class CameraToDobotNode(Node):
    def __init__(self):
        super().__init__('camera_to_dobot_node')

        self.create_subscription(String, '/detected_objects_3d', self.objects_callback, 10)
        self.publisher = self.create_publisher(String, '/detected_objects_dobot', 10)

        self.get_logger().info('Camera to Dobot mapper started.')

    def objects_callback(self, msg):
        try:
            objects_3d = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'Failed to parse detected objects JSON: {e}')
            return

        mapped_objects = []
        for obj in objects_3d:
            camera_x = float(obj['camera_x_m'])
            camera_y = float(obj['camera_y_m'])
            dobot_x, dobot_y = self.camera_to_dobot_xy(camera_x, camera_y)

            mapped_objects.append({
                'label': obj['label'],
                'confidence': obj['confidence'],
                'camera_x_m': obj['camera_x_m'],
                'camera_y_m': obj['camera_y_m'],
                'camera_z_m': obj['camera_z_m'],
                'dobot_x_mm': round(dobot_x, 2),
                'dobot_y_mm': round(dobot_y, 2),
                'above_pick_z_mm': 40.0,
                'pick_z_mm': -41.0,
                'dobot_r_deg': 0.0,
            })

        result = String()
        result.data = json.dumps(mapped_objects)
        self.publisher.publish(result)

        if mapped_objects:
            self.get_logger().info(result.data)

    def camera_to_dobot_xy(self, camera_x_m, camera_y_m):
        dobot_x_mm = (
            -23.39877523 * camera_x_m
            + 949.06588080 * camera_y_m
            + 238.30161522
        )
        dobot_y_mm = (
            796.09550200 * camera_x_m
            + 6.54526101 * camera_y_m
            + 0.17718195
        )
        return dobot_x_mm, dobot_y_mm


def main(args=None):
    rclpy.init(args=args)
    node = CameraToDobotNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

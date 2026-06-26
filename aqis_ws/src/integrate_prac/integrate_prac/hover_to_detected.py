import json

import rclpy
from action_msgs.msg import GoalStatus
from dobot_msgs.action import PointToPoint
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String


class HoverToDetectedNode(Node):
    def __init__(self):
        super().__init__('hover_to_detected_node')

        self.declare_parameter('target_label', '')
        self.declare_parameter('hover_z_mm', 40.0)
        self.declare_parameter('r_deg', 0.0)
        self.declare_parameter('velocity_ratio', 0.3)
        self.declare_parameter('acceleration_ratio', 0.3)

        self.target_label = self.get_parameter('target_label').value
        self.hover_z_mm = float(self.get_parameter('hover_z_mm').value)
        self.r_deg = float(self.get_parameter('r_deg').value)
        self.velocity_ratio = float(self.get_parameter('velocity_ratio').value)
        self.acceleration_ratio = float(self.get_parameter('acceleration_ratio').value)

        self.goal_active = False
        self.goal_sent = False
        self.action_client = ActionClient(self, PointToPoint, 'PTP_action')
        self.create_subscription(String, '/detected_objects_dobot', self.objects_callback, 10)
        self.create_subscription(String, '/pick_color', self.pick_color_callback, 10)

        label_text = self.target_label if self.target_label else 'highest confidence object'
        self.get_logger().info(
            f'Hover test ready. Target: {label_text}, hover_z_mm={self.hover_z_mm}'
        )
        self.get_logger().info('Publish a color to /pick_color to choose a target: red, blue, green, yellow')

    def pick_color_callback(self, msg):
        color = msg.data.strip().lower()
        aliases = {
            'red': 'red_square',
            'blue': 'blue_square',
            'green': 'green_square',
            'yellow': 'yellow_square',
            'red_square': 'red_square',
            'blue_square': 'blue_square',
            'green_square': 'green_square',
            'yellow_square': 'yellow_square',
        }

        if color not in aliases:
            self.get_logger().warn(f'Unknown pick color: {msg.data}')
            return

        self.target_label = aliases[color]
        self.goal_sent = False
        self.goal_active = False
        self.get_logger().info(f'New target selected: {self.target_label}')

    def objects_callback(self, msg):
        if self.goal_active or self.goal_sent:
            return

        try:
            objects = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'Failed to parse Dobot object JSON: {e}')
            return

        if self.target_label:
            objects = [obj for obj in objects if obj.get('label') == self.target_label]
        if not objects:
            return

        target = max(objects, key=lambda obj: float(obj.get('confidence', 0.0)))
        self.send_hover_goal(target)

    def send_hover_goal(self, target):
        x_mm = float(target['dobot_x_mm'])
        y_mm = float(target['dobot_y_mm'])
        pose = [x_mm, y_mm, self.hover_z_mm, self.r_deg]

        self.get_logger().info(
            f'Sending hover goal for {target["label"]}: '
            f'x={x_mm:.2f}, y={y_mm:.2f}, z={self.hover_z_mm:.2f}, r={self.r_deg:.2f}'
        )

        self.action_client.wait_for_server()

        goal = PointToPoint.Goal()
        goal.motion_type = 1
        goal.target_pose = pose
        goal.velocity_ratio = self.velocity_ratio
        goal.acceleration_ratio = self.acceleration_ratio

        self.goal_active = True
        self.goal_sent = True
        future = self.action_client.send_goal_async(goal, feedback_callback=self.feedback_callback)
        future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Hover goal rejected.')
            self.goal_active = False
            return

        self.get_logger().info('Hover goal accepted.')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        status = future.result().status
        result = future.result().result
        self.goal_active = False

        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info(f'Hover goal succeeded: {result}')
        else:
            self.get_logger().warn(f'Hover goal finished with status {status}: {result}')

    def feedback_callback(self, feedback_msg):
        current_pose = feedback_msg.feedback.current_pose
        self.get_logger().info(f'Current pose: {current_pose}')


def main(args=None):
    rclpy.init(args=args)
    node = HoverToDetectedNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

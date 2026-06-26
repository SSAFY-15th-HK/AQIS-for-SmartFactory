import json
import math

import rclpy
from action_msgs.msg import GoalStatus
from dobot_msgs.action import PointToPoint
from dobot_msgs.srv import SuctionCupControl
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String


class PickPlaceDetectedNode(Node):
    def __init__(self):
        super().__init__('pick_place_detected_node')

        self.declare_parameter('above_pick_z_mm', 40.0)
        self.declare_parameter('pick_z_mm', -41.0)
        self.declare_parameter('above_place_z_mm', 40.0)
        self.declare_parameter('place_z_mm', -35.0)
        self.declare_parameter('r_deg', 0.0)
        self.declare_parameter('velocity_ratio', 0.3)
        self.declare_parameter('acceleration_ratio', 0.3)
        self.declare_parameter('tracking_hover_z_mm', 70.0)
        self.declare_parameter('stable_threshold_mm', 5.0)
        self.declare_parameter('stable_required_frames', 30)
        self.declare_parameter('hover_update_threshold_mm', 8.0)
        self.declare_parameter('hover_update_period_sec', 0.25)
        self.declare_parameter('suction_on_wait_sec', 1.0)
        self.declare_parameter('suction_off_wait_sec', 0.5)

        self.above_pick_z_mm = float(self.get_parameter('above_pick_z_mm').value)
        self.pick_z_mm = float(self.get_parameter('pick_z_mm').value)
        self.above_place_z_mm = float(self.get_parameter('above_place_z_mm').value)
        self.place_z_mm = float(self.get_parameter('place_z_mm').value)
        self.r_deg = float(self.get_parameter('r_deg').value)
        self.velocity_ratio = float(self.get_parameter('velocity_ratio').value)
        self.acceleration_ratio = float(self.get_parameter('acceleration_ratio').value)
        self.tracking_hover_z_mm = float(self.get_parameter('tracking_hover_z_mm').value)
        self.stable_threshold_mm = float(self.get_parameter('stable_threshold_mm').value)
        self.stable_required_frames = int(self.get_parameter('stable_required_frames').value)
        self.hover_update_threshold_mm = float(self.get_parameter('hover_update_threshold_mm').value)
        self.hover_update_period_sec = float(self.get_parameter('hover_update_period_sec').value)
        self.suction_on_wait_sec = float(self.get_parameter('suction_on_wait_sec').value)
        self.suction_off_wait_sec = float(self.get_parameter('suction_off_wait_sec').value)

        self.place_pose_by_label = {
            'red_square': [112.5, -192.3, -50.3, -59.6],
            'green_square': [77.6, -187.5, -49.2, -67.5],
            'blue_square': [45.4, -185.5, -49.8, -76.24],
            'yellow_square': [82.1, 168.7, -49.3, 64.0],
        }

        self.target_label = None
        self.latest_objects = []
        self.color_priority = ['red_square', 'green_square', 'blue_square', 'yellow_square']
        self.state = 'IDLE'
        self.tracking_latest_target = None
        self.previous_tracking_xy = None
        self.last_hover_goal_xy = None
        self.stable_count = 0
        self.tracking_goal_active = False
        self.busy = False
        self.sequence = []
        self.sequence_index = 0
        self.wait_timer = None

        cb_group = ReentrantCallbackGroup()
        self.action_client = ActionClient(self, PointToPoint, 'PTP_action', callback_group=cb_group)
        self.suction_client = self.create_client(
            SuctionCupControl,
            'dobot_suction_cup_service',
            callback_group=cb_group,
        )
        self.create_subscription(String, '/detected_objects_dobot', self.objects_callback, 10)
        self.create_timer(self.hover_update_period_sec, self.tracking_timer_callback)

        self.get_logger().info('Automatic pick/place node ready.')
        self.get_logger().info('The robot will pick detected colors automatically after the target is steady.')
        self.get_logger().info(
            'Reactive tracking: '
            f'hover_z={self.tracking_hover_z_mm} mm, '
            f'stable_threshold={self.stable_threshold_mm} mm, '
            f'stable_frames={self.stable_required_frames}'
        )
        self.get_logger().info(f'Color priority: {self.color_priority}')
        self.get_logger().info(f'Place pose map: {self.place_pose_by_label}')

    def objects_callback(self, msg):
        try:
            self.latest_objects = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'Failed to parse Dobot object JSON: {e}')
            return

        if self.state == 'TRACKING':
            self.update_tracking_target()

        if not self.busy:
            self.try_auto_pick()

    def try_auto_pick(self):
        target = None
        for label in self.color_priority:
            target = self.find_target(label)
            if target is not None:
                break

        if target is None:
            return

        self.target_label = target['label']
        self.get_logger().info(f'Auto selected {self.target_label}')
        self.start_tracking(target)

    def find_target(self, label):
        matches = [obj for obj in self.latest_objects if obj.get('label') == label]
        if not matches:
            return None
        return max(matches, key=lambda obj: float(obj.get('confidence', 0.0)))

    def start_tracking(self, target):
        self.busy = True
        self.state = 'TRACKING'
        self.tracking_latest_target = target
        self.previous_tracking_xy = None
        self.last_hover_goal_xy = None
        self.stable_count = 0
        self.tracking_goal_active = False

        self.get_logger().info(
            f'Tracking {target["label"]}. Move the cube if needed; '
            'picking starts after it is steady.'
        )
        self.update_tracking_target()
        self.tracking_timer_callback()

    def update_tracking_target(self):
        if self.target_label is None:
            return

        target = self.find_target(self.target_label)
        if target is None:
            self.stable_count = 0
            return

        x = float(target['dobot_x_mm'])
        y = float(target['dobot_y_mm'])

        if self.previous_tracking_xy is None:
            self.stable_count = 0
        else:
            movement = self.distance_mm((x, y), self.previous_tracking_xy)
            if movement <= self.stable_threshold_mm:
                self.stable_count += 1
            else:
                self.stable_count = 0

        self.previous_tracking_xy = (x, y)
        self.tracking_latest_target = target

    def tracking_timer_callback(self):
        if self.state != 'TRACKING' or self.tracking_latest_target is None:
            return

        x = float(self.tracking_latest_target['dobot_x_mm'])
        y = float(self.tracking_latest_target['dobot_y_mm'])

        if (
            self.stable_count >= self.stable_required_frames
            and not self.tracking_goal_active
        ):
            target = self.tracking_latest_target
            self.get_logger().info(
                f'{target["label"]} is steady for {self.stable_count} frames. Starting pick.'
            )
            self.start_pick_place(target)
            return

        should_send_hover = self.last_hover_goal_xy is None
        if not should_send_hover:
            moved_since_hover = self.distance_mm((x, y), self.last_hover_goal_xy)
            should_send_hover = moved_since_hover >= self.hover_update_threshold_mm

        if should_send_hover and not self.tracking_goal_active:
            self.send_tracking_hover_goal(x, y)

    def send_tracking_hover_goal(self, x_mm, y_mm):
        self.action_client.wait_for_server()

        goal = PointToPoint.Goal()
        goal.motion_type = 1
        goal.target_pose = [x_mm, y_mm, self.tracking_hover_z_mm, self.r_deg]
        goal.velocity_ratio = self.velocity_ratio
        goal.acceleration_ratio = self.acceleration_ratio

        self.tracking_goal_active = True
        self.last_hover_goal_xy = (x_mm, y_mm)
        self.get_logger().info(
            f'Tracking hover: x={x_mm:.2f}, y={y_mm:.2f}, z={self.tracking_hover_z_mm:.2f}, '
            f'stable={self.stable_count}/{self.stable_required_frames}'
        )
        future = self.action_client.send_goal_async(goal)
        future.add_done_callback(self.tracking_goal_response_callback)

    def tracking_goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Tracking hover goal rejected.')
            self.tracking_goal_active = False
            self.busy = False
            self.state = 'IDLE'
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.tracking_move_result_callback)

    def tracking_move_result_callback(self, future):
        status = future.result().status
        self.tracking_goal_active = False
        if status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(f'Tracking hover failed with status {status}.')
            self.busy = False
            self.state = 'IDLE'

    def distance_mm(self, point_a, point_b):
        return math.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])

    def start_pick_place(self, target):
        self.state = 'PICK_PLACE'
        self.tracking_goal_active = False
        pick_x = float(target['dobot_x_mm'])
        pick_y = float(target['dobot_y_mm'])
        place_x, place_y, place_z, place_r = self.place_pose_by_label[target['label']]

        self.sequence = [
            ['move', [pick_x, pick_y, self.above_pick_z_mm, self.r_deg]],
            ['move', [pick_x, pick_y, self.pick_z_mm, self.r_deg]],
            ['suction', True],
            ['wait', self.suction_on_wait_sec],
            ['move', [pick_x, pick_y, self.above_pick_z_mm, self.r_deg]],
            ['move', [place_x, place_y, self.above_place_z_mm, place_r]],
            ['move', [place_x, place_y, place_z, place_r]],
            ['suction', False],
            ['wait', self.suction_off_wait_sec],
            ['move', [place_x, place_y, self.above_place_z_mm, place_r]],
            ['move', [200.0, 0.0, 80.0, 0.0]],
        ]
        self.sequence_index = 0
        self.busy = True

        self.get_logger().info(
            f'Starting pick/place for {target["label"]}: '
            f'pick=({pick_x:.2f}, {pick_y:.2f}), '
            f'place=({place_x:.2f}, {place_y:.2f}, {place_z:.2f}, {place_r:.2f})'
        )
        self.execute_next_step()

    def execute_next_step(self):
        if self.sequence_index >= len(self.sequence):
            self.busy = False
            self.state = 'IDLE'
            self.get_logger().info('Pick/place sequence complete.')
            self.try_auto_pick()
            return

        step = self.sequence[self.sequence_index]
        self.sequence_index += 1

        if step[0] == 'move':
            self.send_move(step[1])
        elif step[0] == 'suction':
            self.send_suction(step[1])
        elif step[0] == 'wait':
            self.get_logger().info(f'Wait: {step[1]} sec')
            self.wait_timer = self.create_timer(step[1], self.wait_done_callback)

    def wait_done_callback(self):
        if self.wait_timer is not None:
            self.wait_timer.cancel()
            self.wait_timer = None
        self.execute_next_step()

    def send_move(self, pose):
        self.action_client.wait_for_server()

        goal = PointToPoint.Goal()
        goal.motion_type = 1
        goal.target_pose = pose
        goal.velocity_ratio = self.velocity_ratio
        goal.acceleration_ratio = self.acceleration_ratio

        self.get_logger().info(f'Move: {pose}')
        future = self.action_client.send_goal_async(goal)
        future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Move goal rejected. Stopping sequence.')
            self.busy = False
            self.state = 'IDLE'
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.move_result_callback)

    def move_result_callback(self, future):
        status = future.result().status
        if status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(f'Move failed with status {status}. Stopping sequence.')
            self.busy = False
            self.state = 'IDLE'
            return

        self.execute_next_step()

    def send_suction(self, enabled):
        if not self.suction_client.wait_for_service(timeout_sec=3.0):
            self.get_logger().error('Suction service unavailable. Stopping sequence.')
            self.busy = False
            self.state = 'IDLE'
            return

        request = SuctionCupControl.Request()
        request.enable_suction = enabled
        self.get_logger().info(f'Suction: {enabled}')
        future = self.suction_client.call_async(request)
        future.add_done_callback(self.suction_result_callback)

    def suction_result_callback(self, future):
        try:
            self.get_logger().info(f'Suction response: {future.result()}')
        except Exception as e:
            self.get_logger().error(f'Suction call failed: {e}')
            self.busy = False
            self.state = 'IDLE'
            return

        self.execute_next_step()


def main(args=None):
    rclpy.init(args=args)
    node = PickPlaceDetectedNode()
    executor = MultiThreadedExecutor()
    try:
        rclpy.spin(node, executor=executor)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

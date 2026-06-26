import rclpy
from rclpy.node import Node
import time

from dobot_msgs.srv import SuctionCupControl

class SuctionCupClient(Node):

    def __init__(self):
        super().__init__('dobot_suction_cup_cli')
        # Create a client for the SuctionCupControl service
        self.cli = self.create_client(SuctionCupControl, 'dobot_suction_cup_service')
        # Wait until the service is available
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Service not avaliable, waiting again...')

        # Request object for the service
        self.req = SuctionCupControl.Request()


    def send_request(self, enable_suction):
        # Send the service request to control the suction cup
        self.req.enable_suction = enable_suction
        self.future = self.cli.call_async(self.req)
        rclpy.spin_until_future_complete(self, self.future)
        return self.future.result()

def main(args=None):
    rclpy.init(args=args)

    suction_cup_client = SuctionCupClient()

    # Repeat the suction control 3 times
    for i in range(3):
        # Turn suction cup ON
        response = suction_cup_client.send_request(True)
        suction_cup_client.get_logger().info(f'Cycle {i + 1}: Suction cup ON for 3 seconds.')
        time.sleep(3)  # Wait for 3 seconds with suction ON

        # Turn suction cup OFF
        response = suction_cup_client.send_request(False)
        suction_cup_client.get_logger().info(f'Cycle {i + 1}: Suction cup OFF for 3 seconds.')
        time.sleep(3)  # Wait for 3 seconds with suction OFF

    # Clean up
    suction_cup_client.get_logger().info('Completed 3 cycles of suction control.')
    suction_cup_client.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

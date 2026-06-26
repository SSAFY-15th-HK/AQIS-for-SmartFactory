import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import socket
import threading

import time

# timeout 2s ros2 topic pub -r 10 /detection_results std_msgs/msg/String "{data: 'back panel'}"
# timeout 2s ros2 topic pub -r 10 /detection_results std_msgs/msg/String "{data: 'board panel'}"

def start_conveyor_server(host='127.0.0.1', port=65432):
    # Create a socket (IPv4, TCP)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"Server is listening on {host}:{port}...")

        conn, addr = s.accept()
        print(f"Connected by {addr}")
        return conn  # Return the connection to be used in handle_client

def handle_conveyor_client(conn, machine, status):
    """Handles communication with the connected client."""
    if machine == 'conv':
        if status == 'conv_run':
            command = '1'

            conn.sendall(command.encode('utf-8'))
            print(f"Sent command {command} to the client.")
    
        elif status == 'conv_stop':
            command = '2'

            conn.sendall(command.encode('utf-8'))
            print(f"Sent command {command} to the client.")

    elif machine == 'seperator':
        if status == 3:
            command = '3'

            conn.sendall(command.encode('utf-8'))
            print(f"Sent command {command} to the client.")
    
        elif status == 4:
            command = '4'

            conn.sendall(command.encode('utf-8'))
            print(f"Sent command {command} to the client.")
    
    else:
        print("Please check the machine name.")

def start_roboDK_server(host='127.0.0.1', port=20000):
    # Create a socket (IPv4, TCP)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"Server is listening on {host}:{port}...")

        conn, addr = s.accept()
        print(f"Connected by {addr}")
        return conn  # Return the connection to be used in handle_client
    
def handle_roboDK_client(conn, status):
    if status == '1':
        command = '1'

        conn.sendall(command.encode('utf-8'))
        print(f"Sent command {command} to the client.")
    elif status == '2':
        command = '2'

        conn.sendall(command.encode('utf-8'))
        print(f"Sent command {command} to the client.")
    else:
        print(f"Wrong Status.")

class ObjectDetectionSubscriber(Node):
    def __init__(self):
        super().__init__('object_detection_subscriber')

        # Subscribe to /detection_results topic
        self.subscription = self.create_subscription(
            String,  # Message type of the /detection_results topic (modify according to YOLOv5 results)
            '/detection_results',
            self.listener_callback,
            10
        )

        self.conv_server_conn = False
        self.roboDK_server_conn = False
        # If the same object is detected 12 or more times, perform the task
        self.detection_buffer = []
        self.buffer_size= 20
        self.detection_threshold = 12

        self.get_logger().info("Object Detection Subscriber has started.")

        ## Conveyor Server On
        server_thread = threading.Thread(target=self.start_conveyor_server_in_thread)
        server_thread.daemon = True
        server_thread.start()

        ## robotDK Server On
        server_thread = threading.Thread(target=self.start_roboDK_server_in_thread)
        server_thread.daemon = True
        server_thread.start()
        

    def listener_callback(self, msg):
        # Receive object detection results (msg.data is assumed to contain YOLOv5 results)
          # Modify according to the actual message structure
        detection_results = msg.data
        self.get_logger().info(f"Received detection results: {detection_results}")

        # Check which objects were detected (e.g., analyze YOLOv5 results)
        detected_objectes = self.parse_detection_results(detection_results)

        # Check if the specified object was detected and add it to the array
        if 'back panel' in detected_objectes:
            self.detection_buffer.append('back panel')
        elif 'board panel' in detected_objectes:
            self.detection_buffer.append('board panel')
        else:
            self.detection_buffer.append('none')
        # Remove the oldest data to maintain the buffer size
        if len(self.detection_buffer) > self.buffer_size:
            self.detection_buffer.pop(0) 

        # Check if any of the objects meet the detection condition and execute the task
        self.check_object_detection()

    def check_object_detection(self):
        # Check if each object has been detected 12 or more times in a row, and then perform the task
        if self.detection_buffer.count('back panel') >= self.detection_threshold:
            self.perform_task_for_object('back panel')
        elif self.detection_buffer.count('board panel') >= self.detection_threshold:
            self.perform_task_for_object('board panel')

    def parse_detection_results(self, detection_results):
        try:
            # Handle the case where the data is empty or malformed
            if not detection_results:
                self.get_logger().warn("Empty detection results received.")
                return []

            # Parse YOLOv5 results and return a list of object names (e.g., "back panel white,board panel blue")
              # Example: "back panel white, board panel blue"
            detected_objects = [obj.strip() for obj in detection_results.split(',')]
            return detected_objects

        except Exception as e:
            # Handle any unexpected errors
            self.get_logger().error(f"Unexpected error: {e}")
            return []

    def perform_task_for_object(self, object_name):
        # Execute the task when the object is detected
        self.get_logger().info(f"{object_name} detected consistently! Performing task...")

        # Define actions for each object
        if object_name == 'back panel':
            self.perform_task_back_panel()
        elif object_name == 'board panel':
            self.perform_task_board_panel()
        
        
        # Reset the buffer after the task is completed and wait for new detections
        self.detection_buffer = []
        
    def start_conveyor_server_in_thread(self):
        self.conv_server_conn = start_conveyor_server()

    def wait_for_conveyor_server_connection(self, timeout=10):
        start_time = time.time()
        while self.conv_server_conn is None and time.time() - start_time < timeout:
            self.get_logger().info("Waiting for server connection...")
            time.sleep(1)

        if self.conv_server_conn is None:
            self.get_logger().error("Failed to establish server connection within timeout.")
        else:
            self.get_logger().info("Conveyor Server connection established.")

    def start_roboDK_server_in_thread(self):
        """Function to start the server in a separate thread."""
        self.roboDK_server_conn = start_roboDK_server()

    def wait_for_roboDK_server_connection(self, timeout=10):
        """Waits for server connection to be ready within a given timeout."""
        start_time = time.time()
        while self.roboDK_server_conn is None and time.time() - start_time < timeout:
            self.get_logger().info("Waiting for server connection...")
            time.sleep(1)

        if self.roboDK_server_conn is None:
            self.get_logger().error("Failed to establish server connection within timeout.")
        else:
            self.get_logger().info("roboDK Server connection established.")

    def perform_task_back_panel(self):
        self.get_logger().info("Executing task for back panel")
        
        self.wait_for_conveyor_server_connection()
        
        if self.conv_server_conn:
            handle_conveyor_client(self.conv_server_conn, 'seperator', 3)
        
        time.sleep(5)

    def perform_task_board_panel(self):
        self.get_logger().info("Executing task for board panel")

        self.wait_for_conveyor_server_connection()
        self.wait_for_roboDK_server_connection()

        if self.conv_server_conn:
            handle_conveyor_client(self.conv_server_conn, 'conv', 'conv_stop')
        
        self.roboDKStatus = '1'
        if self.roboDK_server_conn:
            handle_roboDK_client(self.roboDK_server_conn, self.roboDKStatus)
        
        time.sleep(5)

def main(args=None):
    rclpy.init(args=args)
    node = ObjectDetectionSubscriber()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    rclpy.shutdown()

if __name__ == '__main__':
    main()
    
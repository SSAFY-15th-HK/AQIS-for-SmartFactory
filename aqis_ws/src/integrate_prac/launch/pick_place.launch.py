from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    dobot_bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('dobot_bringup'),
                'launch',
                'dobot_magician_control_system.launch.py',
            )
        )
    )

    realsense_launch = ExecuteProcess(
        cmd=['ros2', 'launch', 'realsense2_camera', 'rs_launch.py', 'align_depth.enable:=true'],
        shell=True,
        output='log',
    )

    yolo_node = Node(
        package='integrate_prac',
        executable='yolo',
        output='log',
    )

    depth_position_node = Node(
        package='integrate_prac',
        executable='depth_position',
        output='log',
    )

    camera_to_dobot_node = Node(
        package='integrate_prac',
        executable='camera_to_dobot',
        output='log',
    )

    dobot_homing_call = ExecuteProcess(
        cmd=[
            'ros2',
            'service',
            'call',
            '/dobot_homing_service',
            'dobot_msgs/srv/ExecuteHomingProcedure',
        ],
        shell=True,
        output='screen',
    )

    pick_place_node = Node(
        package='integrate_prac',
        executable='pick_place_detected',
        output='log',
    )

    return LaunchDescription([
        SetEnvironmentVariable('MAGICIAN_TOOL', 'suction_cup'),
        dobot_bringup_launch,
        TimerAction(period=20.0, actions=[realsense_launch]),
        TimerAction(period=35.0, actions=[dobot_homing_call]),
        TimerAction(period=45.0, actions=[yolo_node]),
        TimerAction(period=50.0, actions=[depth_position_node]),
        TimerAction(period=55.0, actions=[camera_to_dobot_node]),
        TimerAction(period=70.0, actions=[pick_place_node]),
    ])

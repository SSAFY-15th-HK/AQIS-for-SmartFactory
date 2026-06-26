from launch import LaunchDescription
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
import os


def generate_launch_description():
    rviz_config_file = os.path.join(get_package_share_directory('integrate_prac'), 'rviz', 'visualization.rviz')

    return LaunchDescription([
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config_file]
        ), 
        Node(
            package='rqt_image_view',
            executable='rqt_image_view',
            name='rqt_image_view',
            output='screen',
            remappings=[
                ('/image', '/camera/camera/color/image_raw')
            ]
        ), 

    ])

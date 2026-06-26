from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():
    package_share = get_package_share_directory("integrate_prac")
    image_topic = LaunchConfiguration("image_topic")
    depth_topic = LaunchConfiguration("depth_topic")
    camera_info_topic = LaunchConfiguration("camera_info_topic")
    model_path = LaunchConfiguration("model_path")
    confidence = LaunchConfiguration("confidence")
    start_realsense = LaunchConfiguration("start_realsense")
    roi_enabled = LaunchConfiguration("roi_enabled")
    roi_x_min = LaunchConfiguration("roi_x_min")
    roi_y_min = LaunchConfiguration("roi_y_min")
    roi_x_max = LaunchConfiguration("roi_x_max")
    roi_y_max = LaunchConfiguration("roi_y_max")
    roi_width = LaunchConfiguration("roi_width")
    roi_height = LaunchConfiguration("roi_height")

    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("realsense2_camera"), "launch", "rs_launch.py")
        ),
        launch_arguments={
            "enable_color": "true",
            "enable_depth": "true",
            "align_depth.enable": "true",
            "rgb_camera.profile": "640x480x15",
            "depth_module.profile": "640x480x15",
        }.items(),
        condition=IfCondition(start_realsense),
    )

    yolo_node = Node(
        package="integrate_prac",
        executable="realsense_yolo_node",
        name="realsense_yolo_node",
        output="screen",
        parameters=[
            {
                "image_topic": image_topic,
                "depth_topic": depth_topic,
                "camera_info_topic": camera_info_topic,
                "model_path": model_path,
                "confidence": confidence,
                "annotated_image_topic": "/detection_image",
                "legacy_results_topic": "/detection_results",
                "defect_detection_topic": "/defect/detection",
                "roi_enabled": roi_enabled,
                "roi_x_min": roi_x_min,
                "roi_y_min": roi_y_min,
                "roi_x_max": roi_x_max,
                "roi_y_max": roi_y_max,
                "roi_width": roi_width,
                "roi_height": roi_height,
            }
        ],
    )

    web_video_server = ExecuteProcess(
        cmd=["ros2", "run", "web_video_server", "web_video_server", "--ros-args", "-p", "port:=8080"],
        output="screen",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("start_realsense", default_value="true"),
            DeclareLaunchArgument("image_topic", default_value="/camera/camera/color/image_raw"),
            DeclareLaunchArgument("depth_topic", default_value="/camera/camera/aligned_depth_to_color/image_raw"),
            DeclareLaunchArgument("camera_info_topic", default_value="/camera/camera/color/camera_info"),
            DeclareLaunchArgument("model_path", default_value=os.path.join(package_share, "models", "best.pt")),
            DeclareLaunchArgument("confidence", default_value="0.7"),
            DeclareLaunchArgument("roi_enabled", default_value="true"),
            DeclareLaunchArgument("roi_x_min", default_value="-1"),
            DeclareLaunchArgument("roi_y_min", default_value="-1"),
            DeclareLaunchArgument("roi_x_max", default_value="-1"),
            DeclareLaunchArgument("roi_y_max", default_value="-1"),
            DeclareLaunchArgument("roi_width", default_value="220"),
            DeclareLaunchArgument("roi_height", default_value="180"),
            realsense_launch,
            yolo_node,
            web_video_server,
        ]
    )

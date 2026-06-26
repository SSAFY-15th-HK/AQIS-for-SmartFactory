from glob import glob

from setuptools import find_packages, setup

package_name = 'integrate_prac'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/models', glob('models/*')),
        ('share/' + package_name + '/rviz', glob('rviz/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ssafy',
    maintainer_email='ssafy@todo.todo',
    description='AQIS RealSense YOLO, Dobot, and integration ROS2 nodes',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'ptp_move = integrate_prac.ptp_move:main',
            'suction_cup_control = integrate_prac.suction_cup_control:main',
            'yolo = integrate_prac.yolo:main',
            'depth_position = integrate_prac.depth_position:main',
            'camera_to_dobot = integrate_prac.camera_to_dobot:main',
            'hover_to_detected = integrate_prac.hover_to_detected:main',
            'pick_place_detected = integrate_prac.pick_place_detected:main',
            'realsense_yolo_node = integrate_prac.realsense_yolo_node:main',
            'main_prog = integrate_prac.main_prog:main',
        ],
    },
)

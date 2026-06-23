# AQIS Real Hardware Startup Walkthrough

This is the startup order for the real AQIS dashboard with TurtleBot, Dobot, RealSense YOLO detection, conveyor, FastAPI, and web UI.

## Quick Terminal Map

Use this as the demo startup checklist.

### Terminal 1 — Conveyor Pi

Run on the conveyor Raspberry Pi:

```bash
ssh ssafy@192.168.110.151
cd ~/AQIS_pjt
sudo python3 conveyor_http_server.py
```

### Terminal 2 — TurtleBot Base

Run on the TurtleBot:

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export ROS_DOMAIN_ID=33
export LDS_MODEL=LDS-02
export TURTLEBOT3_MODEL=waffle_pi
ros2 launch turtlebot3_bringup robot.launch.py
```

### Terminal 3 — TurtleBot Camera

Run on the TurtleBot:

```bash
source ~/.bashrc
ros2 run v4l2_camera v4l2_camera_node --ros-args \
  -p video_device:=/dev/video0 \
  -p image_size:="[320, 240]" \
  -p pixel_format:=YUYV \
  -p output_encoding:=rgb8
```

### Terminal 4 — TurtleBot Video Server

Run on the TurtleBot:

```bash
source ~/.bashrc
ros2 run web_video_server web_video_server --ros-args -p port:=8081
```

### Terminal 5 — Map / Navigation

Run on the laptop. Use saved map/Nav2:

```bash
source ~/.bashrc
export ROS_DOMAIN_ID=33
ros2 launch turtlebot3_navigation2 navigation2.launch.py use_sim_time:=False map:=/home/ssafy/maps/map.yaml
```

Or use live SLAM:

```bash
source ~/.bashrc
export ROS_DOMAIN_ID=33
ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=False
```

### Terminal 6 — Dobot

Run on the laptop connected to Dobot:

```bash
source /opt/ros/humble/setup.bash
source ~/magician_ros2_control_system_ws/install/setup.bash
export ROS_DOMAIN_ID=33
export MAGICIAN_TOOL=suction_cup
ros2 launch dobot_bringup dobot_magician_control_system.launch.py
```

### Terminal 7 — RealSense YOLO

Run on the laptop connected to RealSense:

```bash
source /opt/ros/humble/setup.bash
source ~/ssafy_ws/install/setup.bash
export ROS_DOMAIN_ID=33
ros2 launch integrate_prac realsense_yolo.launch.py
```

### Terminal 8 — FastAPI Backend

Run on the laptop:

```bash
cd /home/ssafy/git/AQIS-for-SmartFactory/server
source ~/.bashrc
.venv-ros/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Terminal 9 — Web Dashboard

Run on the laptop:

```bash
cd /home/ssafy/git/AQIS-for-SmartFactory/AQIS-real/web
npm run dev -- --host 0.0.0.0 --port 5173
```

Open:

```text
http://localhost:5173
```

## 0. Network And Shared Settings

Use the same ROS domain everywhere:

```bash
export ROS_DOMAIN_ID=33
```

Current known device IPs:

```text
Conveyor Pi: 192.168.110.151
TurtleBot camera stream: 192.168.110.173:8081
FastAPI backend: laptop:8000
Web dashboard: laptop:5173
```

The backend `.env` should contain:

```env
CONVEYOR_MODE=real
VISION_MODE=real
ROBOT_MODE=real
ROS_ENABLED=true
ROS_DOMAIN_ID=33
RPI_BASE_URL=http://192.168.110.151:5000
REALSENSE_STREAM_URL=http://localhost:8080/stream?topic=/detection_image
TURTLEBOT_VIEW_URL=http://192.168.110.173:8081/stream?topic=/image_raw
```

Do not store or document the real LLM access token in this file.

## 1. Start Conveyor Controller

On the conveyor Raspberry Pi:

```bash
ssh ssafy@192.168.110.151
cd ~/AQIS_pjt
sudo python3 conveyor_http_server.py
```

From the laptop, verify:

```bash
curl http://192.168.110.151:5000/status
curl -X POST http://192.168.110.151:5000/conveyor/start
curl -X POST http://192.168.110.151:5000/conveyor/stop
```

Optional sorter tests:

```bash
curl -X POST http://192.168.110.151:5000/sort/normal
curl -X POST http://192.168.110.151:5000/sort/defect
curl -X POST http://192.168.110.151:5000/emergency_stop
```

## 2. Start TurtleBot Base

On the TurtleBot:

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export ROS_DOMAIN_ID=33
export LDS_MODEL=LDS-02
export TURTLEBOT3_MODEL=waffle_pi

ros2 launch turtlebot3_bringup robot.launch.py
```

On the laptop, verify:

```bash
source ~/.bashrc
export ROS_DOMAIN_ID=33

ros2 topic echo --once /odom
ros2 topic echo --once /scan
```

## 3. Start TurtleBot Camera Stream

On the TurtleBot:

```bash
source ~/.bashrc
ros2 run v4l2_camera v4l2_camera_node --ros-args \
  -p video_device:=/dev/video0 \
  -p image_size:="[320, 240]" \
  -p pixel_format:=YUYV \
  -p output_encoding:=rgb8
```

In another TurtleBot terminal:

```bash
source ~/.bashrc
ros2 run web_video_server web_video_server --ros-args -p port:=8081
```

Test from the laptop browser:

```text
http://192.168.110.173:8081/stream?topic=/image_raw
```

## 4. Start Map / Localization

Use one of these on the laptop.

For saved map and Nav2:

```bash
source ~/.bashrc
export ROS_DOMAIN_ID=33

ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=False \
  map:=/path/to/your/map.yaml
```

For live SLAM:

```bash
source ~/.bashrc
export ROS_DOMAIN_ID=33

ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=False
```

Verify:

```bash
ros2 topic echo --once /map
ros2 topic echo --once /amcl_pose
```

If `/amcl_pose` is not available yet, the dashboard will fall back to `/odom` for TurtleBot pose.

## 5. Start Dobot

On the laptop connected to Dobot:

```bash
source /opt/ros/humble/setup.bash
source ~/magician_ros2_control_system_ws/install/setup.bash
export ROS_DOMAIN_ID=33
export MAGICIAN_TOOL=suction_cup

ros2 launch dobot_bringup dobot_magician_control_system.launch.py
```

Verify:

```bash
ros2 topic echo --once /dobot_joint_states
ros2 topic echo --once /dobot_TCP
ros2 topic echo --once /dobot_alarms
ros2 topic echo --once /gripper_status_rviz
```

## 6. Start RealSense YOLO Detection

On the laptop:

```bash
source /opt/ros/humble/setup.bash
source ~/ssafy_ws/install/setup.bash
export ROS_DOMAIN_ID=33

ros2 launch integrate_prac realsense_yolo.launch.py
```

This starts RealSense, YOLO detection, annotated image publishing, and `web_video_server` on port `8080`.

Important topics:

```text
/camera/camera/color/image_raw   RealSense raw color image
/detection_image                 YOLO annotated image for web stream
/detection_results               legacy label stream
/defect/detection                JSON event consumed by FastAPI
```

Verify:

```bash
ros2 topic echo --once /defect/detection
ros2 topic hz /detection_image
```

Test stream in browser:

```text
http://localhost:8080/stream?topic=/detection_image
```

If the model file is not in the repo root, pass the model path:

```bash
ros2 launch integrate_prac realsense_yolo.launch.py \
  model_path:=/home/ssafy/ssafy_ws/yolov5/runs/train/rgby_squares/weights/best.pt
```

## 7. Start FastAPI Backend

On the laptop:

```bash
cd /home/ssafy/git/AQIS-for-SmartFactory/server
source ~/.bashrc
.venv-ros/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/runtime/config
```

The backend subscribes to:

```text
/map
/amcl_pose
/odom
/defect/detection
/dobot_joint_states
/dobot_TCP
/dobot_pose_raw
/dobot_alarms
/gripper_status_rviz
```

When `/defect/detection` reports a defect, FastAPI updates the web quality panel, selects the defect sorter path, and stops the conveyor.

## 8. Start Web Dashboard

On the laptop:

```bash
cd /home/ssafy/git/AQIS-for-SmartFactory/AQIS-real/web
npm run dev -- --host 0.0.0.0 --port 5173
```

Open:

```text
http://localhost:5173
```

From another computer on the same network, open:

```text
http://<LAPTOP_IP>:5173
```

The dashboard **Start Monitoring** button should be used after the hardware terminals above are already running. In this real-hardware setup it starts a lightweight monitoring session in FastAPI; it should not relaunch TurtleBot, Dobot, RealSense, or `web_video_server`, because duplicate hardware launch processes can steal the camera device or collide on MJPEG ports. The API path is still `/api/aqis/start` for compatibility.

## Quick Health Checklist

Run on the laptop:

```bash
source ~/.bashrc
export ROS_DOMAIN_ID=33

ros2 topic list | grep -E "/map|/odom|/scan|/defect/detection|/detection_image|/dobot"
curl http://192.168.110.151:5000/status
curl http://localhost:8000/api/health
```

Expected web status:

```text
WebSocket Live
Map live after /map publishes
TurtleBot live after /odom or /amcl_pose publishes
Dobot live after Dobot topics publish
RealSense Inspection shows /detection_image stream
Defect Monitoring updates after /defect/detection events
```

## Common Problems

If map does not show:

```bash
ros2 topic echo --once /map
```

If this fails, restart Nav2/SLAM. If this works but the web still waits for `/map`, restart FastAPI with `ROS_ENABLED=true` and `ROS_DOMAIN_ID=33`.

If RealSense stream does not show:

```bash
ros2 topic list | grep detection_image
curl -I "http://localhost:8080/stream?topic=/detection_image"
```

If conveyor does not move:

```bash
curl http://192.168.110.151:5000/status
curl -X POST http://192.168.110.151:5000/conveyor/start
```

If TurtleBot topics are missing:

```bash
ros2 topic echo --once /odom
ros2 topic echo --once /scan
```

Check TurtleBot power, SSH session, `LDS_MODEL=LDS-02`, `TURTLEBOT3_MODEL=waffle_pi`, and `ROS_DOMAIN_ID=33`.

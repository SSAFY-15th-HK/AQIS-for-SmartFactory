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
ros2 launch integrate_prac realsense_yolo.launch.py \
  roi_width:=220 \
  roi_height:=180
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

Use `server/.env.example` as the reference for the Dobot pick/place calibration values. Keep the real LLM access token only in `server/.env`; do not commit or document it.

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

Emergency stop test:

```bash
curl -X POST http://192.168.110.151:5000/emergency_stop
```

The old servo separator endpoints are intentionally disabled in the current hardware flow. Defective canlids are removed by Dobot pick-and-place after the conveyor stops.

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

Home the Dobot before calibration or automatic pick/place:

```bash
ros2 service call /dobot_homing_service dobot_msgs/srv/ExecuteHomingProcedure
```

Before running the automatic workflow, verify one manual pick/place cycle with the current calibrated coordinates:

```bash
python3 /home/ssafy/git/AQIS-for-SmartFactory/AQIS-real/scripts/dobot_pick_place_once.py
```

Tune these values in `server/.env` for your conveyor geometry. The current setup uses RealSense `camera_point_m` to calculate the pick pose after the conveyor has fully stopped:

```env
DOBOT_PICK_X=125.0
DOBOT_PICK_Y=-180.0
DOBOT_PICK_Z=-5.8
DOBOT_PLACE_X=150.0
DOBOT_PLACE_Y=190.0
DOBOT_PLACE_Z=20.0
DOBOT_SAFE_Z=50.0
DOBOT_HOME_X=200.0
DOBOT_HOME_Y=0.0
DOBOT_HOME_Z=100.0
DOBOT_TOOL_R=7.0
DOBOT_MOTION_TYPE=1
DOBOT_VELOCITY_RATIO=0.2
DOBOT_ACCELERATION_RATIO=0.2
DOBOT_SUCTION_SETTLE_SEC=0.35
DOBOT_RESUME_CONVEYOR_AFTER_PICK=true
DOBOT_PICK_AFTER_STOP_DELAY_SEC=0.6
DOBOT_PICK_MAX_DETECTION_AGE_SEC=3.0
DOBOT_DYNAMIC_PICK_ENABLED=true
DOBOT_DYNAMIC_PICK_Z=-7.8
DOBOT_DYNAMIC_TOOL_R=7.0
DOBOT_DYNAMIC_PICK_OFFSET_X_MM=0.0
DOBOT_DYNAMIC_PICK_OFFSET_Y_MM=0.0
DOBOT_DYNAMIC_PICK_OFFSET_Z_MM=0.0
DOBOT_CAMERA_TO_DOBOT_X_CAM_X=0.06923808
DOBOT_CAMERA_TO_DOBOT_X_CAM_Y=1.05444383
DOBOT_CAMERA_TO_DOBOT_X_BIAS=0.23200291
DOBOT_CAMERA_TO_DOBOT_Y_CAM_X=0.76906914
DOBOT_CAMERA_TO_DOBOT_Y_CAM_Y=0.09692414
DOBOT_CAMERA_TO_DOBOT_Y_BIAS=0.02651858
DOBOT_DYNAMIC_Z_ENABLED=true
DOBOT_CAMERA_TO_DOBOT_Z_CAM_X=-0.02862024
DOBOT_CAMERA_TO_DOBOT_Z_CAM_Y=0.05172572
DOBOT_CAMERA_TO_DOBOT_Z_BIAS=-0.00744611
```

If you move the camera, Dobot, conveyor, suction cup, or home position, redo the camera-to-Dobot calibration points before trusting automatic pickup.

For a small final correction after calibration, use the Dobot-frame offset values. Left/right correction is usually `DOBOT_DYNAMIC_PICK_OFFSET_Y_MM`; forward/back correction is usually `DOBOT_DYNAMIC_PICK_OFFSET_X_MM`.

## 6. Start RealSense YOLO Detection

On the laptop:

```bash
source /opt/ros/humble/setup.bash
source ~/ssafy_ws/install/setup.bash
export ROS_DOMAIN_ID=33

ros2 launch integrate_prac realsense_yolo.launch.py \
  roi_width:=220 \
  roi_height:=180
```

This starts RealSense with aligned depth, YOLO detection, annotated image publishing, the center pick ROI, and `web_video_server` on port `8080`.

Important topics:

```text
/camera/camera/color/image_raw   RealSense raw color image
/camera/camera/aligned_depth_to_color/image_raw
/camera/camera/color/camera_info
/detection_image                 YOLO annotated image for web stream
/detection_results               legacy label stream
/defect/detection                JSON event consumed by FastAPI
```

Verify:

```bash
ros2 topic echo --once /defect/detection
ros2 topic hz /detection_image
```

For readable JSON:

```bash
ros2 topic echo --once /defect/detection --field data | sed -n '1p' | python3 -m json.tool
```

The JSON should include `roi_hit: true`, `has_depth: true`, `depth_m`, and `camera_point_m` before automatic Dobot pickup is enabled.

Test stream in browser:

```text
http://localhost:8080/stream?topic=/detection_image
```

If the model file is not in the repo root, pass the model path:

```bash
ros2 launch integrate_prac realsense_yolo.launch.py \
  model_path:=/home/ssafy/ssafy_ws/yolov5/runs/train/rgby_squares/weights/best.pt \
  roi_width:=220 \
  roi_height:=180
```

## 7. Start FastAPI Backend

On the laptop:

```bash
cd /home/ssafy/git/AQIS-for-SmartFactory/server
source ~/.bashrc
.venv-ros/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Use `.venv-ros` for real hardware. The plain `.venv` can run FastAPI, but it may not load ROS Humble `rclpy`.

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

When `/defect/detection` reports a normal canlid, FastAPI updates the web quality panel and leaves the conveyor moving. When it reports an abnormal canlid while monitoring is running, FastAPI stops the conveyor first, waits `DOBOT_PICK_AFTER_STOP_DELAY_SEC`, then uses the next fresh stopped detection with `camera_point_m` to trigger the Dobot suction-cup pick/place cycle. The conveyor resumes after pickup if `DOBOT_RESUME_CONVEYOR_AFTER_PICK=true`.

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

The dashboard **Start Monitoring** button should be used after the hardware terminals above are already running. In this real-hardware setup it starts a lightweight monitoring session in FastAPI and starts the conveyor. It should not relaunch TurtleBot, Dobot, RealSense, or `web_video_server`, because duplicate hardware launch processes can steal the camera device or collide on MJPEG ports. The API path is still `/api/aqis/start` for compatibility.

The dashboard **Stop Monitoring** button stops the monitoring session, stops the conveyor, and stops any active Dobot pick/place client.

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
RealSense online after /detection_image stream loads
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

If RealSense detects objects but Dobot does not pick:

```bash
ros2 topic echo --once /defect/detection --field data | sed -n '1p' | python3 -m json.tool
```

Check that the detection is inside the ROI and has depth:

```text
roi_hit: true
has_depth: true
camera_point_m: [x, y, z]
```

If `has_depth` is false, verify the aligned depth topic:

```bash
ros2 topic echo --once /camera/camera/aligned_depth_to_color/image_raw
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

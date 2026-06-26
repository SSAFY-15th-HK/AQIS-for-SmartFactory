# AQIS 실제 장비 시작 가이드

이 문서는 GitHub에서 repo를 clone한 사용자가 실제 장비를 실행할 수 있도록 정리한 기준 문서입니다.

## 0. Repo 기준 경로

아래 문서에서는 repo 위치를 다음처럼 가정합니다.

```bash
export AQIS_ROOT=~/git/AQIS-for-SmartFactory
```

다른 위치에 clone했다면 `AQIS_ROOT`만 바꿔서 사용합니다.

## 1. 최초 설치

노트북에서 한 번 실행합니다.

```bash
cd "$AQIS_ROOT"
./scripts/setup_dev.sh
```

새 터미널마다 기본 환경:

```bash
source /opt/ros/humble/setup.bash
source "$AQIS_ROOT/aqis_ws/install/setup.bash"
export ROS_DOMAIN_ID=33
export TURTLEBOT3_MODEL=waffle_pi
export AQIS_YOLOV5_REPO=~/yolov5
```

서버 환경 파일:

```bash
cd "$AQIS_ROOT/server"
cp .env.example .env
```

`server/.env`에서 다음 값은 장비 환경에 맞게 확인합니다.

```env
RPI_BASE_URL=http://192.168.110.151:5000
REALSENSE_STREAM_URL=http://localhost:8080/stream?topic=/detection_image
TURTLEBOT_VIEW_URL=http://<TURTLEBOT_IP>:8081/stream?topic=/image_raw
ROS_DOMAIN_ID=33
LLM_BASE_URL=
LLM_API_KEY=
```

## 2. Terminal 1 - TurtleBot Bringup

TurtleBot에 SSH 접속해서 실행합니다.

```bash
ssh turtlebot3@<TURTLEBOT_IP>
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export ROS_DOMAIN_ID=33
export LDS_MODEL=LDS-02
export TURTLEBOT3_MODEL=waffle_pi

ros2 launch turtlebot3_bringup robot.launch.py
```

확인:

```bash
ros2 topic echo --once /odom
ros2 topic echo --once /scan
```

## 3. Terminal 2 - TurtleBot Camera Stream

TurtleBot 카메라를 웹으로 보고 싶을 때 TurtleBot 또는 카메라가 연결된 장비에서 실행합니다.

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export ROS_DOMAIN_ID=33

ros2 run v4l2_camera v4l2_camera_node --ros-args \
  -p video_device:=/dev/video0 \
  -p image_size:="[640,480]" \
  -p time_per_frame:="[1,15]"
```

다른 터미널:

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=33
ros2 run web_video_server web_video_server --ros-args -p port:=8081
```

브라우저 확인:

```text
http://<TURTLEBOT_IP>:8081/stream?topic=/image_raw
```

## 4. Terminal 3 - Nav2

노트북에서 실행합니다. 지도와 AMCL 파라미터는 repo 안의 파일을 사용합니다.

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export ROS_DOMAIN_ID=33
export TURTLEBOT3_MODEL=waffle_pi

ros2 launch turtlebot3_navigation2 navigation2.launch.py \
  use_sim_time:=false \
  map:="$AQIS_ROOT/maps/realmap.yaml" \
  params_file:="$AQIS_ROOT/config/nav2/full_amcl_config.yaml"
```

## 5. Terminal 4 - Dobot Bringup

노트북에서 Dobot Magician을 연결하고 실행합니다. Dobot 드라이버 워크스페이스는 외부 의존성입니다.

```bash
source /opt/ros/humble/setup.bash
source ~/magician_ros2_control_system_ws/install/setup.bash
export ROS_DOMAIN_ID=33
export MAGICIAN_TOOL=suction_cup

ros2 launch dobot_bringup dobot_magician_control_system.launch.py
```

확인:

```bash
ros2 topic echo --once /dobot_joint_states
ros2 topic echo --once /dobot_pose_raw
```

홈이 필요하면:

```bash
ros2 service call /dobot_homing_service dobot_msgs/srv/ExecuteHomingProcedure {}
```

## 6. Terminal 5 - RealSense YOLO + MJPEG

노트북에서 RealSense가 연결된 상태로 실행합니다. 모델은 `integrate_prac` 패키지에 포함된 `models/best.pt`를 기본으로 사용합니다.

```bash
source /opt/ros/humble/setup.bash
source "$AQIS_ROOT/aqis_ws/install/setup.bash"
export ROS_DOMAIN_ID=33
export AQIS_YOLOV5_REPO=~/yolov5

ros2 launch integrate_prac realsense_yolo.launch.py \
  confidence:=0.7 \
  roi_width:=220 \
  roi_height:=180
```

주요 토픽:

```text
/detection_image       YOLO 박스가 그려진 웹 스트림용 이미지
/defect/detection      FastAPI와 컨베이어/Dobot 자동화가 읽는 JSON 결과
/detection_results     레거시 라벨 결과
```

브라우저 확인:

```text
http://localhost:8080/stream?topic=/detection_image
```

## 7. Terminal 6 - Conveyor HTTP Bridge

라즈베리파이 또는 컨베이어 제어 장비에서 실행합니다.

```bash
cd "$AQIS_ROOT/AQIS-real/conveyor"
python3 conveyor_http_server.py --host 0.0.0.0 --port 5000
```

다른 장비에 repo가 없다면 `AQIS-real/conveyor/conveyor_http_server.py`만 복사해서 실행해도 됩니다.

확인:

```bash
curl http://<RPI_IP>:5000/status
curl -X POST http://<RPI_IP>:5000/start
curl -X POST http://<RPI_IP>:5000/stop
```

## 8. Terminal 7 - FastAPI Backend

노트북에서 실행합니다.

```bash
cd "$AQIS_ROOT/server"
source /opt/ros/humble/setup.bash
source "$AQIS_ROOT/aqis_ws/install/setup.bash"
source ~/magician_ros2_control_system_ws/install/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export ROS_DOMAIN_ID=33

.venv-ros/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

확인:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/runtime/config
```

## 9. Terminal 8 - Web Dashboard

노트북에서 실행합니다.

```bash
cd "$AQIS_ROOT/AQIS-real/web"
npm run dev -- --host 0.0.0.0 --port 5173
```

브라우저:

```text
http://localhost:5173
```

## 10. 자동 동작 흐름

1. Web에서 Start
2. FastAPI가 모니터링 상태를 RUNNING으로 변경하고 컨베이어 start 요청
3. RealSense YOLO가 ROI 안의 불량 캔뚜껑을 `/defect/detection`으로 publish
4. FastAPI가 컨베이어 stop 요청
5. 컨베이어가 완전히 멈춘 뒤 최신 detection 데이터를 기준으로 Dobot pick/place 실행
6. 설정값에 따라 컨베이어 resume

## 11. 자주 확인하는 명령

ROS 토픽:

```bash
ros2 topic list
ros2 topic echo --once /defect/detection --field data
ros2 topic echo --once /dobot_pose_raw
ros2 topic echo --once /odom
```

시간 동기화:

```bash
date -u
chronyc tracking
```

카메라 스트림:

```bash
curl http://localhost:8080/stream?topic=/detection_image
```

## 12. 외부 의존성 메모

이 repo는 AQIS 소유 코드를 포함합니다. 다음은 별도 설치가 필요합니다.

- ROS2 Humble
- TurtleBot3 bringup/navigation workspace or apt packages
- Dobot Magician ROS2 control workspace
- RealSense ROS2 driver
- YOLOv5 local repo (`AQIS_YOLOV5_REPO`, 기본 `~/yolov5`)
- Raspberry Pi GPIO 환경 또는 mock conveyor mode

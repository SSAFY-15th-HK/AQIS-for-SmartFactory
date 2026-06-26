# AQIS for SmartFactory

AQIS is a real-time smart-factory monitoring project. It inspects can lids on a conveyor with RealSense + YOLO, stops the conveyor on abnormal detections, and uses a Dobot Magician suction tool for pick-and-place handling. The system connects TurtleBot3, Dobot, RealSense, a conveyor, FastAPI, and a React dashboard.

The main README is Korean: [README.md](./README.md).

## Repository Layout

```text
AQIS-for-SmartFactory/
  aqis_ws/src/integrate_prac/  # AQIS-owned ROS2 package
  AQIS-real/                   # Real hardware dashboard, conveyor server, Dobot scripts
  AQIS-sim/                    # RoboDK simulation
  server/                      # FastAPI + ROS2 bridge + WebSocket + LLM proxy
  maps/                        # Nav2/SLAM map assets
  config/nav2/                 # Nav2/AMCL parameters
  docs/                        # Detailed documentation
  ros2.repos                   # External ROS source dependencies
```

## What Is Tracked

Tracked:

- AQIS-owned ROS2 package: `aqis_ws/src/integrate_prac`
- FastAPI backend
- Real hardware React dashboard
- RoboDK simulation
- Map, navigation config, and YOLO model assets
- Documentation and sample env files

Not tracked:

- `build/`, `install/`, `log/`
- `.env`, API keys, LLM tokens
- `.venv`, `node_modules`, `dist`
- ROS bags, recordings, runtime DB files
- Build outputs from third-party ROS workspaces

## Quick Setup

Target environment: Ubuntu 22.04 + ROS2 Humble.

```bash
git clone https://github.com/SSAFY-15th-HK/AQIS-for-SmartFactory.git
cd AQIS-for-SmartFactory
export AQIS_ROOT="$(pwd)"
./scripts/setup_dev.sh
```

For each new shell:

```bash
source /opt/ros/humble/setup.bash
source "$AQIS_ROOT/aqis_ws/install/setup.bash"
export ROS_DOMAIN_ID=33
export AQIS_YOLOV5_REPO=~/yolov5
```

Create the backend env file:

```bash
cd "$AQIS_ROOT/server"
cp .env.example .env
```

Edit `server/.env` for your hardware IPs, LLM endpoint/token, and Dobot calibration values.

## Real Hardware Startup

Use [docs/real-hardware-startup.md](./docs/real-hardware-startup.md) as the source of truth.

Short order:

1. Start TurtleBot3 bringup on the TurtleBot.
2. Start Nav2 or SLAM on the laptop.
3. Start Dobot bringup on the laptop.
4. Start RealSense YOLO on the laptop.
5. Start the conveyor HTTP bridge on the Raspberry Pi.
6. Start the FastAPI backend.
7. Start the React dashboard.

## Core Commands

RealSense YOLO:

```bash
ros2 launch integrate_prac realsense_yolo.launch.py \
  confidence:=0.7 \
  roi_width:=220 \
  roi_height:=180
```

FastAPI:

```bash
cd "$AQIS_ROOT/server"
source /opt/ros/humble/setup.bash
source ../aqis_ws/install/setup.bash
.venv-ros/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Real dashboard:

```bash
cd "$AQIS_ROOT/AQIS-real/web"
npm run dev -- --host 0.0.0.0 --port 5173
```

## Important Topics

| Topic | Purpose |
|---|---|
| `/detection_image` | YOLO annotated MJPEG image for the web UI |
| `/defect/detection` | Detection result JSON consumed by FastAPI |
| `/dobot_joint_states` | Dobot joint status |
| `/dobot_pose_raw` | Dobot raw TCP pose |
| `/odom`, `/amcl_pose` | TurtleBot pose |
| `/map` | SLAM/Nav2 map |

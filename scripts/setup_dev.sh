#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"
YOLOV5_DIR="${AQIS_YOLOV5_REPO:-$HOME/yolov5}"

echo "[AQIS] root: $ROOT_DIR"
echo "[AQIS] ROS distro: $ROS_DISTRO"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "[AQIS] ros2 was not found. Install ROS2 Humble first, then rerun this script."
  exit 1
fi

sudo apt update
sudo apt install -y \
  python3-pip \
  python3-venv \
  python3-rosdep \
  python3-vcstool \
  ros-${ROS_DISTRO}-cv-bridge \
  ros-${ROS_DISTRO}-navigation2 \
  ros-${ROS_DISTRO}-nav2-bringup \
  ros-${ROS_DISTRO}-realsense2-camera \
  ros-${ROS_DISTRO}-web-video-server \
  ros-${ROS_DISTRO}-v4l2-camera

if [ ! -d "$YOLOV5_DIR/.git" ]; then
  echo "[AQIS] Cloning YOLOv5 into $YOLOV5_DIR"
  git clone https://github.com/ultralytics/yolov5.git "$YOLOV5_DIR"
fi

if [ -f "$YOLOV5_DIR/requirements.txt" ]; then
  python3 -m pip install --user -r "$YOLOV5_DIR/requirements.txt"
fi

source "/opt/ros/${ROS_DISTRO}/setup.bash"
cd "$ROOT_DIR/aqis_ws"
rosdep update || true
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install

cd "$ROOT_DIR/server"
python3 -m venv .venv-ros
.venv-ros/bin/pip install -r requirements.txt

cd "$ROOT_DIR/AQIS-real/web"
npm install

cd "$ROOT_DIR/AQIS-sim/web"
npm install

cat <<EOF

[AQIS] Setup complete.

Next shell setup:
  source /opt/ros/${ROS_DISTRO}/setup.bash
  source "$ROOT_DIR/aqis_ws/install/setup.bash"
  export AQIS_YOLOV5_REPO="$YOLOV5_DIR"

Copy server env:
  cp "$ROOT_DIR/server/.env.example" "$ROOT_DIR/server/.env"

EOF

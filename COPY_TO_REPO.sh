#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/AQIS-for-SmartFactory"
  exit 1
fi

TARGET="$1"
mkdir -p "$TARGET"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -av \
  --exclude='.git' \
  --exclude='server/.venv' \
  --exclude='web/node_modules' \
  --exclude='web/dist' \
  "$SCRIPT_DIR/" "$TARGET/"

echo "Copied AQIS Day 1 scaffold to: $TARGET"

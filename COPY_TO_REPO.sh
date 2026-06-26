#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/backup-directory"
  exit 1
fi

TARGET="$1"
mkdir -p "$TARGET"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -av \
  --exclude='.git' \
  --exclude='**/build' \
  --exclude='**/install' \
  --exclude='**/log' \
  --exclude='**/.venv' \
  --exclude='**/node_modules' \
  --exclude='**/dist' \
  --exclude='server/.env' \
  "$SCRIPT_DIR/" "$TARGET/"

echo "Copied AQIS project snapshot to: $TARGET"

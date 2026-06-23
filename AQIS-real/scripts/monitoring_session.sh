#!/usr/bin/env bash
set -euo pipefail

echo "AQIS monitoring session is running. Hardware nodes are managed in their own terminals."

trap 'echo "AQIS monitoring session stopped."; exit 0' INT TERM

while true; do
  sleep 3600 &
  wait $!
done

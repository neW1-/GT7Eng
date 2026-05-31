#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/Users/martin/Documents/dev/gt7eng/GT7Eng"
LOG_DIR="$ROOT_DIR/.gt7eng-run"
LOG_FILE="$LOG_DIR/streamdeck-command.log"

mkdir -p "$LOG_DIR"
cd "$ROOT_DIR"

{
  echo
  date "+%Y-%m-%d %H:%M:%S %z"
  echo "start_streamdeck.command starting"
  /bin/bash "$ROOT_DIR/start_streamdeck.sh"
} 2>&1 | tee -a "$LOG_FILE"

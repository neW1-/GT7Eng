#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${GT7ENG_RUN_DIR:-"$ROOT_DIR/.gt7eng-run"}"
GT7_PID_FILE="$RUN_DIR/gt7eng.pid"
BRIDGE_PID_FILE="$RUN_DIR/discord-bridge.pid"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

GT7ENG_PORT="${GT7ENG_PORT:-8001}"

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

collect_tree() {
  local root_pid="$1"
  local all=("$root_pid")
  local index=0
  while [[ "$index" -lt "${#all[@]}" ]]; do
    local pid="${all[$index]}"
    while IFS= read -r child; do
      [[ -n "$child" ]] && all+=("$child")
    done < <(pgrep -P "$pid" 2>/dev/null || true)
    index=$((index + 1))
  done
  printf "%s\n" "${all[@]}"
}

stop_pid_tree() {
  local label="$1"
  local pid="$2"
  if ! pid_alive "$pid"; then
    echo "$label is not running."
    return
  fi

  local pids=()
  while IFS= read -r tree_pid; do
    [[ -n "$tree_pid" ]] && pids+=("$tree_pid")
  done < <(collect_tree "$pid" | awk '!seen[$0]++')
  echo "Stopping $label: ${pids[*]}"
  kill -TERM "${pids[@]}" 2>/dev/null || true

  for _ in $(seq 1 20); do
    local still_running=0
    for child in "${pids[@]}"; do
      if pid_alive "$child"; then
        still_running=1
        break
      fi
    done
    [[ "$still_running" -eq 0 ]] && return
    sleep 0.5
  done

  echo "$label did not stop after TERM; sending KILL."
  kill -KILL "${pids[@]}" 2>/dev/null || true
}

stop_from_pid_file() {
  local label="$1"
  local file="$2"
  if [[ ! -f "$file" ]]; then
    echo "$label PID file not found."
    return
  fi

  local pid
  pid="$(cat "$file")"
  stop_pid_tree "$label" "$pid"
  rm -f "$file"
}

stop_from_pid_file "Discord bridge" "$BRIDGE_PID_FILE"
stop_from_pid_file "GT7 service" "$GT7_PID_FILE"

if lsof -nP -iTCP:"$GT7ENG_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Warning: port $GT7ENG_PORT is still in use:"
  lsof -nP -iTCP:"$GT7ENG_PORT" -sTCP:LISTEN || true
else
  echo "GT7 service port $GT7ENG_PORT is clear."
fi

echo "Stopped GT7 Race Engineer. oMLX was not stopped."

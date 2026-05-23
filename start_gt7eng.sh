#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="${GT7ENG_RUN_DIR:-"$ROOT_DIR/.gt7eng-run"}"
GT7_PID_FILE="$RUN_DIR/gt7eng.pid"
BRIDGE_PID_FILE="$RUN_DIR/discord-bridge.pid"
GT7_LOG="$RUN_DIR/gt7eng.log"
BRIDGE_LOG="$RUN_DIR/discord-bridge.log"

mkdir -p "$RUN_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

GT7ENG_HOST="${GT7ENG_HOST:-0.0.0.0}"
GT7ENG_PORT="${GT7ENG_PORT:-8001}"
GT7ENG_TELEMETRY="${GT7ENG_TELEMETRY:-live}"
GT7ENG_LLM_BASE_URL="${GT7ENG_LLM_BASE_URL:-}"

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

pid_file_alive() {
  local file="$1"
  [[ -f "$file" ]] && pid_alive "$(cat "$file")"
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts="${3:-30}"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$label is reachable: $url"
      return 0
    fi
    sleep 1
  done
  echo "$label did not become reachable: $url"
  return 1
}

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

start_gt7_service() {
  if pid_file_alive "$GT7_PID_FILE"; then
    echo "GT7 service already running with PID $(cat "$GT7_PID_FILE")."
    return
  fi

  if port_in_use "$GT7ENG_PORT"; then
    echo "Port $GT7ENG_PORT is already in use. Stop the existing process first."
    lsof -nP -iTCP:"$GT7ENG_PORT" -sTCP:LISTEN || true
    exit 1
  fi

  if [[ ! -x "$ROOT_DIR/.venv/bin/gt7eng" ]]; then
    echo "Missing $ROOT_DIR/.venv/bin/gt7eng. Run setup first: pip install -e '.[dev,voice]'"
    exit 1
  fi

  echo "Starting GT7 service on $GT7ENG_HOST:$GT7ENG_PORT..."
  nohup "$ROOT_DIR/.venv/bin/gt7eng" run \
    --host "$GT7ENG_HOST" \
    --port "$GT7ENG_PORT" \
    --telemetry "$GT7ENG_TELEMETRY" \
    >>"$GT7_LOG" 2>&1 &
  echo "$!" >"$GT7_PID_FILE"

  sleep 1
  if ! pid_file_alive "$GT7_PID_FILE"; then
    echo "GT7 service failed to start. Last log lines:"
    tail -n 80 "$GT7_LOG" || true
    exit 1
  fi

  wait_for_http "http://127.0.0.1:$GT7ENG_PORT/health" "GT7 service" 20
}

check_omlx() {
  if [[ -z "$GT7ENG_LLM_BASE_URL" ]]; then
    return
  fi

  local models_url="${GT7ENG_LLM_BASE_URL%/}/models"
  if curl -fsS \
    -H "Authorization: Bearer ${GT7ENG_LLM_API_KEY:-}" \
    "$models_url" >/dev/null 2>&1; then
    echo "oMLX/OpenAI-compatible endpoint is reachable: $GT7ENG_LLM_BASE_URL"
  else
    echo "Warning: LLM endpoint is not reachable: $GT7ENG_LLM_BASE_URL"
    echo "Intent repair will still run, but LLM-backed repair/Q&A will fail until oMLX is started."
  fi
}

start_discord_bridge() {
  if pid_file_alive "$BRIDGE_PID_FILE"; then
    echo "Discord bridge already running with PID $(cat "$BRIDGE_PID_FILE")."
    return
  fi

  if [[ ! -f "$ROOT_DIR/bridge/discord/.env" ]]; then
    echo "Missing bridge/discord/.env. Configure Discord before starting the bridge."
    exit 1
  fi

  if [[ ! -d "$ROOT_DIR/bridge/discord/node_modules" ]]; then
    echo "Missing bridge/discord/node_modules. Run: cd bridge/discord && npm install"
    exit 1
  fi

  echo "Starting Discord bridge..."
  (
    cd "$ROOT_DIR/bridge/discord"
    nohup npm start >>"$BRIDGE_LOG" 2>&1 &
    echo "$!" >"$BRIDGE_PID_FILE"
  )

  sleep 2
  if ! pid_file_alive "$BRIDGE_PID_FILE"; then
    echo "Discord bridge failed to start. Last log lines:"
    tail -n 80 "$BRIDGE_LOG" || true
    exit 1
  fi
}

start_gt7_service
check_omlx
start_discord_bridge

echo
echo "GT7 Race Engineer is starting."
echo "HUD:  http://127.0.0.1:$GT7ENG_PORT"
echo "Logs: $RUN_DIR"
echo "Use ./stop_gt7eng.sh to stop the GT7 service and Discord bridge."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
BLUETOOTH_USAGE="GT7Eng uses Bluetooth to connect to the pixel display."

resolve_path() {
  local target="$1"
  local dir
  local link

  while [[ -L "$target" ]]; do
    dir="$(cd -P "$(dirname "$target")" && pwd)"
    link="$(readlink "$target")"
    if [[ "$link" == /* ]]; then
      target="$link"
    else
      target="$dir/$link"
    fi
  done

  dir="$(cd -P "$(dirname "$target")" && pwd)"
  printf "%s/%s\n" "$dir" "$(basename "$target")"
}

find_python_app() {
  local python_exe="$1"
  local dir

  dir="$(dirname "$python_exe")"
  while [[ "$dir" != "/" ]]; do
    if [[ "$dir" == *.app && -f "$dir/Contents/Info.plist" ]]; then
      printf "%s\n" "$dir"
      return 0
    fi
    if [[ -f "$dir/Resources/Python.app/Contents/Info.plist" ]]; then
      printf "%s\n" "$dir/Resources/Python.app"
      return 0
    fi
    if [[ -f "$dir/Python.app/Contents/Info.plist" ]]; then
      printf "%s\n" "$dir/Python.app"
      return 0
    fi
    dir="$(dirname "$dir")"
  done

  return 1
}

patch_bluetooth_usage() {
  local plist="$1"

  if [[ ! -f "$plist" ]]; then
    return
  fi

  if /usr/libexec/PlistBuddy -c "Print :NSBluetoothAlwaysUsageDescription" "$plist" >/dev/null 2>&1; then
    return
  fi

  echo "Adding Bluetooth usage description to $plist..."
  /usr/libexec/PlistBuddy -c "Add :NSBluetoothAlwaysUsageDescription string $BLUETOOTH_USAGE" "$plist"
}

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing $VENV_PYTHON. Run setup first: python3 -m venv .venv && pip install -e '.[dev,voice,pixel-display]'"
  exit 1
fi

PYTHON_EXE="$(resolve_path "$VENV_PYTHON")"
if ! PY_APP="$(find_python_app "$PYTHON_EXE")"; then
  echo "Could not find a Python.app bundle for $PYTHON_EXE."
  echo "This Stream Deck wrapper only patches framework-style Python installs that contain Resources/Python.app."
  exit 1
fi

PLIST="$PY_APP/Contents/Info.plist"
FRAMEWORK_RESOURCES_PLIST="$(dirname "$PY_APP")/Info.plist"

patch_bluetooth_usage "$PLIST"
patch_bluetooth_usage "$FRAMEWORK_RESOURCES_PLIST"

echo "Re-signing $PY_APP..."
codesign --force --deep --sign - "$PY_APP"

exec "$ROOT_DIR/start_gt7eng.sh"

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ENV_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def is_local_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().lower()
    return normalized in LOCAL_HOSTS or normalized.startswith("::ffff:127.")


def format_env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if any(ch.isspace() for ch in text) or "#" in text:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


class EnvFile:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def read_values(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        values: dict[str, str] = {}
        for raw_line in self.path.read_text(encoding="utf-8").splitlines():
            match = ENV_LINE_RE.match(raw_line.strip())
            if not match:
                continue
            key, raw_value = match.groups()
            value = raw_value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            values[key] = value
        return values

    def update(self, updates: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.path.read_text(encoding="utf-8").splitlines() if self.path.exists() else []
        remaining = {key: format_env_value(value) for key, value in updates.items()}
        lines: list[str] = []

        for raw_line in existing:
            match = ENV_LINE_RE.match(raw_line.strip())
            if match and match.group(1) in remaining:
                key = match.group(1)
                lines.append(f"{key}={remaining.pop(key)}")
            else:
                lines.append(raw_line)

        if remaining:
            if lines and lines[-1].strip():
                lines.append("")
            for key, value in remaining.items():
                lines.append(f"{key}={value}")

        tmp_path = self.path.with_name(f".{self.path.name}.tmp")
        tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp_path.replace(self.path)


@dataclass(slots=True)
class BridgeHeartbeatStore:
    payload: dict[str, Any] = field(default_factory=dict)
    received_at: float | None = None

    def update(self, payload: dict[str, Any]) -> None:
        self.payload = dict(payload)
        self.received_at = time.time()

    def status(self) -> dict[str, Any]:
        return {
            "received_at": self.received_at,
            "age_seconds": None if self.received_at is None else max(0.0, time.time() - self.received_at),
            "payload": self.payload,
        }


class DiscordBridgeManager:
    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root)
        self.bridge_dir = self.project_root / "bridge" / "discord"
        run_dir = os.getenv("GT7ENG_RUN_DIR")
        self.run_dir = Path(run_dir) if run_dir else self.project_root / ".gt7eng-run"
        self.pid_file = self.run_dir / "discord-bridge.pid"
        self.log_file = self.run_dir / "discord-bridge.log"
        self.restart_required = False
        self.last_error = ""
        self.heartbeat = BridgeHeartbeatStore()

    def status(self) -> dict[str, Any]:
        pid = self._pid_from_file()
        running = self._pid_alive(pid)
        stale_pid = pid is not None and not running
        state = "running" if running else "stale_pid" if stale_pid else "stopped"
        return {
            "state": state,
            "running": running,
            "pid": pid if running or stale_pid else None,
            "pid_file": str(self.pid_file),
            "log_file": str(self.log_file),
            "env_configured": (self.bridge_dir / ".env").exists(),
            "node_modules": (self.bridge_dir / "node_modules").exists(),
            "restart_required": self.restart_required,
            "last_error": self.last_error,
            "heartbeat": self.heartbeat.status(),
        }

    def mark_restart_required(self) -> None:
        if self._pid_alive(self._pid_from_file()):
            self.restart_required = True

    def start(self) -> dict[str, Any]:
        pid = self._pid_from_file()
        if self._pid_alive(pid):
            return self.status()
        if pid is not None:
            self.pid_file.unlink(missing_ok=True)

        if not (self.bridge_dir / ".env").exists():
            self.last_error = "Missing bridge/discord/.env."
            raise RuntimeError(self.last_error)
        if not (self.bridge_dir / "node_modules").exists():
            self.last_error = "Missing bridge/discord/node_modules. Run npm install."
            raise RuntimeError(self.last_error)

        self.run_dir.mkdir(parents=True, exist_ok=True)
        log_handle = self.log_file.open("ab")
        try:
            process = subprocess.Popen(
                ["npm", "start"],
                cwd=self.bridge_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_handle.close()
        self.pid_file.write_text(str(process.pid), encoding="utf-8")
        time.sleep(0.5)
        if process.poll() is not None:
            self.last_error = "Discord bridge exited immediately. Check the bridge log."
            raise RuntimeError(self.last_error)
        self.restart_required = False
        self.last_error = ""
        return self.status()

    def stop(self) -> dict[str, Any]:
        pid = self._pid_from_file()
        if pid is None:
            return self.status()
        if not self._pid_alive(pid):
            self.pid_file.unlink(missing_ok=True)
            return self.status()

        pids = self._pid_tree(pid)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for tree_pid in pids:
                try:
                    os.kill(tree_pid, sig)
                except ProcessLookupError:
                    pass
            if sig == signal.SIGTERM:
                for _ in range(20):
                    if not any(self._pid_alive(tree_pid) for tree_pid in pids):
                        break
                    time.sleep(0.1)
                if not any(self._pid_alive(tree_pid) for tree_pid in pids):
                    break

        self.pid_file.unlink(missing_ok=True)
        return self.status()

    def restart(self) -> dict[str, Any]:
        self.stop()
        return self.start()

    def _pid_from_file(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None

    @staticmethod
    def _pid_alive(pid: int | None) -> bool:
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _pid_tree(self, root_pid: int) -> list[int]:
        pids = [root_pid]
        index = 0
        while index < len(pids):
            pid = pids[index]
            try:
                output = subprocess.check_output(
                    ["pgrep", "-P", str(pid)],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                output = ""
            for raw_child in output.splitlines():
                try:
                    child = int(raw_child)
                except ValueError:
                    continue
                if child not in pids:
                    pids.append(child)
            index += 1
        return list(reversed(pids))

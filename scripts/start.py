#!/usr/bin/env python3
"""One-command local boot for PharmaLearn.

Use this after cloning or pulling on any machine:

    uv run python scripts/start.py

What it does:
  1. Ensures `.env` exists (copies from `.env.example` if missing)
  2. Syncs Python deps with uv (installs Python 3.13 if needed)
  3. Installs the web UI deps with bun (or npm as fallback)
  4. Frees ports 8000 / 3000 if stale servers are holding them
  5. Starts API + UI and prints the URLs

Ctrl+C stops both. No Docker required.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "ui" / "web"
API_PORT = 8000
UI_PORT = 3000
CHILDREN: list[subprocess.Popen] = []


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> None:
    print(f"\n> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd or ROOT, check=check)


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _pids_on_port(port: int) -> list[int]:
    pids: set[int] = set()
    if sys.platform == "win32":
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, check=False
        ).stdout
        needle = f":{port} "
        for line in out.splitlines():
            if needle not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(int(parts[-1]))
        return sorted(pids)

    out = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True, check=False
    ).stdout
    for piece in out.split():
        if piece.isdigit():
            pids.add(int(piece))
    return sorted(pids)


def _free_port(port: int) -> None:
    if _port_free(port):
        return
    pids = _pids_on_port(port)
    if not pids:
        print(f"! port {port} busy but no owner found — retrying shortly")
        time.sleep(1)
        return
    for pid in pids:
        print(f"! freeing port {port} (pid {pid})")
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False,
                           capture_output=True)
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    time.sleep(1)


def _ensure_env() -> None:
    env = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env.exists() and example.exists():
        shutil.copy(example, env)
        print("> created .env from .env.example")


def _ensure_tools() -> None:
    if not _have("uv"):
        sys.exit("uv is required: https://docs.astral.sh/uv/getting-started/installation/")
    if not (_have("bun") or _have("npm")):
        sys.exit("bun (preferred) or npm is required for the UI")


def _sync() -> None:
    _run(["uv", "python", "install", "3.13"], check=False)
    _run(["uv", "sync"])
    if _have("bun"):
        _run(["bun", "install"], cwd=UI)
    else:
        _run(["npm", "install"], cwd=UI)


def _spawn(cmd: list[str], *, cwd: Path, title: str) -> subprocess.Popen:
    print(f"\n> starting {title}: {' '.join(cmd)}")
    kwargs: dict = {"cwd": cwd}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    proc = subprocess.Popen(cmd, **kwargs)
    CHILDREN.append(proc)
    return proc


def _shutdown(*_args) -> None:
    print("\n> stopping…")
    for proc in CHILDREN:
        if proc.poll() is not None:
            continue
        try:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            else:
                proc.send_signal(signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 5
    for proc in CHILDREN:
        remaining = max(0.1, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(0)


def main() -> None:
    os.chdir(ROOT)
    _ensure_tools()
    _ensure_env()
    _sync()
    _free_port(API_PORT)
    _free_port(UI_PORT)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    api = _spawn(
        ["uv", "run", "uvicorn", "api.main:app", "--host", "127.0.0.1",
         "--port", str(API_PORT)],
        cwd=ROOT, title="API",
    )
    ui_cmd = ["bun", "dev"] if _have("bun") else ["npm", "run", "dev"]
    ui = _spawn(ui_cmd, cwd=UI, title="UI")

    print("\nPharmaLearn is starting")
    print(f"  UI  http://localhost:{UI_PORT}")
    print(f"  API http://127.0.0.1:{API_PORT}/docs")
    print("  Ctrl+C to stop both\n")

    while True:
        if api.poll() is not None:
            print(f"! API exited with code {api.returncode}")
            _shutdown()
        if ui.poll() is not None:
            print(f"! UI exited with code {ui.returncode}")
            _shutdown()
        time.sleep(0.5)


if __name__ == "__main__":
    main()

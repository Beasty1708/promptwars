#!/usr/bin/env python3
"""
One-Command Launcher for Guardian AI
Launches FastAPI backend (port 8000) and Vite frontend (port 5173) concurrently.

Usage (CMD or PowerShell):
    python start_guardian.py
"""
import os
import sys
import subprocess
import time
import shutil
import socket

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

# ── Known Node.js install locations on Windows ──────────────────────────────
NODE_CANDIDATE_DIRS = [
    r"C:\Program Files\nodejs",
    r"C:\Program Files (x86)\nodejs",
    os.path.expanduser(r"~\AppData\Roaming\nvm\current"),
    os.path.expanduser(r"~\scoop\apps\nodejs\current"),
    os.path.expanduser(r"~\AppData\Local\Programs\nodejs"),
]


def find_node_dir() -> str | None:
    """Return the directory that contains npm.cmd, or None if not found."""
    # 1. Check PATH first (works if node is already in PATH)
    npm_in_path = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_in_path:
        return os.path.dirname(os.path.abspath(npm_in_path))
    # 2. Check well-known install dirs
    for d in NODE_CANDIDATE_DIRS:
        if os.path.isfile(os.path.join(d, "npm.cmd")):
            return d
    return None


def kill_port(port: int):
    """Kill any process listening on the given TCP port (Windows netstat/taskkill)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit() and int(pid) > 0:
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True)
                    print(f"   Freed port {port} (killed PID {pid})")
    except Exception:
        pass  # non-fatal


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    print("=" * 65)
    print(" GUARDIAN AI — PERSONAL SAFETY & MOBILITY ANOMALY PLATFORM")
    print(" Tagline: Observe. Understand. Verify. Protect.")
    print("=" * 65)

    # ── Locate Node.js ───────────────────────────────────────────────────────
    node_dir = find_node_dir()
    if node_dir is None:
        print("\n[ERROR] Node.js not found.")
        print("  Please install Node.js LTS from https://nodejs.org/")
        print("  After installing, restart your terminal and run this script again.")
        sys.exit(1)

    npm_cmd = os.path.join(node_dir, "npm.cmd")
    print(f"\n[Node.js] Found at: {node_dir}")

    # Inject node_dir into the subprocess environment so node/npm work in CMD
    env = os.environ.copy()
    env["PATH"] = node_dir + os.pathsep + env.get("PATH", "")

    # ── Free ports if already occupied ───────────────────────────────────────
    print("\n[0/3] Checking ports 8000 & 5173...")
    for port in [8000, 5173]:
        if port_in_use(port):
            print(f"   Port {port} is occupied — freeing it...")
            kill_port(port)
            time.sleep(0.8)
        else:
            print(f"   Port {port} is free.")

    # ── Seed database ─────────────────────────────────────────────────────────
    print("\n[1/3] Initializing and seeding demo database...")
    subprocess.run(
        [sys.executable, os.path.join(ROOT_DIR, "scripts", "seed_demo.py")],
        check=True
    )

    # ── Check repo size ───────────────────────────────────────────────────────
    print("\n[2/3] Verifying repository storage budget (< 9 MB)...")
    subprocess.run(
        [sys.executable, os.path.join(ROOT_DIR, "scripts", "check_repo_size.py")],
        check=True
    )

    # ── Start servers ─────────────────────────────────────────────────────────
    print("\n[3/3] Starting Guardian AI Servers...")
    print(" -> Backend API:  http://127.0.0.1:8000")
    print(" -> Swagger Docs: http://127.0.0.1:8000/docs")
    print(" -> Frontend UI:  http://127.0.0.1:5173\n")

    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "backend.app.main:app",
         "--host", "127.0.0.1",
         "--port", "8000",
         "--reload"],
        cwd=ROOT_DIR
    )

    # Install frontend deps if node_modules is missing
    nm_path = os.path.join(ROOT_DIR, "frontend", "node_modules")
    if not os.path.isdir(nm_path):
        print("[npm] node_modules not found — running npm install...")
        subprocess.run(
            [npm_cmd, "install"],
            cwd=os.path.join(ROOT_DIR, "frontend"),
            env=env,
            check=True
        )

    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=os.path.join(ROOT_DIR, "frontend"),
        env=env,
        shell=False
    )

    print("\n Guardian AI is running. Press Ctrl+C to stop both servers.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Guardian AI servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        print("Servers stopped cleanly.")


if __name__ == "__main__":
    main()

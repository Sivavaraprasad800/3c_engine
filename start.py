"""
start.py — Loads .env and starts the FRS server.

Usage:
  python start.py               ← Render/cloud: DB + API only (no AI engine)
  AI_MODE=1 python start.py     ← Local machine: full AI + cameras
"""

import os
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["FFMPEG_LOG_LEVEL"] = "quiet"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;discardcorrupt|flags;low_delay|max_delay;1000000|reorder_queue_size;10|loglevel;quiet"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"
import sys

# ── UTF-8 safe stdout (Windows cp1252 crashes on unicode prints like "→") ──
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ── Silence low-level C stderr (OpenCV/FFmpeg HEVC missing reference frame noise) ──
try:
    sys.stderr = sys.stdout  # Keep Python errors/tracebacks logging to stdout
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)
except Exception:
    pass
from pathlib import Path

# ── Load .env if it exists ─────────────────────────────────────
env_file = Path(".env")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    print("[start] Loaded .env")
else:
    print("[start] No .env found — using SQLite fallback (data/frs.db)")

# ── Auto-detect local vs Render ───────────────────────────────
# On Render, RENDER env var is always set to "true"
is_render = os.environ.get("RENDER", "").lower() == "true"
if not is_render and "AI_MODE" not in os.environ:
    # Local machine — enable AI by default
    os.environ["AI_MODE"] = "1"
    print("[start] Local machine detected — AI_MODE=1 (face engine will load)")
else:
    ai = os.environ.get("AI_MODE", "0")
    print(f"[start] AI_MODE={ai}")

import uvicorn
# Default 8001 locally — port 8000 is used by the Django project.
# Render sets PORT itself, so production is unaffected.
port = int(os.environ.get("PORT", 8001))

# ── Friendly port-in-use check (avoids the scary Errno 10048) ──
import socket
_probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    if sys.platform == "win32":
        _probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    _probe.bind(("0.0.0.0", port))
    _probe.close()
except OSError:
    print(f"")
    print(f"[start] ✋ PORT {port} IS ALREADY IN USE — another server is running!")
    print(f"[start] ➜ The dashboard is probably live at http://localhost:{port}")
    print(f"[start] ➜ To RESTART: stop the other one first (Ctrl+C in its terminal), then run: python start.py")
    sys.exit(1)

uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

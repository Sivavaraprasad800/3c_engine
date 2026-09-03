"""
camera_diagnostics.py — Camera Connection Diagnostics Log
Logs every camera event with timestamps to diagnose connection issues.
Writes to data/camera_diagnostics.log
"""
import os
import time
import threading
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("data")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "camera_diagnostics.log"

_lock = threading.Lock()


def log(event_type: str, camera_id: str, message: str, level: str = "INFO"):
    """
    Log a camera diagnostic event.

    event_type: CONNECT | DISCONNECT | FRAME | ERROR | START | STOP | RESOLUTION | FPS
    camera_id: camera identifier
    message: human-readable description
    level: INFO | WARN | ERROR
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level:5s}] [{event_type:12s}] [{camera_id:25s}] {message}"

    with _lock:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # Also print to console for immediate visibility
    color = {"INFO": "", "WARN": "WARNING: ", "ERROR": "ERROR:    "}
    print(f"{color.get(level, '')}{line}")


def log_connect_start(camera_id: str, rtsp_url: str):
    """Called when starting to connect to a camera."""
    log("CONNECT", camera_id, f"Attempting connection to {rtsp_url}", "INFO")


def log_connect_success(camera_id: str, elapsed_ms: float, width: int, height: int, fps: float):
    """Called when camera connection succeeds."""
    mp = width * height / 1_000_000
    log("CONNECT", camera_id,
        f"Connected in {elapsed_ms:.0f}ms | Resolution: {width}x{height} ({mp:.1f}MP) | FPS: {fps:.0f}",
        "INFO")


def log_connect_fail(camera_id: str, elapsed_ms: float, error: str):
    """Called when camera connection fails."""
    log("CONNECT", camera_id,
        f"FAILED after {elapsed_ms:.0f}ms: {error[:120]}",
        "ERROR")


def log_reconnect(camera_id: str, attempt: int, reason: str):
    """Called when camera reconnects."""
    log("DISCONNECT", camera_id,
        f"Reconnect attempt #{attempt}: {reason}",
        "WARN")


def log_frame_issue(camera_id: str, issue: str, frame_no: int = 0):
    """Called when a frame has issues (corrupt, gray, dropped)."""
    log("FRAME", camera_id,
        f"Frame #{frame_no}: {issue}",
        "WARN")


def log_fps(camera_id: str, capture_fps: float, ai_fps: float, queue_depth: int = 0):
    """Log current FPS status."""
    log("FPS", camera_id,
        f"Capture: {capture_fps:.1f} fps | AI: {ai_fps:.1f} fps | Queue: {queue_depth}",
        "INFO")


def log_startup_summary(cameras: list):
    """Log a summary of all cameras at startup."""
    log("START", "SYSTEM", "=" * 60, "INFO")
    log("START", "SYSTEM", f"STARTUP — {len(cameras)} camera(s) configured", "INFO")
    for cam in cameras:
        status = "ENABLED" if cam.get("enabled", True) else "DISABLED"
        url = cam.get("rtsp_url", "N/A")
        cam_type = cam.get("camera_type", "checkin")
        log("START", cam["id"],
            f"  {status} | Type: {cam_type} | URL: {url[:60]}",
            "INFO")
    log("START", "SYSTEM", "=" * 60, "INFO")


def get_log_path() -> str:
    """Return the path to the diagnostics log file."""
    return str(LOG_FILE.absolute())


def get_recent_logs(n: int = 50) -> list:
    """Return the last N lines from the log file."""
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [l.rstrip() for l in lines[-n:]]
    except Exception:
        return []

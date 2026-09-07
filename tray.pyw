"""
tray.pyw — FRS 3C Engine System Tray Application

Run this file to start FRS as a background application with a system tray icon.
- Double-click tray icon = open dashboard in browser
- Right-click = menu (Open, Stop, Start, Exit)
- No console window (use .pyw extension)
- Auto-starts the FRS server when launched
- Logs stored in data/logs/ — auto-deleted after 30 days

Usage:
  pythonw tray.pyw             (no console window)
  python tray.pyw              (with console for debugging)
"""
import os
import sys
import time
import threading
import subprocess
import webbrowser
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Load .env ───────────────────────────────────────────────────────────────
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PORT     = int(os.environ.get("PORT", 8001))
DASHBOARD_URL = f"http://localhost:{PORT}"
APP_DIR  = Path(__file__).parent
LOG_DIR  = APP_DIR / "data" / "logs"
LOG_KEEP_DAYS = 30   # delete logs older than this

SERVER_PROCESS = None
_server_lock   = threading.Lock()

# ── Logging setup ────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _log_path() -> Path:
    """Daily rotating log file: logs/frs_2026-09-07.log"""
    return LOG_DIR / f"frs_{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_path(), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("FRS_Tray")

# ── Log rotation: delete logs older than 30 days ────────────────────────────
def purge_old_logs():
    """Delete all log files older than LOG_KEEP_DAYS days."""
    cutoff = datetime.now() - timedelta(days=LOG_KEEP_DAYS)
    deleted = 0
    for f in LOG_DIR.glob("frs_*.log"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
        except Exception:
            pass
    # Also rotate camera_diagnostics.log if > 10MB
    cam_log = APP_DIR / "data" / "camera_diagnostics.log"
    if cam_log.exists() and cam_log.stat().st_size > 10 * 1024 * 1024:
        archive = LOG_DIR / f"camera_diagnostics_{datetime.now().strftime('%Y-%m-%d')}.log"
        cam_log.rename(archive)
        deleted += 1
    if deleted:
        log.info(f"[LogPurge] Deleted {deleted} log file(s) older than {LOG_KEEP_DAYS} days")

def log_purge_scheduler():
    """Run log purge once daily."""
    while True:
        purge_old_logs()
        time.sleep(24 * 60 * 60)  # wait 24 hours

# ── Build tray icon image ─────────────────────────────────────────────────────
def make_icon():
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size-2, size-2], fill=(74, 158, 255, 255))
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    text = "FRS"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text(((size-tw)//2, (size-th)//2 - 2), text, fill="white", font=font)
    return img

# ── Server management ─────────────────────────────────────────────────────────
def is_server_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{DASHBOARD_URL}/api/v1/health", timeout=2)
        return True
    except Exception:
        return False

def start_server():
    global SERVER_PROCESS
    with _server_lock:
        if SERVER_PROCESS and SERVER_PROCESS.poll() is None:
            return
        python = sys.executable
        script = str(APP_DIR / "start.py")
        server_log = open(_log_path(), "a", encoding="utf-8")
        CREATE_NO_WINDOW = 0x08000000
        SERVER_PROCESS = subprocess.Popen(
            [python, script],
            cwd=str(APP_DIR),
            creationflags=CREATE_NO_WINDOW,
            stdout=server_log,
            stderr=server_log,
        )
        log.info(f"Server started (PID {SERVER_PROCESS.pid})")

def stop_server():
    global SERVER_PROCESS
    with _server_lock:
        if SERVER_PROCESS:
            try:
                SERVER_PROCESS.terminate()
                SERVER_PROCESS.wait(timeout=8)
            except Exception:
                SERVER_PROCESS.kill()
            SERVER_PROCESS = None
            log.info("Server stopped")

def open_dashboard():
    for _ in range(45):
        if is_server_running():
            break
        time.sleep(1)
    webbrowser.open(DASHBOARD_URL)

# ── Watchdog: auto-restart server if it crashes ───────────────────────────────
def watchdog():
    time.sleep(15)
    while True:
        time.sleep(20)
        try:
            if SERVER_PROCESS and SERVER_PROCESS.poll() is not None:
                log.warning("Server crashed — restarting automatically...")
                start_server()
        except Exception:
            pass

# ── Tray menu actions ─────────────────────────────────────────────────────────
def on_open(icon, item):
    threading.Thread(target=open_dashboard, daemon=True).start()

def on_stop(icon, item):
    stop_server()
    icon.title = "FRS 3C Engine — Stopped"

def on_start(icon, item):
    start_server()
    icon.title = "FRS 3C Engine — Running"
    threading.Thread(target=open_dashboard, daemon=True).start()

def on_exit(icon, item):
    stop_server()
    icon.stop()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    import pystray
    from pystray import MenuItem as Item

    (APP_DIR / "data").mkdir(exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 60)
    log.info(f"FRS 3C Engine starting — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Log directory: {LOG_DIR}")
    log.info(f"Log retention: {LOG_KEEP_DAYS} days")
    log.info("=" * 60)

    # Purge old logs on startup
    purge_old_logs()

    # Start background threads
    threading.Thread(target=watchdog,            daemon=True).start()
    threading.Thread(target=log_purge_scheduler, daemon=True).start()

    # Start server
    start_server()

    # Open dashboard
    threading.Thread(target=open_dashboard, daemon=True).start()

    # Build tray
    icon_img = make_icon()
    menu = pystray.Menu(
        Item("📊 Open Dashboard", on_open, default=True),
        pystray.Menu.SEPARATOR,
        Item("▶ Start Server",   on_start),
        Item("■ Stop Server",    on_stop),
        pystray.Menu.SEPARATOR,
        Item("✕ Exit",           on_exit),
    )
    icon = pystray.Icon(
        name="FRS_3C_Engine",
        icon=icon_img,
        title="FRS 3C Engine — Running",
        menu=menu,
    )

    log.info(f"Tray ready — dashboard: {DASHBOARD_URL}")
    icon.run()

if __name__ == "__main__":
    main()

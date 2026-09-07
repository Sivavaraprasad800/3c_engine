"""
tray.pyw — FRS 3C Engine System Tray Application

Double-click FRS_3C_Engine.exe to run.
- Shows system tray icon (bottom-right taskbar)
- Starts FRS server in background thread
- Opens dashboard in browser automatically
- Runs 24/7, auto-restarts on crash
- 30-day log rotation
"""
import os
import sys
import time
import threading
import webbrowser
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Resolve app directory (works both as .py and as bundled .exe) ────────────
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent   # next to the .exe
    # Ensure dist/ is next to the exe (copy from _internal if needed)
    _internal_dist = Path(sys._MEIPASS) / "dist"
    _exe_dist      = APP_DIR / "dist"
    if not _exe_dist.exists() and _internal_dist.exists():
        import shutil
        shutil.copytree(str(_internal_dist), str(_exe_dist))
    # Add _MEIPASS to sys.path so bundled modules are importable
    sys.path.insert(0, sys._MEIPASS)
else:
    APP_DIR = Path(__file__).parent

# ── Load .env ─────────────────────────────────────────────────────────────────
env_file = APP_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# Change working directory to APP_DIR so relative paths work
os.chdir(str(APP_DIR))

PORT          = int(os.environ.get("PORT", 8001))
DASHBOARD_URL = f"http://localhost:{PORT}"
LOG_DIR       = APP_DIR / "data" / "logs"
LOG_KEEP_DAYS = 30

# ── Logging setup ─────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
(APP_DIR / "data").mkdir(exist_ok=True)

def _log_path() -> Path:
    return LOG_DIR / f"frs_{datetime.now().strftime('%Y-%m-%d')}.log"

_file_handler = logging.FileHandler(_log_path(), encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
_con_handler = logging.StreamHandler(sys.stdout)
_con_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _con_handler])
log = logging.getLogger("FRS")

# ── 30-day log rotation ───────────────────────────────────────────────────────
def purge_old_logs():
    cutoff = datetime.now() - timedelta(days=LOG_KEEP_DAYS)
    deleted = 0
    for f in LOG_DIR.glob("frs_*.log"):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink(); deleted += 1
        except Exception:
            pass
    # Rotate camera_diagnostics.log if > 10MB
    cam_log = APP_DIR / "data" / "camera_diagnostics.log"
    if cam_log.exists() and cam_log.stat().st_size > 10 * 1024 * 1024:
        cam_log.rename(LOG_DIR / f"camera_diagnostics_{datetime.now().strftime('%Y-%m-%d')}.log")
        deleted += 1
    if deleted:
        log.info(f"[LogPurge] Deleted {deleted} old log(s) (>{LOG_KEEP_DAYS} days)")

def _log_purge_scheduler():
    while True:
        time.sleep(24 * 60 * 60)
        try: purge_old_logs()
        except Exception: pass

# ── Server thread (runs uvicorn in-process) ───────────────────────────────────
_server_thread  = None
_server_started = threading.Event()
_server_stop    = threading.Event()

def _run_server():
    """Start uvicorn server in a background thread."""
    try:
        # Set up env vars for server
        os.environ["AI_MODE"] = os.environ.get("AI_MODE", "1")

        import uvicorn
        from server import app as frs_app

        log.info(f"Starting FRS server on port {PORT}...")
        config = uvicorn.Config(
            frs_app,
            host="0.0.0.0",
            port=PORT,
            reload=False,
            log_level="warning",   # reduce uvicorn noise
            access_log=False,
        )
        server = uvicorn.Server(config)
        _server_started.set()
        server.run()
    except Exception as e:
        log.error(f"Server error: {e}", exc_info=True)

def start_server():
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return
    _server_thread = threading.Thread(target=_run_server, daemon=True)
    _server_thread.start()
    log.info("Server thread started")

def is_server_running() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{DASHBOARD_URL}/api/v1/health", timeout=2)
        return True
    except Exception:
        return False

def open_dashboard():
    for _ in range(60):
        if is_server_running(): break
        time.sleep(1)
    webbrowser.open(DASHBOARD_URL)
    log.info(f"Dashboard opened: {DASHBOARD_URL}")

# ── Watchdog ──────────────────────────────────────────────────────────────────
def _watchdog():
    time.sleep(20)
    while True:
        time.sleep(30)
        try:
            if _server_thread and not _server_thread.is_alive():
                log.warning("Server thread died — restarting...")
                start_server()
        except Exception:
            pass

# ── Tray icon ─────────────────────────────────────────────────────────────────
def make_icon():
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size-2, size-2], fill=(74, 158, 255, 255))
    try:    font = ImageFont.truetype("arial.ttf", 18)
    except: font = ImageFont.load_default()
    text = "FRS"
    bb = draw.textbbox((0,0), text, font=font)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text(((size-tw)//2, (size-th)//2-2), text, fill="white", font=font)
    return img

def on_open(icon, item):
    threading.Thread(target=open_dashboard, daemon=True).start()

def on_restart(icon, item):
    log.info("Restart requested from tray")
    start_server()
    threading.Thread(target=open_dashboard, daemon=True).start()

def on_exit(icon, item):
    log.info("Exit requested from tray — shutting down")
    icon.stop()
    os._exit(0)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    import pystray
    from pystray import MenuItem as Item

    log.info("=" * 60)
    log.info(f"FRS 3C Engine  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"App dir: {APP_DIR}")
    log.info(f"Dashboard: {DASHBOARD_URL}")
    log.info(f"Log dir: {LOG_DIR}  |  Retention: {LOG_KEEP_DAYS} days")
    log.info("=" * 60)

    purge_old_logs()

    threading.Thread(target=_watchdog,            daemon=True).start()
    threading.Thread(target=_log_purge_scheduler, daemon=True).start()

    start_server()
    threading.Thread(target=open_dashboard, daemon=True).start()

    icon = pystray.Icon(
        name  = "FRS_3C_Engine",
        icon  = make_icon(),
        title = "FRS 3C Engine — Running",
        menu  = pystray.Menu(
            Item("📊 Open Dashboard", on_open,    default=True),
            pystray.Menu.SEPARATOR,
            Item("🔄 Restart Server", on_restart),
            pystray.Menu.SEPARATOR,
            Item("✕  Exit",           on_exit),
        ),
    )

    log.info("Tray icon ready — right-click for menu")
    icon.run()

if __name__ == "__main__":
    main()

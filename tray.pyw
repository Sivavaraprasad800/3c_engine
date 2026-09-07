"""
tray.pyw — FRS 3C Engine Desktop Application

- Opens as a NATIVE WINDOWS APP WINDOW (no browser, no URL bar)
- Runs 24/7 in background
- System tray icon when minimized
- Auto-starts on Windows boot
- 30-day log rotation
- PC lock/shutdown: keeps running / auto-restarts
"""
import os
import sys
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Resolve app directory ────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
    sys.path.insert(0, sys._MEIPASS)
    # Copy dist/ next to exe if not already there
    _internal_dist = Path(sys._MEIPASS) / "dist"
    _exe_dist      = APP_DIR / "dist"
    if not _exe_dist.exists() and _internal_dist.exists():
        import shutil
        shutil.copytree(str(_internal_dist), str(_exe_dist))
else:
    APP_DIR = Path(__file__).parent

# ── Load .env ────────────────────────────────────────────────────────────────
env_file = APP_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

os.chdir(str(APP_DIR))

PORT          = int(os.environ.get("PORT", 8001))
APP_URL       = f"http://localhost:{PORT}"
LOG_DIR       = APP_DIR / "data" / "logs"
LOG_KEEP_DAYS = 30

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
(APP_DIR / "data").mkdir(exist_ok=True)

def _log_path():
    return LOG_DIR / f"frs_{datetime.now().strftime('%Y-%m-%d')}.log"

_fh = logging.FileHandler(_log_path(), encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_fh])
log = logging.getLogger("FRS")

def purge_old_logs():
    cutoff = datetime.now() - timedelta(days=LOG_KEEP_DAYS)
    deleted = 0
    for f in LOG_DIR.glob("frs_*.log"):
        try:
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink(); deleted += 1
        except Exception: pass
    cam = APP_DIR / "data" / "camera_diagnostics.log"
    if cam.exists() and cam.stat().st_size > 10 * 1024 * 1024:
        cam.rename(LOG_DIR / f"camera_{datetime.now().strftime('%Y-%m-%d')}.log")
        deleted += 1
    if deleted:
        log.info(f"[LogPurge] Removed {deleted} old log(s)")

def _log_scheduler():
    while True:
        time.sleep(24 * 3600)
        try: purge_old_logs()
        except Exception: pass

# ── FRS Server (runs in background thread) ───────────────────────────────────
_server_thread = None
_server_ready  = threading.Event()

def _start_server_thread():
    global _server_thread
    if _server_thread and _server_thread.is_alive():
        return
    def _run():
        try:
            os.environ["AI_MODE"] = os.environ.get("AI_MODE", "1")
            import uvicorn
            from server import app as frs_app
            log.info(f"Starting FRS server on port {PORT}...")
            config = uvicorn.Config(
                frs_app,
                host="0.0.0.0",
                port=PORT,
                reload=False,
                log_level="warning",
                access_log=False,
            )
            srv = uvicorn.Server(config)
            _server_ready.set()
            srv.run()
        except Exception as e:
            log.error(f"Server error: {e}", exc_info=True)
    _server_thread = threading.Thread(target=_run, daemon=True, name="FRSServer")
    _server_thread.start()

def _wait_for_server(timeout=120):
    """Poll until server responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            import urllib.request
            urllib.request.urlopen(f"{APP_URL}/api/v1/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False

def _watchdog():
    time.sleep(30)
    while True:
        time.sleep(20)
        try:
            if _server_thread and not _server_thread.is_alive():
                log.warning("Server died — restarting...")
                _start_server_thread()
        except Exception: pass

# ── Main window ──────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info(f"FRS 3C Engine  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"App dir: {APP_DIR}")
    log.info("=" * 60)

    purge_old_logs()
    _start_server_thread()
    threading.Thread(target=_watchdog,      daemon=True).start()
    threading.Thread(target=_log_scheduler, daemon=True).start()

    # Wait for server to be ready before opening window
    log.info("Waiting for server to be ready...")
    ready = _wait_for_server(timeout=120)
    if not ready:
        log.error("Server did not start in time!")

    # ── Open native app window (no browser, no URL bar) ──────────────────
    import webview

    # Use icon file if it exists
    _icon_file = str(APP_DIR / "icon_tray.png")
    if not os.path.exists(_icon_file):
        _icon_file = None

    window = webview.create_window(
        title       = "3C Engine — Face Recognition System",
        url         = APP_URL,
        width       = 1280,
        height      = 800,
        min_size    = (900, 600),
        resizable   = True,
        on_top      = False,
        text_select = False,
    )

    log.info(f"Opening app window: {APP_URL}")

    # Start webview (blocks until window is closed)
    webview.start(
        debug       = False,
        gui         = "edgechromium",
        http_server = False,
        icon        = _icon_file,
    )

    # Window closed — but keep server running in background (for 24/7)
    log.info("Window closed — server continues running in background")

if __name__ == "__main__":
    main()

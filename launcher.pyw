"""
launcher.pyw — FRS 3C Engine Launcher

What this does:
1. On first run: starts the FRS server as a background process (auto-restart on crash)
2. Opens the native app window (no browser, no URL bar)
3. Close the window → server KEEPS RUNNING in background
4. Next time you open: just shows the window again, no restart
5. Server auto-starts on Windows boot (startup folder)

This is the correct architecture:
  Server runs forever in background (like a Windows Service)
  Window just shows/hides — totally separate from the server
"""
import os
import sys
import time
import subprocess
import threading
import logging
from pathlib import Path
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    APP_DIR  = Path(sys.executable).parent
    sys.path.insert(0, sys._MEIPASS)
    _env_src = Path(sys._MEIPASS) / ".env"
    _env_dst = APP_DIR / ".env"
    if not _env_dst.exists() and _env_src.exists():
        import shutil; shutil.copy(str(_env_src), str(_env_dst))
    # Copy dist/
    _src = Path(sys._MEIPASS) / "dist"
    _dst = APP_DIR / "dist"
    if not _dst.exists() and _src.exists():
        import shutil; shutil.copytree(str(_src), str(_dst))
else:
    APP_DIR = Path(__file__).parent

# ── Load .env ─────────────────────────────────────────────────────────────────
_env = APP_DIR / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# AppData config (org_id stored here)
_APPDATA    = Path(os.environ.get("APPDATA", str(APP_DIR)))
_CONFIG_DIR = _APPDATA / "FRS_3C_Engine"
_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_ENV = _CONFIG_DIR / "config.env"
if _CONFIG_ENV.exists():
    for line in _CONFIG_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

os.chdir(str(APP_DIR))

PORT    = int(os.environ.get("PORT", 8001))
APP_URL = f"http://localhost:{PORT}"

# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_DIR = _CONFIG_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_log_file = _LOG_DIR / f"frs_{datetime.now().strftime('%Y-%m-%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(_log_file, encoding="utf-8")]
)
log = logging.getLogger("FRS")

# ── Check if server is already running ───────────────────────────────────────
def server_alive() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(f"{APP_URL}/api/v1/health", timeout=2)
        return True
    except Exception:
        return False

# ── Start server as a separate process (keeps running after window closes) ───
_server_proc = None

def start_server_process():
    global _server_proc
    if server_alive():
        log.info("Server already running on port %d", PORT)
        return
    python = sys.executable if not getattr(sys, 'frozen', False) else None
    if python is None:
        # Running as exe — start server in a thread instead
        _start_server_thread()
        return

    log.info("Starting FRS server process...")
    CREATE_NO_WINDOW = 0x08000000
    server_log = open(_LOG_DIR / f"server_{datetime.now().strftime('%Y-%m-%d')}.log", "a", encoding="utf-8")
    _server_proc = subprocess.Popen(
        [python, str(APP_DIR / "start.py")],
        cwd=str(APP_DIR),
        creationflags=CREATE_NO_WINDOW,
        stdout=server_log,
        stderr=server_log,
    )
    log.info("Server process started (PID %d)", _server_proc.pid)

_srv_thread = None
def _start_server_thread():
    global _srv_thread
    if _srv_thread and _srv_thread.is_alive():
        return
    def _run():
        try:
            os.environ["AI_MODE"] = os.environ.get("AI_MODE", "1")
            import uvicorn
            from server import app as frs_app
            uvicorn.Server(uvicorn.Config(frs_app, host="0.0.0.0", port=PORT,
                                          reload=False, log_level="warning", access_log=False)).run()
        except Exception as e:
            log.error("Server thread error: %s", e, exc_info=True)
    _srv_thread = threading.Thread(target=_run, daemon=False, name="FRSServer")
    _srv_thread.start()

# ── Watchdog: auto-restart server if it crashes ───────────────────────────────
def _watchdog():
    time.sleep(15)
    while True:
        time.sleep(30)
        try:
            if _server_proc and _server_proc.poll() is not None:
                log.warning("Server process died — restarting...")
                start_server_process()
            elif _srv_thread and not _srv_thread.is_alive():
                log.warning("Server thread died — restarting...")
                _start_server_thread()
        except Exception: pass

# ── Wait for server ───────────────────────────────────────────────────────────
def wait_for_server(timeout=120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_alive(): return True
        time.sleep(1)
    return False

# ── Open native window ────────────────────────────────────────────────────────
def open_window():
    import webview
    org = os.environ.get("ORG_ID", "").strip()
    configured = bool(org) and org != "default"
    url   = APP_URL if configured else f"{APP_URL}/#setup"
    title = f"3C Engine — {org.replace('_',' ').title()}" if configured else "3C Engine — Setup"

    _icon = str(APP_DIR / "icon_tray.png")
    if not os.path.exists(_icon) and getattr(sys,'frozen',False):
        _icon = str(Path(sys._MEIPASS) / "icon_tray.png")
    if not os.path.exists(_icon): _icon = None

    webview.create_window(title, url, width=1280, height=800,
                           min_size=(900, 600), resizable=True, text_select=False)
    webview.start(debug=False, gui="edgechromium", http_server=False)
    # Window closed — server keeps running (it's a separate process/thread)
    log.info("App window closed — server continues in background")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("FRS 3C Engine launcher starting — %s", datetime.now().isoformat())

    # Start server (separate process — keeps running after window closes)
    start_server_process()
    threading.Thread(target=_watchdog, daemon=True).start()

    # Wait for server
    log.info("Waiting for server on port %d...", PORT)
    if not wait_for_server(120):
        log.error("Server did not start in time!")

    # Open native window
    open_window()

if __name__ == "__main__":
    main()

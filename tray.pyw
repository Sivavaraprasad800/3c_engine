"""
tray.pyw — FRS 3C Engine Desktop Application

Single-file exe behaviour:
- DB credentials embedded inside exe (users never see them)
- Org ID stored in AppData (persists across reinstalls)
- First-run: asks company name before showing dashboard
- Runs 24/7 in background, auto-start on boot
- 30-day log rotation
"""
import os
import sys
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ── Resolve paths ─────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # Running as bundled .exe
    _MEIPASS   = Path(sys._MEIPASS)
    APP_DIR    = Path(sys.executable).parent
    sys.path.insert(0, str(_MEIPASS))

    # dist/ — copy from bundle to exe directory on first run
    _src_dist = _MEIPASS / "dist"
    _dst_dist = APP_DIR / "dist"
    if not _dst_dist.exists() and _src_dist.exists():
        import shutil
        shutil.copytree(str(_src_dist), str(_dst_dist))

    # .env — load from bundle (has DB credentials embedded)
    _bundled_env = _MEIPASS / ".env"
    _env_file    = _bundled_env if _bundled_env.exists() else APP_DIR / ".env"

    # Config dir — AppData so org_id persists even if exe is moved
    _appdata    = Path(os.environ.get("APPDATA", str(APP_DIR)))
    _config_dir = _appdata / "FRS_3C_Engine"
    _config_dir.mkdir(parents=True, exist_ok=True)
    _config_env = _config_dir / "config.env"   # stores ORG_ID
    _data_dir   = _config_dir / "data"
else:
    _MEIPASS    = None
    APP_DIR     = Path(__file__).parent
    _env_file   = APP_DIR / ".env"
    _config_dir = APP_DIR
    _config_env = APP_DIR / ".env"
    _data_dir   = APP_DIR / "data"

_data_dir.mkdir(parents=True, exist_ok=True)
os.chdir(str(APP_DIR))

# ── Load embedded .env (DB credentials) ──────────────────────────────────────
def _load_env(path: Path):
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_load_env(_env_file)      # DB creds from bundle
_load_env(_config_env)    # ORG_ID from AppData config

PORT          = int(os.environ.get("PORT", 8001))
APP_URL       = f"http://localhost:{PORT}"
LOG_DIR       = _data_dir / "logs"
LOG_KEEP_DAYS = 30

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)

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
    if deleted:
        log.info(f"[LogPurge] Removed {deleted} old log(s)")

def _log_scheduler():
    while True:
        time.sleep(24 * 3600)
        try: purge_old_logs()
        except Exception: pass

# ── Org ID helpers ────────────────────────────────────────────────────────────
def get_org_id() -> str:
    return os.environ.get("ORG_ID", "").strip().lower()

def save_org_id(org_id: str):
    """Save org_id to AppData config.env so it persists."""
    org_id = org_id.strip().lower().replace(" ", "_")
    lines = []
    if _config_env.exists():
        for line in _config_env.read_text(encoding="utf-8").splitlines():
            if not line.strip().startswith("ORG_ID="):
                lines.append(line)
    lines.append(f"ORG_ID={org_id}")
    _config_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["ORG_ID"] = org_id
    log.info(f"[Setup] ORG_ID saved: '{org_id}'")

def is_configured() -> bool:
    org = get_org_id()
    return bool(org) and org != "default"

# ── FRS Server ────────────────────────────────────────────────────────────────
_server_thread = None

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
            config = uvicorn.Config(frs_app, host="0.0.0.0", port=PORT,
                                    reload=False, log_level="warning", access_log=False)
            uvicorn.Server(config).run()
        except Exception as e:
            log.error(f"Server error: {e}", exc_info=True)
    _server_thread = threading.Thread(target=_run, daemon=True, name="FRSServer")
    _server_thread.start()

def _wait_for_server(timeout=120) -> bool:
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

# ── Icon ──────────────────────────────────────────────────────────────────────
def make_icon():
    from PIL import Image
    icon_path = APP_DIR / "icon_tray.png"
    if not icon_path.exists() and _MEIPASS:
        icon_path = _MEIPASS / "icon_tray.png"
    if icon_path.exists():
        return Image.open(str(icon_path)).convert("RGBA")
    from PIL import ImageDraw, ImageFont
    size = 64
    img  = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0,0,size-1,size-1], radius=10, fill=(20,23,28,255))
    draw.ellipse([8,6,56,52], outline=(74,158,255,220), width=2)
    draw.ellipse([6,4,58,54], outline=(0,210,150,120), width=1)
    try:    font = ImageFont.truetype("arial.ttf", 14)
    except: font = ImageFont.load_default()
    draw.text((18,38), "FRS", fill=(74,158,255,255), font=font)
    return img

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info(f"FRS 3C Engine  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Config dir: {_config_dir}")
    log.info(f"ORG_ID: '{get_org_id()}' | Configured: {is_configured()}")
    log.info("=" * 60)

    purge_old_logs()
    _start_server_thread()
    threading.Thread(target=_watchdog,      daemon=True).start()
    threading.Thread(target=_log_scheduler, daemon=True).start()

    log.info("Waiting for server...")
    _wait_for_server(timeout=120)

    import webview

    # Decide which URL to open first
    if is_configured():
        start_url = APP_URL
        title = f"3C Engine — {get_org_id().replace('_', ' ').title()}"
    else:
        # First run — go to setup page
        start_url = f"{APP_URL}/#setup"
        title = "3C Engine — First Time Setup"

    log.info(f"Opening: {start_url}")

    _icon_file = str(APP_DIR / "icon_tray.png")
    if not os.path.exists(_icon_file) and _MEIPASS:
        _icon_file = str(_MEIPASS / "icon_tray.png")
    if not os.path.exists(_icon_file):
        _icon_file = None

    webview.create_window(
        title       = title,
        url         = start_url,
        width       = 1280,
        height      = 800,
        min_size    = (900, 600),
        resizable   = True,
        on_top      = False,
        text_select = False,
    )

    webview.start(debug=False, gui="edgechromium", http_server=False,
                  icon=_icon_file)

    log.info("Window closed — server continues running in background")

if __name__ == "__main__":
    main()

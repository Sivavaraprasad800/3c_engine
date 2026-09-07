"""
launcher.pyw — FRS 3C Engine Desktop App

Architecture:
- Server starts as an INDEPENDENT detached process (survives window close)
- Window is a separate pywebview process
- Close window → server KEEPS RUNNING → cameras still detecting
- Double-click again → window reopens, data still live
- PC reboot → Windows Startup shortcut relaunches everything
"""
import os, sys, time, subprocess, logging
from pathlib import Path
from datetime import datetime

APP_DIR = Path(__file__).parent
os.chdir(str(APP_DIR))

# Load .env
for _f in [APP_DIR / ".env"]:
    if _f.exists():
        for line in _f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

# AppData config
_cfg = Path(os.environ.get("APPDATA", str(APP_DIR))) / "FRS_3C_Engine"
_cfg.mkdir(parents=True, exist_ok=True)
_cfgenv = _cfg / "config.env"
if _cfgenv.exists():
    for line in _cfgenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PORT    = int(os.environ.get("PORT", 8001))
APP_URL = f"http://localhost:{PORT}"
PYTHON  = sys.executable

# Logging
_logdir = _cfg / "logs"
_logdir.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(_logdir/f"frs_{datetime.now():%Y-%m-%d}.log", encoding="utf-8")])
log = logging.getLogger("FRS")

def server_alive():
    try:
        import urllib.request
        urllib.request.urlopen(f"{APP_URL}/api/v1/health", timeout=2)
        return True
    except: return False

def start_server():
    """Start server as a DETACHED process — runs forever, survives window close."""
    if server_alive():
        log.info("Server already running")
        return
    log.info("Starting FRS server (detached)...")
    slog = open(_logdir / f"server_{datetime.now():%Y-%m-%d}.log", "a", encoding="utf-8")
    DETACHED  = 0x00000008   # survives parent exit
    NO_WINDOW = 0x08000000   # no console window
    p = subprocess.Popen(
        [PYTHON, str(APP_DIR / "start.py")],   # list = handles ] in path correctly
        cwd=str(APP_DIR),
        creationflags=DETACHED | NO_WINDOW,
        stdout=slog, stderr=slog,
        close_fds=True,
    )
    log.info(f"Server started PID={p.pid} — detached, survives window close")

def wait_server(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if server_alive(): return True
        time.sleep(1)
    return False

def open_window():
    import webview
    org = os.environ.get("ORG_ID","").strip()
    ok  = bool(org) and org not in ("","default")
    url   = APP_URL if ok else f"{APP_URL}/#setup"
    title = f"3C Engine — {org.replace('_',' ').title()}" if ok else "3C Engine — Setup"

    # Show a loading page that auto-connects when server is ready
    loading_html = f"""<!DOCTYPE html><html>
<head><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#14171c;color:#fff;display:flex;flex-direction:column;
     align-items:center;justify-content:center;height:100vh;font-family:sans-serif}}
.logo{{width:72px;height:72px;background:#4a9eff;border-radius:16px;
       display:flex;align-items:center;justify-content:center;
       font-size:28px;font-weight:700;margin-bottom:24px}}
h1{{font-size:22px;font-weight:700;margin-bottom:8px}}
p{{font-size:13px;color:#8899aa;margin-bottom:32px}}
.dots{{display:flex;gap:8px}}
.dot{{width:10px;height:10px;background:#4a9eff;border-radius:50%;
      animation:b 1.2s infinite}}
.dot:nth-child(2){{animation-delay:.2s}}
.dot:nth-child(3){{animation-delay:.4s}}
@keyframes b{{0%,60%,100%{{transform:translateY(0)}}30%{{transform:translateY(-12px)}}}}
</style>
<script>
function check(){{
  fetch('{APP_URL}/api/v1/health')
    .then(r=>r.json())
    .then(d=>{{if(d.status==='ok')window.location.href='{url}';else setTimeout(check,2000);
              document.getElementById('msg').textContent='Loading AI models...';}})
    .catch(()=>{{document.getElementById('msg').textContent='Starting server...';setTimeout(check,2000);}});
}}
window.onload=()=>setTimeout(check,500);
</script></head>
<body>
<div class="logo">3C</div>
<h1>3C Engine FRS</h1>
<p id="msg">Starting up...</p>
<div class="dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
</body></html>"""

    webview.create_window(title, html=loading_html, width=1280, height=800,
                           min_size=(900,600), resizable=True, text_select=False)
    webview.start(debug=False, gui="edgechromium", http_server=False)
    log.info("Window closed — server still running in background")

def main():
    log.info(f"=== FRS 3C Engine Launcher {datetime.now().isoformat()} ===")
    start_server()
    # Open window IMMEDIATELY with loading screen — no wait
    # The loading screen auto-connects when server is ready
    log.info("Opening app window (loading screen will connect to server when ready)...")
    open_window()

if __name__ == "__main__":
    main()

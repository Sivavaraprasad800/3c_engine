"""
tray.pyw — FRS 3C Engine System Tray Application

Run this file to start FRS as a background application with a system tray icon.
- Double-click tray icon = open dashboard in browser
- Right-click = menu (Open, Stop, Start, Exit)
- No console window (use .pyw extension)
- Auto-starts the FRS server when launched

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
from pathlib import Path

# ── Load .env ───────────────────────────────────────────────────────────────
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PORT = int(os.environ.get("PORT", 8001))
DASHBOARD_URL = f"http://localhost:{PORT}"
APP_DIR = Path(__file__).parent
SERVER_PROCESS = None
_server_lock = threading.Lock()

# ── Build tray icon image (FRS logo) ────────────────────────────────────────
def make_icon():
    """Create a simple tray icon using Pillow — blue square with 'FRS' text."""
    from PIL import Image, ImageDraw, ImageFont
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Background circle
    draw.ellipse([2, 2, size-2, size-2], fill=(74, 158, 255, 255))
    # Text
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    text = "FRS"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 2), text, fill="white", font=font)
    return img

# ── Server management ────────────────────────────────────────────────────────
def is_server_running() -> bool:
    """Check if server is responding."""
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
            return  # already running
        python = sys.executable
        script = str(APP_DIR / "start.py")
        # Start with no console window (CREATE_NO_WINDOW)
        CREATE_NO_WINDOW = 0x08000000
        SERVER_PROCESS = subprocess.Popen(
            [python, script],
            cwd=str(APP_DIR),
            creationflags=CREATE_NO_WINDOW,
            stdout=open(APP_DIR / "data" / "frs_tray.log", "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
        print(f"[Tray] Server started (PID {SERVER_PROCESS.pid})")

def stop_server():
    global SERVER_PROCESS
    with _server_lock:
        if SERVER_PROCESS:
            try:
                SERVER_PROCESS.terminate()
                SERVER_PROCESS.wait(timeout=5)
            except Exception:
                SERVER_PROCESS.kill()
            SERVER_PROCESS = None
            print("[Tray] Server stopped")

def open_dashboard():
    """Open dashboard in default browser."""
    # Wait for server to be ready (up to 30s)
    for _ in range(30):
        if is_server_running():
            break
        time.sleep(1)
    webbrowser.open(DASHBOARD_URL)

# ── Watchdog: auto-restart server if it crashes ──────────────────────────────
def watchdog():
    """Background thread: restart server if it crashes."""
    time.sleep(10)  # wait for initial startup
    while True:
        time.sleep(15)
        try:
            if SERVER_PROCESS and SERVER_PROCESS.poll() is not None:
                print("[Tray] Server crashed — restarting...")
                start_server()
        except Exception:
            pass

# ── Tray menu actions ────────────────────────────────────────────────────────
def on_open(icon, item):
    threading.Thread(target=open_dashboard, daemon=True).start()

def on_stop(icon, item):
    stop_server()

def on_start(icon, item):
    start_server()
    threading.Thread(target=open_dashboard, daemon=True).start()

def on_exit(icon, item):
    stop_server()
    icon.stop()

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    import pystray
    from pystray import MenuItem as Item

    # Ensure data/ dir exists for logs
    (APP_DIR / "data").mkdir(exist_ok=True)

    # Start server immediately
    start_server()

    # Start watchdog
    threading.Thread(target=watchdog, daemon=True).start()

    # Open dashboard after short delay
    threading.Thread(target=open_dashboard, daemon=True).start()

    # Build tray icon
    icon_img = make_icon()

    menu = pystray.Menu(
        Item("📊 Open Dashboard",  on_open, default=True),
        pystray.Menu.SEPARATOR,
        Item("▶ Start Server",  on_start),
        Item("■ Stop Server",   on_stop),
        pystray.Menu.SEPARATOR,
        Item("✕ Exit",          on_exit),
    )

    icon = pystray.Icon(
        name="FRS_3C_Engine",
        icon=icon_img,
        title="FRS 3C Engine — Running",
        menu=menu,
    )

    print(f"[Tray] FRS 3C Engine started — {DASHBOARD_URL}")
    icon.run()

if __name__ == "__main__":
    main()

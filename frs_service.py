"""
frs_service.py — FRS 3C Engine Windows Service

Runs the FRS server permanently as a Windows Service.
- Starts automatically on Windows boot
- Runs even when no user is logged in
- Survives window close / user logout
- Auto-restarts on crash (via service recovery settings)

Install:  python frs_service.py install
Start:    python frs_service.py start
Stop:     python frs_service.py stop
Remove:   python frs_service.py remove
"""
import sys
import os
import time
import threading
from pathlib import Path

APP_DIR = Path(__file__).parent
os.chdir(str(APP_DIR))

# Load .env
_env = APP_DIR / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import win32serviceutil
import win32service
import win32event
import servicemanager

class FRSService(win32serviceutil.ServiceFramework):
    _svc_name_        = "FRS_3C_Engine"
    _svc_display_name_= "FRS 3C Engine - Face Recognition"
    _svc_description_ = "Face Recognition System — 3C Engine. Provides camera-based face detection and attendance tracking."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._running   = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self._running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )
        self._run()

    def _run(self):
        """Start uvicorn server and keep it running."""
        os.environ["AI_MODE"] = os.environ.get("AI_MODE", "1")

        def server_thread():
            try:
                import uvicorn
                from server import app as frs_app
                port = int(os.environ.get("PORT", 8001))
                config = uvicorn.Config(frs_app, host="0.0.0.0", port=port,
                                        reload=False, log_level="warning", access_log=False)
                uvicorn.Server(config).run()
            except Exception as e:
                servicemanager.LogErrorMsg(f"FRS server error: {e}")

        t = threading.Thread(target=server_thread, daemon=True)
        t.start()

        # Keep service alive until stop signal
        while self._running:
            rc = win32event.WaitForSingleObject(self.stop_event, 5000)
            if rc == win32event.WAIT_OBJECT_0:
                break

        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, "")
        )


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Called by SCM (service control manager) — run as service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FRSService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FRSService)

"""Test that detached server starts correctly."""
import subprocess, sys, os, time
from pathlib import Path

APP_DIR = Path(r'd:\kk]\siva\frs_ai_model-main\frs_ai_model-main')
PYTHON  = sys.executable
slog    = open(r'C:\Users\siva\AppData\Roaming\FRS_3C_Engine\logs\test_server.log', 'w', encoding='utf-8')

DETACHED  = 0x00000008
NO_WINDOW = 0x08000000

try:
    p = subprocess.Popen(
        [PYTHON, str(APP_DIR / 'start.py')],
        cwd=str(APP_DIR),
        creationflags=DETACHED | NO_WINDOW,
        stdout=slog, stderr=slog,
        close_fds=True,
    )
    print(f'Server started PID={p.pid}')
    slog.flush()
    
    # Wait and check
    time.sleep(40)
    import urllib.request
    try:
        r = urllib.request.urlopen('http://localhost:8001/api/v1/health', timeout=3)
        print('Health check:', r.read().decode()[:80])
    except Exception as e:
        print('Health check failed:', e)
        
except Exception as e:
    print('Popen ERROR:', e)

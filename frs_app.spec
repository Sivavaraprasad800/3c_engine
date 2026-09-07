# -*- mode: python ; coding: utf-8 -*-
# FRS 3C Engine — PyInstaller spec
# Entry point: tray.pyw  (system tray app, no console)
#
# Build command (Python 3.10 only):
#   C:\Users\siva\AppData\Local\Programs\Python\Python310\Scripts\pyinstaller.exe frs_app.spec --clean --distpath exe_output --workpath build_tmp

import os
from pathlib import Path

block_cipher = None
ROOT = os.path.abspath(".")

# ── Data files bundled inside the exe ────────────────────────────────────────
datas = [
    # React frontend
    (os.path.join(ROOT, "dist"), "dist"),
    # InsightFace models
    (os.path.join(os.path.expanduser("~"), ".insightface"), ".insightface"),
    # FAISS local fallback
    *( [(os.path.join(ROOT, "face_index.faiss"), ".")] if os.path.exists(os.path.join(ROOT, "face_index.faiss")) else [] ),
    *( [(os.path.join(ROOT, "id_map.pkl"), ".")] if os.path.exists(os.path.join(ROOT, "id_map.pkl")) else [] ),
    # .env template
    (os.path.join(ROOT, ".env.example"), "."),
    # Icons
    *( [(os.path.join(ROOT, "icon_tray.png"), ".")] if os.path.exists(os.path.join(ROOT, "icon_tray.png")) else [] ),
    *( [(os.path.join(ROOT, "icon.ico"), ".")] if os.path.exists(os.path.join(ROOT, "icon.ico")) else [] ),
]

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = [
    # FastAPI / Starlette
    "fastapi", "fastapi.routing", "fastapi.middleware.cors",
    "fastapi.staticfiles", "fastapi.responses",
    "starlette", "starlette.routing", "starlette.middleware",
    "starlette.middleware.cors", "starlette.staticfiles",
    "starlette.responses", "starlette.requests",
    # Uvicorn
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    # SQLAlchemy + MySQL
    "sqlalchemy", "sqlalchemy.dialects.mysql", "sqlalchemy.dialects.mysql.pymysql",
    "sqlalchemy.pool", "sqlalchemy.engine",
    "pymysql", "pymysql.cursors",
    # InsightFace / ONNX
    "insightface", "insightface.app", "insightface.model_zoo",
    "onnxruntime", "onnxruntime.capi",
    # FAISS
    "faiss",
    # OpenCV
    "cv2",
    # NumPy / SciPy
    "numpy", "scipy", "scipy.spatial",
    # Pydantic
    "pydantic", "pydantic.v1", "annotated_types", "typing_extensions",
    # Multipart / forms
    "multipart", "python_multipart", "multipart.multipart",
    # Pystray (system tray) — kept for future use
    "pystray", "pystray._win32",
    # Pillow (for icon)
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    # PyWebView (native app window — no browser needed)
    "webview", "webview.platforms", "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "clr", "System", "System.Windows.Forms",
    # Misc
    "email_validator", "dotenv", "pickle", "json", "threading", "pathlib",
    "webbrowser", "subprocess", "logging",
    # App modules
    "server", "database", "face_engine", "camera_diagnostics",
    "global_tracker", "zone_utils", "external_events_db",
    "kloudspot_service", "camera_processor", "start",
]

a = Analysis(
    ["tray.pyw"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "pandas", "jupyter",
        "IPython", "torch", "tensorflow",
        "basicsr", "gfpgan", "realesrgan",
        "paddleocr", "paddle",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FRS_3C_Engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # NO console window — tray app runs silently
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "icon.ico") if os.path.exists(os.path.join(ROOT, "icon.ico")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FRS_3C_Engine",
)

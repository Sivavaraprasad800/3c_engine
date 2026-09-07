# -*- mode: python ; coding: utf-8 -*-
# FRS 3C Engine — PyInstaller spec — SINGLE FILE EXE
#
# Build command (Python 3.10 only):
#   C:\Users\siva\AppData\Local\Programs\Python\Python310\Scripts\pyinstaller.exe frs_app.spec --clean --distpath exe_output --workpath build_tmp

import os
from pathlib import Path

block_cipher = None
ROOT = os.path.abspath(".")

# ── Embed .env with DB credentials directly into the exe ─────────────────────
# This means users never see or need the .env file
datas = [
    # React frontend dashboard
    (os.path.join(ROOT, "dist"), "dist"),
    # InsightFace AI models
    (os.path.join(os.path.expanduser("~"), ".insightface"), ".insightface"),
    # Icons
    *( [(os.path.join(ROOT, "icon_tray.png"), ".")] if os.path.exists(os.path.join(ROOT, "icon_tray.png")) else [] ),
    *( [(os.path.join(ROOT, "icon.ico"), ".")] if os.path.exists(os.path.join(ROOT, "icon.ico")) else [] ),
    # Embed .env with production DB credentials
    (os.path.join(ROOT, ".env"), "."),
    # FAISS fallback
    *( [(os.path.join(ROOT, "face_index.faiss"), ".")] if os.path.exists(os.path.join(ROOT, "face_index.faiss")) else [] ),
    *( [(os.path.join(ROOT, "id_map.pkl"), ".")] if os.path.exists(os.path.join(ROOT, "id_map.pkl")) else [] ),
]

hiddenimports = [
    "fastapi", "fastapi.routing", "fastapi.middleware.cors",
    "fastapi.staticfiles", "fastapi.responses",
    "starlette", "starlette.routing", "starlette.middleware",
    "starlette.middleware.cors", "starlette.staticfiles",
    "starlette.responses", "starlette.requests",
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "sqlalchemy", "sqlalchemy.dialects.mysql", "sqlalchemy.dialects.mysql.pymysql",
    "sqlalchemy.pool", "sqlalchemy.engine",
    "pymysql", "pymysql.cursors",
    "insightface", "insightface.app", "insightface.model_zoo",
    "onnxruntime", "onnxruntime.capi",
    "faiss",
    "cv2",
    "numpy", "scipy", "scipy.spatial",
    "pydantic", "pydantic.v1", "annotated_types", "typing_extensions",
    "multipart", "python_multipart", "multipart.multipart",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    "pystray", "pystray._win32",
    "webview", "webview.platforms", "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "clr", "clr_loader",
    "email_validator", "dotenv", "pickle", "json", "threading", "pathlib",
    "webbrowser", "subprocess", "logging",
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

# ── SINGLE FILE exe ───────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,       # ← include binaries IN the exe (onefile mode)
    a.zipfiles,       # ← include zipfiles IN the exe
    a.datas,          # ← include all data IN the exe
    [],
    name="FRS_3C_Engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,    # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "icon.ico") if os.path.exists(os.path.join(ROOT, "icon.ico")) else None,
)
# NOTE: No COLLECT() — this is single-file mode, everything is inside the exe

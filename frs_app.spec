# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FRS 3C Engine
# Build with Python 3.10:
#   C:\Users\siva\AppData\Local\Programs\Python\Python310\Scripts\pyinstaller.exe frs_app.spec

import sys
import os
from pathlib import Path

block_cipher = None

ROOT = os.path.abspath(".")

# ── Collect all data files needed at runtime ─────────────────
datas = [
    # React frontend (built dist/)
    (os.path.join(ROOT, "dist"), "dist"),
    # InsightFace models (buffalo_l downloaded to ~/.insightface)
    (os.path.join(os.path.expanduser("~"), ".insightface"), ".insightface"),
    # FAISS local fallback files (if they exist)
    *( [(os.path.join(ROOT, "face_index.faiss"), ".")] if os.path.exists(os.path.join(ROOT, "face_index.faiss")) else [] ),
    *( [(os.path.join(ROOT, "id_map.pkl"), ".")] if os.path.exists(os.path.join(ROOT, "id_map.pkl")) else [] ),
    # .env template (NOT the real .env — that stays out of the exe)
    (os.path.join(ROOT, ".env.example"), "."),
]

# ── Hidden imports PyInstaller misses ────────────────────────
hiddenimports = [
    # FastAPI / Starlette
    "fastapi", "fastapi.routing", "fastapi.middleware.cors",
    "fastapi.staticfiles", "fastapi.responses",
    "starlette", "starlette.routing", "starlette.middleware",
    "starlette.middleware.cors", "starlette.staticfiles",
    "starlette.responses", "starlette.requests",
    # Uvicorn
    "uvicorn", "uvicorn.logging", "uvicorn.loops",
    "uvicorn.loops.auto", "uvicorn.protocols",
    "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    # SQLAlchemy
    "sqlalchemy", "sqlalchemy.dialects.mysql",
    "sqlalchemy.dialects.mysql.pymysql",
    "sqlalchemy.pool", "sqlalchemy.engine",
    # PyMySQL
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
    # Misc
    "pydantic", "pydantic.v1",
    "annotated_types", "typing_extensions",
    "multipart", "python_multipart",
    "multipart.multipart",
    "aiofiles",
    "email_validator",
    "dotenv",
    "pickle", "json", "threading", "pathlib",
    # App modules
    "database", "face_engine", "camera_diagnostics",
    "global_tracker", "zone_utils",
    "external_events_db", "kloudspot_service",
    "camera_processor",
]

a = Analysis(
    ["start.py"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy unused packages to keep size down
        "tkinter", "matplotlib", "pandas", "jupyter",
        "IPython", "PIL", "torch", "tensorflow",
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
    exclude_binaries=True,   # use COLLECT (folder) not single-file — faster startup
    name="FRS_3C_Engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # no UPX — faster build, more reliable
    console=True,            # keep console so you can see server logs
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
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

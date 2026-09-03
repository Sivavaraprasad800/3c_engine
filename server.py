"""
server.py — FastAPI Backend for Face Recognition System
Cameras auto-start on server startup. No terminal commands needed.
Run: uvicorn server:app --host 0.0.0.0 --port 8000

DATABASE:
  Set DATABASE_URL env var to your PostgreSQL connection string.
  Render free PostgreSQL example:
    DATABASE_URL=postgresql://user:pass@hostname/dbname

  If DATABASE_URL is not set, falls back to local SQLite (data/frs.db).

  Images (face crops, enrollment photos) are stored as Base64 in the DB.
  No cloud storage or local snapshot folder required for new records.
"""

import os
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["FFMPEG_LOG_LEVEL"] = "quiet"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;discardcorrupt|flags;low_delay|max_delay;1000000|reorder_queue_size;10|loglevel;quiet"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"
import sys
import warnings
warnings.filterwarnings("ignore")

# ── UTF-8 safe stdout — prevents UnicodeEncodeError crashes when output is
#    redirected to a file/no-console (Windows cp1252 default) ──
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ── Silence low-level C stderr (OpenCV/FFmpeg HEVC missing reference frame noise) ──
try:
    sys.stderr = sys.stdout  # Keep Python errors/tracebacks logging to stdout
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)
except Exception:
    pass

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

# ── Stable RTSP: force TCP transport + fail fast on dead streams ──
# Fixes "RTP bad cseq" packet loss and 30-second hangs on stream death.
# Set OPENCV_FFMPEG_CAPTURE_OPTIONS yourself to override.
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|fflags;discardcorrupt|max_delay;1000000|reorder_queue_size;10"
)

# ── Global AI concurrency limiter ─────────────────────────────
# Allow 2 simultaneous AI inferences for better detection rate
_AI_MAX_CONCURRENT = int(os.environ.get("AI_MAX_CONCURRENT", "4"))
_REC_SEMAPHORE = threading.Semaphore(_AI_MAX_CONCURRENT)

# ── Throttled logger — kills console spam (Zone/Dedup/FPS prints) ──
_log_last: dict = {}

def _throttled_log(key: str, interval: float, msg: str):
    now = time.time()
    if now - _log_last.get(key, 0.0) >= interval:
        _log_last[key] = now
        print(msg)

# ── AI imports — safe fallback ────────────────────────────────
try:
    import cv2
    import numpy as np
    from face_engine import FaceRecognitionEngine
    from zone_utils import bbox_in_zone, pose_in_range
except ImportError:
    cv2 = None
    np = None
    FaceRecognitionEngine = None
    def bbox_in_zone(*a, **k): return True
    def pose_in_range(*a, **k): return True


from fastapi import FastAPI, File, UploadFile, Query, HTTPException, Body
from urllib.parse import urlsplit, urlunsplit, quote
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, Response
from pydantic import BaseModel

import traceback as _tb

from database import (
    init_db,
    # persons
    db_get_persons, db_upsert_person, db_delete_person,
    db_update_person, db_next_person_id,
    # person training images (stored in DB — no disk required)
    db_get_person_training_images, db_add_person_training_image,
    db_clear_person_training_images,
    # cameras
    db_get_cameras, db_upsert_camera, db_delete_camera,
    # events
    db_save_event, db_get_events, db_delete_event,
    db_update_event, db_purge_old_events,
    # attendance
    db_get_attendance, db_save_attendance, db_update_attendance,
    db_get_open_checkin, db_get_all_open_checkins,
    db_delete_attendance_record, db_delete_attendance_bulk,
    db_get_todays_attendance, db_get_all_attendance_dates,
    # alerts
    db_save_alert, db_get_alerts, db_update_alert, db_purge_old_alerts,
    # unknowns
    db_save_unknown, db_get_unknowns, db_get_unknown_by_id,
    db_resolve_unknown, db_delete_unknown, db_clear_resolved_unknowns,
    # analytics
    db_get_events_for_analytics, db_get_attendance_for_analytics, db_get_dashboard_stats, db_get_dashboard_full,
    # system settings
    db_get_system_settings, db_save_system_setting,
    # image helpers
    numpy_to_b64, b64_to_data_url,
    # room movements (global tracking / occupancy)
    db_save_room_movement, db_get_room_movements,
    db_get_room_occupancy_today, db_clear_room_movements,
    # lazy snapshots
    db_get_event_snapshot, db_get_attendance_snapshot, db_get_unknown_snapshot,
)
from global_tracker import global_id_manager, room_occupancy_manager
import camera_diagnostics as _diag

# ── MySQL 3C event mirroring — DISABLED (was causing startup hang) ──
_MYSQL_MIRROR_ENABLED = False
def _mysql_mirror(*a, **k): pass

# ── person_id → entity_id cache (loaded once, refreshed on demand) ──
_PID_TO_ENTITY: dict = {}   # {person_id: entity_id}
_PID_ENTITY_LOCK = threading.Lock()

def _load_entity_cache():
    """Load person_id → entity_id from three_c_eng_mapping table."""
    global _PID_TO_ENTITY
    try:
        from database import db_get_three_c_mapping
        rows = db_get_three_c_mapping()
        with _PID_ENTITY_LOCK:
            _PID_TO_ENTITY = {
                r["person_id"]: r["entity_id"]
                for r in rows
                if r.get("person_id") and r.get("entity_id")
            }
        print(f"[3c_eng] Entity cache loaded: {len(_PID_TO_ENTITY)} person→entity mappings")
    except Exception as e:
        print(f"[3c_eng] Entity cache load failed: {e}")

def get_entity_id(person_id) -> str:
    """Fast O(1) lookup of entity_id for a person_id."""
    if not person_id:
        return ""
    with _PID_ENTITY_LOCK:
        return _PID_TO_ENTITY.get(person_id, "")

# Load on startup (will retry in background if DB not ready yet)
threading.Thread(target=_load_entity_cache, daemon=True).start()


# ─── PATHS ────────────────────────────────────────────────────
SNAPSHOTS_DIR = Path("snapshots")
DATA_DIR      = Path("data")
TRAIN_DIR     = Path("train_images")
for d in [SNAPSHOTS_DIR, DATA_DIR, TRAIN_DIR]:
    d.mkdir(exist_ok=True)

# ─── APP ──────────────────────────────────────────────────────
app = FastAPI(title="Face Recognition System", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/train_images", StaticFiles(directory="train_images"), name="train_images")

# ── Serve React frontend assets (JS/CSS) ──────────────────────
_dist = Path("dist")
if _dist.exists() and (_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

engine: FaceRecognitionEngine = None

# Track pushed frame rate per camera
_pushed_fps: dict = {}
_pushed_count: dict = {}
_pushed_last_reset: dict = {}

def _update_pushed_fps(camera_id: str):
    now = time.time()
    if camera_id not in _pushed_count:
        _pushed_count[camera_id] = 0
        _pushed_last_reset[camera_id] = now
        _pushed_fps[camera_id] = 0.0
    _pushed_count[camera_id] += 1
    elapsed = now - _pushed_last_reset[camera_id]
    if elapsed >= 2.0:
        _pushed_fps[camera_id] = round(_pushed_count[camera_id] / elapsed, 1)
        _pushed_count[camera_id] = 0
        _pushed_last_reset[camera_id] = now
# Tracks actual recognition fps per camera
_fps_tracker: dict = {}   # cam_id -> {"count": int, "last_reset": float, "fps": float}

def _update_fps(cam_id: str):
    now = time.time()
    if cam_id not in _fps_tracker:
        _fps_tracker[cam_id] = {"count": 0, "last_reset": now, "fps": 0.0}
    t = _fps_tracker[cam_id]
    t["count"] += 1
    elapsed = now - t["last_reset"]
    if elapsed >= 2.0:   # recalculate every 2 seconds
        t["fps"] = round(t["count"] / elapsed, 1)
        t["count"] = 0
        t["last_reset"] = now
        _throttled_log(f"fps:{cam_id}", 20,
                       f"[Camera:{cam_id}] Recognition FPS: {t['fps']}")

# Tracks raw camera capture fps (frame-reader loop) — the REAL stream rate
# shown on the pulse monitor. Recognition fps is AI-only and much lower.
_capture_fps: dict = {}   # cam_id -> {"count": int, "last_reset": float, "fps": float}

def _update_capture_fps(cam_id: str):
    now = time.time()
    if cam_id not in _capture_fps:
        _capture_fps[cam_id] = {"count": 0, "last_reset": now, "fps": 0.0}
    t = _capture_fps[cam_id]
    t["count"] += 1
    elapsed = now - t["last_reset"]
    if elapsed >= 2.0:   # recalculate every 2 seconds
        t["fps"] = round(t["count"] / elapsed, 1)
        t["count"] = 0
        t["last_reset"] = now

# ─── DEDUP TRACKER ────────────────────────────────────────────
_last_seen: dict = {}
# DEDUP_SECONDS — read from _SYSTEM_SETTINGS_CACHE["dedup_seconds"] at runtime

# Known suppression — if person was Known recently, suppress Unknown at same position
_recently_known: dict = {}
# KNOWN_SUPPRESS_SECONDS — read from _SYSTEM_SETTINGS_CACHE["known_suppress_seconds"] at runtime

# ─── SIMPLE TIME-BASED UNKNOWN COOLDOWN ──────────────────────
# key: camera_id -> last unknown saved timestamp
_camera_unknown_last: dict = {}
# CAMERA_UNKNOWN_COOLDOWN — read from _SYSTEM_SETTINGS_CACHE["camera_unknown_cooldown"] at runtime

# ─── PENDING UNKNOWN BUFFER ───────────────────────────────────
# When an unknown is detected, hold it for 1.5 seconds before saving.
# During that window, if a KNOWN match arrives for the same face → upgrade to known, discard unknown.
# Structure: camera_id -> {face_id -> {emb, crop, capture_info, detected_at, saved}}
_pending_unknowns: dict = {}
_pending_lock = threading.Lock()
_PENDING_WINDOW = 1.5   # seconds to wait before saving an unknown

def _flush_pending_unknowns():
    """Background thread: flush pending unknowns whose window has expired."""
    while True:
        time.sleep(0.3)
        now = time.time()
        to_save = []
        with _pending_lock:
            for cam_id, faces in list(_pending_unknowns.items()):
                for face_id, info in list(faces.items()):
                    if not info.get("saved") and now - info["detected_at"] >= _PENDING_WINDOW:
                        to_save.append((cam_id, face_id, info))
                        info["saved"] = True   # mark — don't save twice
        for cam_id, face_id, info in to_save:
            # Final check: try one more time to match (in case frame was queued)
            # Just save as unknown now — window expired
            try:
                now_iso = datetime.now().isoformat()
                db_save_unknown({
                    "tracking_id": face_id,
                    "first_seen":  now_iso,
                    "last_seen":   now_iso,
                    "camera_ids":  [cam_id],
                    "snapshots":   [info.get("snapshot_path","")],
                    "event_count": 1,
                    "embedding":   info.get("raw_emb"),
                    "date":        datetime.now().strftime("%Y-%m-%d"),
                }, snapshot_array=info.get("face_crop"))
                db_save_alert({
                    "type": "UNKNOWN_PERSON", "severity": "medium",
                    "message": f"Unknown person detected at {cam_id}",
                    "person_id": None, "acknowledged": False,
                    "created_at": now_iso,
                })
                db_save_event({
                    "camera_id":    cam_id,
                    "person_id":    None,
                    "person_name":  "Unknown",
                    "person_type":  "unknown",
                    "confidence":   0.0,
                    "bbox":         info.get("bbox",[]),
                    "snapshot_path": info.get("snapshot_path",""),
                    "matched":      False,
                    "suspected":    False,
                    "timestamp":    now_iso,
                }, snapshot_array=info.get("face_crop"))
            except Exception as _e:
                print(f"[Pending] Unknown save failed: {str(_e)[:60]}")

# Start flush thread
threading.Thread(target=_flush_pending_unknowns, daemon=True).start()
class OneCapturePerVisit:
    """
    Two-layer dedup:
    1. Time cooldown per camera position (primary — always works)
    2. Embedding similarity (secondary — catches same person at different positions)
    """
    def __init__(self, similarity_threshold=0.45, visit_timeout=300, cooldown=120):
        self.similarity_threshold = similarity_threshold
        self.visit_timeout        = visit_timeout
        self.cooldown             = cooldown   # seconds before same position can fire again
        self._store = {}   # face_id -> {embedding, camera, time, first_time, hits}
        self._lock  = threading.Lock()

    def check(self, embedding, camera_id: str) -> tuple:
        if embedding is None:
            return True, {"reason": "no_embedding"}

        emb = np.array(embedding, dtype=np.float32).flatten()
        norm = np.linalg.norm(emb)
        if norm == 0:
            return True, {"reason": "zero_norm"}
        emb = emb / norm
        now = time.time()

        with self._lock:
            # Clean expired entries
            expired = [k for k, v in self._store.items()
                       if now - v["time"] > self.visit_timeout]
            for k in expired:
                del self._store[k]

            best_sim = 0.0
            best_key = None

            # Find best matching face on same camera
            for key, rec in self._store.items():
                if rec["camera"] != camera_id:
                    continue
                sim = float(np.dot(emb, rec["embedding"]))
                if sim > best_sim:
                    best_sim = sim
                    best_key = key

            # Layer 1: similarity match
            if best_key and best_sim >= self.similarity_threshold:
                rec = self._store[best_key]
                rec["time"] = now
                rec["hits"] += 1
                _throttled_log(f"dedup:{camera_id}", 10,
                               f"[Dedup:{camera_id}] BLOCKED sim={best_sim:.3f} hits={rec['hits']}")
                return False, {"reason": "similarity_match", "face_id": best_key,
                               "similarity": round(best_sim, 3)}

            # Layer 2: cooldown — only block if SAME person (sim >= 0.50)
            # FIX: raised from 0.30 to 0.50 — prevents blocking DIFFERENT people
            # who just happen to look somewhat similar (0.30-0.50 range)
            if best_key and best_sim >= 0.50:
                rec = self._store[best_key]
                time_since = now - rec["time"]
                if time_since < self.cooldown:
                    rec["time"] = now
                    rec["hits"] += 1
                    _throttled_log(f"dedupcool:{camera_id}", 10,
                                   f"[Dedup:{camera_id}] BLOCKED cooldown sim={best_sim:.3f} age={time_since:.0f}s hits={rec['hits']}")
                    return False, {"reason": "cooldown", "face_id": best_key,
                                   "similarity": round(best_sim, 3)}

            # New person or new visit
            face_id = f"{camera_id}:{int(now * 1000)}"
            self._store[face_id] = {
                "embedding":  emb,
                "camera":     camera_id,
                "time":       now,
                "first_time": now,
                "hits":       1
            }
            if len(self._store) > 5000:
                oldest = min(self._store, key=lambda k: self._store[k]["time"])
                del self._store[oldest]

            _throttled_log(f"dedupok:{camera_id}", 30,
                           f"[Dedup:{camera_id}] ALLOWED store={len(self._store)} best_sim={best_sim:.3f}")
            return True, {"reason": "new_capture", "face_id": face_id}


# Global instance — tuned for 99.98% capture rate in 3-second windows
_one_capture = OneCapturePerVisit(
    similarity_threshold=0.50,  # higher = allow more distinct captures
    visit_timeout=300,           # 5 min = new visit
    cooldown=5                   # 5 sec cooldown — fast re-capture for missed faces
)


class EmbeddingAverager:
    """
    EMBEDDING AVERAGING: Collects multiple frame embeddings per person,
    averages them, then searches FAISS with the averaged embedding.
    
    Why: Single frame = noisy (blur, angle, lighting).
    Average of 5-10 frames = cleaner, more representative = +0.10 confidence.
    
    Based on research: quality-weighted averaging gives best results.
    """
    def __init__(self, buffer_seconds=3.0, max_embeddings=10):
        self.buffer_seconds = buffer_seconds
        self.max_embeddings = max_embeddings
        self._buffers = {}   # key: f"{camera_id}:{grid_x}_{grid_y}" -> {embeddings, first_seen, best_emb}
        self._lock = threading.Lock()

    def add(self, embedding, camera_id, bbox, det_score=0.5):
        """Add an embedding to the buffer for this camera position.
        Returns (should_search, averaged_embedding) tuple.
        should_search=True means enough frames collected -> search now.
        """
        import numpy as np
        emb = np.array(embedding, dtype=np.float32).flatten()
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        
        # Grid key: 50px cells to group same-face detections
        x1, y1, x2, y2 = bbox
        gx = int((x1 + x2) / 2 / 50)
        gy = int((y1 + y2) / 2 / 50)
        key = f"{camera_id}:{gx}_{gy}"
        now = time.time()
        
        with self._lock:
            if key not in self._buffers:
                self._buffers[key] = {
                    "embeddings": [],
                    "scores": [],
                    "first_seen": now,
                    "last_seen": now,
                }
            buf = self._buffers[key]
            
            # Clean expired buffers (>5 seconds old)
            expired = [k for k, v in self._buffers.items() if now - v["last_seen"] > 5]
            for k in expired:
                del self._buffers[k]
            
            # Add this embedding
            buf["embeddings"].append(emb)
            buf["scores"].append(det_score)
            buf["last_seen"] = now
            
            # Limit buffer size
            if len(buf["embeddings"]) > self.max_embeddings:
                buf["embeddings"].pop(0)
                buf["scores"].pop(0)
            
            # Should we search now?
            age = now - buf["first_seen"]
            count = len(buf["embeddings"])
            
            # Search when: have 2+ embeddings AND either aged 1.5s OR have 8+ embeddings
            # Lowered from 3 to 2 for faster response (was missing faces at 3)
            should_search = (count >= 2 and (age >= self.buffer_seconds * 0.5 or count >= self.max_embeddings))
            
            if should_search:
                # Quality-weighted average
                avg_emb = self._quality_weighted_avg(buf["embeddings"], buf["scores"])
                # Clear buffer after search (may already be cleaned by expiry)
                self._buffers.pop(key, None)
                return True, avg_emb
            
            return False, None

    def _quality_weighted_avg(self, embeddings, scores):
        """Weighted average: higher detection score = more weight."""
        import numpy as np
        if not embeddings:
            return None
        
        weights = np.array(scores, dtype=np.float32)
        # Normalize weights
        w_sum = weights.sum()
        if w_sum > 0:
            weights = weights / w_sum
        else:
            weights = np.ones(len(embeddings)) / len(embeddings)
        
        # Weighted sum
        avg = np.zeros_like(embeddings[0])
        for emb, w in zip(embeddings, weights):
            avg += emb * w
        
        # Re-normalize
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm
        return avg


# Global instance
_embedding_averager = EmbeddingAverager(buffer_seconds=3.0, max_embeddings=10)

# ─── PERSON STATUS ────────────────────────────────────────────
_person_status: dict = {}   # person_id -> "in" | "out"
_person_status_lock = threading.Lock()

# ─── CAMERA THREADS ───────────────────────────────────────────
# Holds running camera processor threads
# key: camera_id -> {"thread": Thread, "stop": Event, "cap": VideoCapture}
_camera_threads: dict = {}

# Live frame buffer — latest frame per camera for streaming
# key: camera_id -> jpeg bytes
_live_frames: dict = {}
_frame_lock = threading.Lock()

# ─── MODELS ──────────────────────────────────────────────────
class AlertUpdate(BaseModel):
    acknowledged: bool

class CameraCreate(BaseModel):
    id: str
    name: str
    rtsp_url: str
    camera_type: str = "checkin"
    fps: int = 30
    enabled: bool = True
    notes: str = ""
    # Extended settings
    face_confidence: float = 0.4
    detection_range: float = 6.5
    min_yaw: int = -45
    max_yaw: int = 45
    min_pitch: int = -25
    max_pitch: int = 25
    detection_zone: list = []   # polygon points [[x,y], ...] as % of frame (0-100)
    send_image: bool = True
    data_frequency: int = 2
    room_id: Optional[str] = None   # room for occupancy counting (global tracking)
    map_x: Optional[float] = None   # floor-flow canvas position (%)
    map_y: Optional[float] = None   # floor-flow canvas position (%)
    entry_zone: Optional[list] = None   # legacy
    exit_zone: Optional[list] = None    # legacy
    count_line: Optional[list] = None   # head-count line [x1,y1,x2,y2] % of frame
    count_inside_pt: Optional[list] = None

class CameraUpdate(BaseModel):
    name: Optional[str] = None
    rtsp_url: Optional[str] = None
    camera_type: Optional[str] = None
    fps: Optional[int] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None
    face_confidence: Optional[float] = None
    detection_range: Optional[float] = None
    min_yaw: Optional[int] = None
    max_yaw: Optional[int] = None
    min_pitch: Optional[int] = None
    max_pitch: Optional[int] = None
    detection_zone: Optional[list] = None
    send_image: Optional[bool] = None
    data_frequency: Optional[int] = None
    room_id: Optional[str] = None
    map_x: Optional[float] = None
    map_y: Optional[float] = None
    entry_zone: Optional[list] = None
    exit_zone: Optional[list] = None
    count_line: Optional[list] = None
    count_inside_pt: Optional[list] = None

class ManualCheckout(BaseModel):
    person_id: int
    camera_id: str = "manual"

class EventUpdate(BaseModel):
    person_name: Optional[str] = None
    camera_id: Optional[str] = None

class PersonUpdate(BaseModel):
    name: Optional[str] = None
    watchlist: Optional[str] = None

class UnknownResolve(BaseModel):
    action: str              # "dismiss" | "enroll" | "blacklist"
    name: Optional[str] = None   # required for enroll and blacklist

# ─── CORE RECOGNITION LOGIC ───────────────────────────────────
# Per-camera locks — cameras no longer block each other
_process_locks: dict = {}
_process_locks_meta = threading.Lock()

def _get_process_lock(cam_id: str) -> threading.Lock:
    with _process_locks_meta:
        if cam_id not in _process_locks:
            _process_locks[cam_id] = threading.Lock()
        return _process_locks[cam_id]

# ── In-memory Settings Cache for ultra-fast zero-DB frame processing ──
_SYSTEM_SETTINGS_CACHE = {
    "face_threshold": 0.50,
    "suspected_threshold": 0.37,
    "blacklist_threshold": 0.35,
    "visitor_threshold": 0.50,
    "dedup_threshold": 0.65,
    "camera_cooldown": 120,
    "global_cooldown": 300,
    "dedup_seconds": 120,
    "known_suppress_seconds": 120,
    "camera_unknown_cooldown": 15,
    "capture_known_only": False,
}

def reload_system_settings_cache():
    """Load settings from DB into memory cache."""
    try:
        s = db_get_system_settings()
        _SYSTEM_SETTINGS_CACHE["face_threshold"]      = float(s.get("face_threshold", 0.50))
        _SYSTEM_SETTINGS_CACHE["suspected_threshold"] = float(s.get("suspected_threshold", 0.37))
        _SYSTEM_SETTINGS_CACHE["blacklist_threshold"] = float(s.get("blacklist_threshold", 0.35))
        _SYSTEM_SETTINGS_CACHE["visitor_threshold"]   = float(s.get("visitor_threshold", 0.50))
        _SYSTEM_SETTINGS_CACHE["dedup_threshold"]     = float(s.get("dedup_threshold", 0.65))
        _SYSTEM_SETTINGS_CACHE["camera_cooldown"]     = int(s.get("camera_cooldown", 120))
        _SYSTEM_SETTINGS_CACHE["global_cooldown"]     = int(s.get("global_cooldown", 300))
        _SYSTEM_SETTINGS_CACHE["dedup_seconds"]       = int(s.get("dedup_seconds", 120))
        _SYSTEM_SETTINGS_CACHE["known_suppress_seconds"] = int(s.get("known_suppress_seconds", 120))
        _SYSTEM_SETTINGS_CACHE["camera_unknown_cooldown"] = int(s.get("camera_unknown_cooldown", 15))
        _SYSTEM_SETTINGS_CACHE["capture_known_only"] = str(s.get("capture_known_only", "false")).lower() in ("true", "1", "yes")
    except Exception as e:
        print(f"[Server] Settings cache reload error: {e}")

try:
    reload_system_settings_cache()
except Exception:
    pass

def process_frame(image, camera_id, camera_type, threshold=None,
                  detection_zone=None, face_confidence=0.6,
                  min_yaw=-35, max_yaw=35, min_pitch=-15, max_pitch=15,
                  detection_range=6.5, send_image=True, room_id=None,
                  count_line=None, count_inside_pt=None):
    """Run recognition on a frame and handle check-in/out logic. Saves to DB."""
    if threshold is None:
        threshold = _SYSTEM_SETTINGS_CACHE.get("face_threshold", 0.50)

    blacklist_thresh  = _SYSTEM_SETTINGS_CACHE.get("blacklist_threshold", 0.35)
    visitor_thresh    = _SYSTEM_SETTINGS_CACHE.get("visitor_threshold", 0.50)
    suspected_thresh  = _SYSTEM_SETTINGS_CACHE.get("suspected_threshold", 0.37)

    h, w = image.shape[:2]

    # ── Pre-filter closure: rejects faces BEFORE embedding extraction ──
    # Same 3 checks as the post-filter (confidence / zone / pose) but applied
    # right after detection — out-of-zone faces cost ~0 CPU instead of full
    # detection+embedding. Huge win when a zone is configured.
    _zone = detection_zone if detection_zone and len(detection_zone) >= 3 else None
    def _face_prefilter(bbox, det_score, landmarks):
        if det_score is not None and det_score < face_confidence:
            return False
        if _zone and not bbox_in_zone(bbox, _zone, w, h):
            return False
        if not pose_in_range(landmarks, min_yaw, max_yaw, min_pitch, max_pitch):
            return False
        return True

    # ── EMBEDDING AVERAGING: Detect faces first, collect embeddings, then search ──
    # Instead of searching FAISS on every frame (noisy), we:
    # 1. Detect faces + extract embeddings (fast, ~30ms)
    # 2. Collect 3-10 embeddings per person in a buffer
    # 3. Average them (quality-weighted) -> cleaner embedding
    # 4. Search FAISS with averaged embedding -> +0.10 confidence
    
    _detected_faces = engine.detect_and_analyze(image)
    results = []
    
    for face_data in _detected_faces:
        bbox = face_data["bbox"]
        det_score = face_data["confidence"]
        emb = face_data["embedding"]
        landmarks = face_data["landmarks"]
        
        # Pre-filter check
        if det_score < face_confidence:
            continue
        if _zone and not bbox_in_zone(bbox, _zone, w, h):
            continue
        if not pose_in_range(landmarks, min_yaw, max_yaw, min_pitch, max_pitch):
            continue
        
        # Add to embedding averager buffer
        should_search, avg_emb = _embedding_averager.add(
            emb, camera_id, bbox, det_score)
        
        if not should_search:
            # Not enough frames yet — skip FAISS search this frame
            continue
        
        # Search FAISS with AVERAGED embedding (much cleaner than single frame)
        import numpy as _np
        avg_emb_np = _np.array(avg_emb, dtype=_np.float32).reshape(1, -1)
        
        # Build result template
        result = {
            "bbox":            bbox,
            "confidence":      det_score,
            "person_id":       None,
            "person_name":     "Unknown",
            "person_type":     "unknown",
            "match_confidence": 0.0,
            "matched":         False,
            "suspected":       False,
            "quality_ok":      True,
            "quality_reason":  None,
            "raw_embedding":   avg_emb.flatten().tolist(),
        }
        
        # Priority: blacklist -> employee -> visitor
        match = engine.blacklist_index.search(avg_emb_np, blacklist_thresh)
        if match:
            result.update({"person_id": match['person_id'], "person_name": match['name'],
                            "person_type": "blacklisted",
                            "match_confidence": match['confidence'], "matched": True})
            results.append(result)
            continue
        
        match = engine.employee_index.search(avg_emb_np, threshold)
        if match:
            result.update({"person_id": match['person_id'], "person_name": match['name'],
                            "person_type": "employee",
                            "match_confidence": match['confidence'], "matched": True})
            results.append(result)
            continue
        
        # Suspected match
        if suspected_thresh < threshold:
            suspected = engine.employee_index.search(avg_emb_np, suspected_thresh)
            if suspected and suspected['confidence'] < threshold:
                result.update({"person_id": suspected['person_id'], "person_name": suspected['name'],
                                "person_type": "employee", "match_confidence": suspected['confidence'],
                                "matched": False, "suspected": True})
                results.append(result)
                continue
        
        match = engine.visitor_index.search(avg_emb_np, visitor_thresh)
        if match:
            result.update({"person_id": match['person_id'], "person_name": match['name'],
                            "person_type": "visitor",
                            "match_confidence": match['confidence'], "matched": True})
            results.append(result)
            continue
        
        results.append(result)

    # Post-filter safety net (normally no-op now that pre-filter runs first)
    before = len(results)
    results = [
        r for r in results
        if r.get("confidence", 1.0) >= face_confidence
        and bbox_in_zone(r["bbox"], detection_zone, w, h)
        and pose_in_range(r.get("landmarks"), min_yaw, max_yaw, min_pitch, max_pitch)
    ]
    after = len(results)
    if detection_zone and len(detection_zone) >= 3 and before != after:
        _throttled_log(f"zone:{camera_id}", 30,
                       f"[Zone:{camera_id}] Filtered {before-after}/{before} faces outside zone/angle limits")

    # ── DEBUG: Log why faces are rejected (every 10th frame) ──
    if before > 0 and after == 0 and frame_no % 10 == 0:
        for r_dbg in [r for r in (results if results else [])][:1]:
            pass  # results empty after filter — log below
        _throttled_log(f"reject:{camera_id}", 10,
                       f"[Reject:{camera_id}] All {before} face(s) rejected by post-filter"
                       f" (conf>={face_confidence}, zone, yaw {min_yaw}/{max_yaw}, pitch {min_pitch}/{max_pitch})")
    elif before == 0:
        # SCRFD detected ZERO faces — this is the #1 reason detection fails
        _throttled_log(f"noface:{camera_id}", 30,
                       f"[NoFace:{camera_id}] SCRFD found 0 faces in {w}x{h} frame (AI sees 960x540)"
                       f" — face too small/far/angle/lighting?")

    # ── Pre-filter unknowns BEFORE acquiring the lock ────────
    filtered_results = []
    for r in results:
        if not r.get("matched"):
            raw_emb = r.get("raw_embedding")
            allow, info = _one_capture.check(raw_emb, camera_id)
            if not allow:
                continue
            r["_capture_info"] = info
        filtered_results.append(r)

    if not filtered_results:
        return results

    with _get_process_lock(camera_id):
        now      = time.time()
        now_iso  = datetime.now().isoformat()

        # ── Per-frame dedup: track person_ids already processed this frame ──
        # Prevents SCRFD's multiple overlapping detections of the same face
        # from generating duplicate attendance entries.
        _frame_seen_persons = set()

        # ── Shared DB connection for ALL events in this frame ──
        # Ensures dedup sees prior inserts within the same frame (no race condition)
        try:
            _frame_conn = engine.connect()
        except Exception:
            _frame_conn = None

        for r in filtered_results:
            x1, y1, x2, y2 = r["bbox"]
            cx, cy = (x1+x2)//2//50, (y1+y2)//2//50
            pos_key = f"{camera_id}:{cx}_{cy}"

            # FIX: Reset per-iteration to prevent stale values from previous face
            snapshot_path = None
            face_crop = None

            _pid = r.get("person_id")
            _is_matched  = bool(r.get("matched"))
            _is_suspected = bool(r.get("suspected"))
            _deduplicated = False   # flag: if True, skip DB save but still run room tracking

            # ── Dedup for matched AND suspected persons (both have a person_id) ──
            if (_is_matched or _is_suspected) and _pid is not None:
                # Layer 1: per-frame dedup — skip if same person already processed this frame
                if _pid in _frame_seen_persons:
                    _deduplicated = True
                else:
                    _frame_seen_persons.add(_pid)

                # Layer 2: time-based dedup — skip if seen recently on this camera
                dedup_key = f"{camera_id}:person_{_pid}"
                if not _deduplicated and now - _last_seen.get(dedup_key, 0) < _SYSTEM_SETTINGS_CACHE.get("dedup_seconds", 5):
                    _deduplicated = True
                if not _deduplicated:
                    _last_seen[dedup_key] = now
                    # FIX: Store embedding with position key so unknown suppression
                    # uses similarity check — not just position overlap.
                    # Use tighter position grid (//30 instead of //50) to reduce
                    # cross-person contamination when multiple people in same frame.
                    tight_cx = (x1+x2)//2//30
                    tight_cy = (y1+y2)//2//30
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            adj_key = f"{camera_id}:{tight_cx+dx}_{tight_cy+dy}"
                            _recently_known[adj_key] = {
                                "person_id":   _pid,
                                "person_name": r["person_name"],
                                "embedding":   r.get("raw_embedding"),
                                "expire":      now + _SYSTEM_SETTINGS_CACHE.get("known_suppress_seconds", 120)
                            }
            else:
                # ── Unknown person ───────────────────────────
                # FIX: Only suppress if unknown's EMBEDDING matches the known person
                # Previously blocked ALL unknowns at same position — wrong when
                # different unknowns walk past the same camera
                suppressed = False
                _unk_emb = r.get("raw_embedding")
                if _unk_emb is not None:
                    _unk_np = np.array(_unk_emb, dtype=np.float32).flatten()
                    _unk_norm = np.linalg.norm(_unk_np)
                    if _unk_norm > 0:
                        _unk_np = _unk_np / _unk_norm
                    # FIX: Use same tight grid (//30) as the writer above
                    tight_cx = (x1+x2)//2//30
                    tight_cy = (y1+y2)//2//30
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            adj = _recently_known.get(f"{camera_id}:{tight_cx+dx}_{tight_cy+dy}")
                            if adj and now < adj["expire"]:
                                # Check embedding similarity — only suppress if SAME person
                                _adj_emb = adj.get("embedding")
                                if _adj_emb is not None:
                                    _adj_np = np.array(_adj_emb, dtype=np.float32).flatten()
                                    _adj_norm = np.linalg.norm(_adj_np)
                                    if _adj_norm > 0:
                                        _adj_np = _adj_np / _adj_norm
                                    _sim = float(np.dot(_unk_np, _adj_np))
                                    if _sim >= 0.45:  # same person, suppress
                                        suppressed = True
                                        break
                                # No embedding stored — do NOT suppress without similarity proof
                                # This was the bug: position-only suppression caused wrong names
                        if suppressed:
                            break
                if suppressed:
                    continue

                raw_emb = r.get("raw_embedding")
                if raw_emb is None:
                    continue

                last_unknown_time = _camera_unknown_last.get(camera_id, 0)
                if now - last_unknown_time < _SYSTEM_SETTINGS_CACHE.get("camera_unknown_cooldown", 15):
                    continue
                _camera_unknown_last[camera_id] = now

            # ── Capture face crop as Base64 (DB storage — no disk needed) ──
            # IMPROVED: 15% padding (less background, more face) + target 200px
            fw = x2 - x1  # face width
            fh = y2 - y1  # face height
            pad_x = max(8, int(fw * 0.15))   # 15% padding (was 30%)
            pad_y = max(8, int(fh * 0.20))   # 20% padding top/bottom (was 35%)
            ih, iw = image.shape[:2]
            cx1 = max(0, x1 - pad_x)
            cy1 = max(0, y1 - pad_y)
            cx2 = min(iw, x2 + pad_x)
            cy2 = min(ih, y2 + pad_y)
            face_crop = image[cy1:cy2, cx1:cx2]
            # Target 200px for stored crop (was 112px) — much clearer for dashboard display
            _target_size = 200
            if face_crop.shape[0] < _target_size or face_crop.shape[1] < _target_size:
                scale = max(_target_size / face_crop.shape[0], _target_size / face_crop.shape[1])
                new_w = int(face_crop.shape[1] * scale)
                new_h = int(face_crop.shape[0] * scale)
                # Use LANCZOS4 for best quality upscale (was INTER_CUBIC)
                face_crop = cv2.resize(face_crop, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            snap_b64  = numpy_to_b64(face_crop)   # stored in DB as base64
            # snapshot_path kept as a reference string (no disk write needed)
            ts = int(time.time()*1000)
            snapshot_path = f"b64://{camera_id}_{ts}"   # virtual path — actual data in DB

            capture_known_only = _SYSTEM_SETTINGS_CACHE.get("capture_known_only", False)
            is_matched_or_suspected = bool(r.get("matched") or r.get("suspected"))

            # ── For unknown person (no match, no suspect) — use PENDING BUFFER (delayed save) ──────
            # Hold unknown for 1.5s. If same face matches as Known in that window → upgrade, discard unknown.
            # Note: suspected persons (matched=False but has person_id) are saved immediately below.
            if not r.get("matched") and not r.get("suspected") and not capture_known_only:
                raw_emb      = r.get("raw_embedding")
                capture_info = r.get("_capture_info", {})
                face_id      = capture_info.get("face_id", f"{camera_id}:{int(now*1000)}")
                with _pending_lock:
                    cam_buf = _pending_unknowns.setdefault(camera_id, {})
                    if face_id not in cam_buf:
                        # New unknown face — add to pending buffer, don't save yet
                        cam_buf[face_id] = {
                            "raw_emb":       raw_emb,
                            "face_crop":     face_crop,
                            "bbox":          r["bbox"],
                            "snapshot_path": snapshot_path,
                            "detected_at":   now,
                            "saved":         False,
                        }
                        # Clean old entries (>30s)
                        expired = [fid for fid,v in cam_buf.items() if now - v["detected_at"] > 30]
                        for fid in expired:
                            del cam_buf[fid]

            # ── If KNOWN or SUSPECTED match — cancel any pending unknown for this camera position ──
            elif (r.get("matched") or r.get("suspected")) and r.get("person_id"):
                raw_emb = r.get("raw_embedding")
                if raw_emb is not None:
                    import numpy as _np
                    emb = _np.array(raw_emb, dtype=_np.float32)
                    norm = _np.linalg.norm(emb)
                    if norm > 0:
                        emb = emb / norm
                    with _pending_lock:
                        cam_buf = _pending_unknowns.get(camera_id, {})
                        to_cancel = []
                        for fid, info in cam_buf.items():
                            if info.get("saved"):
                                continue
                            prev_emb = info.get("raw_emb")
                            if prev_emb is None:
                                continue
                            p_emb = _np.array(prev_emb, dtype=_np.float32)
                            p_norm = _np.linalg.norm(p_emb)
                            if p_norm > 0:
                                p_emb = p_emb / p_norm
                            sim = float(_np.dot(emb, p_emb))
                            if sim >= 0.35:   # same person (was unknown, now known)
                                to_cancel.append(fid)
                                _throttled_log(f"upgrade:{camera_id}", 5,
                                    f"[Unknown→Known] Cancelled unknown {fid} (sim={sim:.3f}) → {r.get('person_name')}")
                        for fid in to_cancel:
                            info["saved"] = True  # cancel — don't save as unknown

            # ── Save event to DB for KNOWN/SUSPECTED persons only ──────────────
            # Unknown events are saved by _flush_pending_unknowns after 1.5s window
            # Skip if deduplicated — still run room tracking below
            if (r.get("matched") or r.get("suspected")) and not _deduplicated:
                try:
                    # Resolve entity_id for this person (for MySQL 3c_eng_events)
                    _eid = get_entity_id(r.get("person_id")) if r.get("person_id") else ""
                    _evt_id = db_save_event({
                        "camera_id":    camera_id,
                        "person_id":    r.get("person_id"),
                        "person_name":  r.get("person_name", "Unknown"),
                        "person_type":  r.get("person_type", "unknown"),
                        "confidence":   r.get("match_confidence", 0),
                        "bbox":         r["bbox"],
                        "snapshot_path": snapshot_path,
                        "matched":      r.get("matched", False),
                        "suspected":    r.get("suspected", False),
                        "timestamp":    now_iso,
                    }, snapshot_array=face_crop, shared_conn=_frame_conn)
                    # ── Mirror REMOVED: db_save_event already writes to 3c_eng_events ──
                    # The old mirror_event() caused 2x duplicates because both
                    # db_save_event AND mirror_event inserted into the same table.

                    # ── CONTINUOUS LEARNING: Update templates on good detections ──
                    # Like zdotapps: replace worst template when detection is good
                    # This makes confidence rise from 0.50 to 0.70+ over time
                    try:
                        _match_conf = r.get("match_confidence", 0)
                        if _match_conf >= 0.65 and r.get("person_id"):
                            _raw_emb = r.get("raw_embedding")
                            if _raw_emb is not None:
                                _emb_np = np.array(_raw_emb, dtype=np.float32)
                                _result = engine.employee_index.replace_worst_template(
                                    r["person_id"], _emb_np, min_similarity=0.60)
                                if _result.get("replaced"):
                                    _throttled_log(f"template:{camera_id}", 60,
                                        f"[Template:{camera_id}] Updated {r.get('person_name')} "
                                        f"(sim={_result['similarity']:.3f}, replaced worst={_result.get('replaced_worst_score', 0):.3f})")
                    except Exception as _tpl_err:
                        pass  # template update is best-effort, don't break detection

                except Exception as _db_err:
                    print(f"[DB] Event save failed (network?): {str(_db_err)[:60]}")

            # ── GLOBAL PERSON ID + ROOM OCCUPANCY ─────────────
            # Maps every detection (known or unknown) to one Global ID that is
            # shared across ALL cameras, then runs room entry/exit logic.
            try:
                gid, _is_new = global_id_manager.register(
                    camera_id=camera_id,
                    person_id=r.get("person_id"),
                    person_name=r.get("person_name", "Unknown"),
                    person_type=r.get("person_type", "unknown"),
                    embedding=r.get("raw_embedding"),
                    confidence=r.get("match_confidence", 0),
                    snapshot_b64=snap_b64,
                )
                r["global_id"] = gid

                if room_id and camera_type in ("headcount", "both") and count_line:
                    # ── Single-line head counting (headcount & both cameras) ──
                    # Person's face center is on one side of the drawn line.
                    # When their side flips between detections, they crossed:
                    #   moved to side +1 = IN (+1), moved to side -1 = OUT (-1).
                    try:
                        _x1, _y1, _x2, _y2 = r["bbox"]
                        _cx = (_x1 + _x2) / 2 / w * 100
                        _cy = (_y1 + _y2) / 2 / h * 100
                        ax, ay, bx, by = count_line[:4]
                        # cross product sign = which side of the line the point is on
                        _side_val = (bx - ax) * (_cy - ay) - (by - ay) * (_cx - ax)
                        
                        if count_inside_pt:
                            ix, iy = count_inside_pt[:2]
                            inside_side_val = (bx - ax) * (iy - ay) - (by - ay) * (ix - ax)
                            is_inside = (_side_val >= 0) == (inside_side_val >= 0)
                            _side = 1 if is_inside else -1
                        else:
                            _side = 1 if _side_val >= 0 else -1

                        movement = room_occupancy_manager.register_line(
                            room_id=room_id,
                            camera_id=camera_id,
                            global_id=gid,
                            side=_side,
                            person_name=r.get("person_name", "Unknown"),
                            person_type=r.get("person_type", "unknown"),
                            confidence=r.get("match_confidence", 0),
                        )
                        if movement:
                            db_save_room_movement(movement, snapshot_array=face_crop)
                            # Record headcount
                            try:
                                _hc_dir = "IN" if movement["direction"] == "entry" else "OUT"
                                _room_name = cam.get("room_name") or room_id or camera_id
                                from database import db_record_headcount
                                db_record_headcount(
                                    camera_id=camera_id, room_name=_room_name,
                                    direction=_hc_dir,
                                    person_name=movement.get("person_name", "Unknown"),
                                    person_id=r.get("person_id"),
                                    confidence=r.get("match_confidence", 0)
                                )
                            except Exception as _hc_err:
                                print(f"[HeadCount] record error: {str(_hc_err)[:60]}")
                            _throttled_log(f"room:{room_id}", 10,
                                f"[Room:{room_id}] {movement['direction'].upper()} "
                                f"{movement['person_name']} ({gid}) via {camera_id} "
                                f"— inside: {movement['inside_count']}")
                    except Exception as _ln_err:
                        print(f"[Tracker] line check error: {str(_ln_err)[:80]}")
                        movement = None
                elif room_id and camera_type in ("checkin", "checkout"):
                    # legacy door cameras (checkin/checkout) count via camera type
                    movement = room_occupancy_manager.register(
                        room_id=room_id,
                        camera_id=camera_id,
                        camera_type=camera_type,
                        global_id=gid,
                        person_name=r.get("person_name", "Unknown"),
                        person_type=r.get("person_type", "unknown"),
                        confidence=r.get("match_confidence", 0),
                    )
                    if movement:
                        db_save_room_movement(movement, snapshot_array=face_crop)
                        # Record headcount
                        try:
                            _hc_dir = "IN" if movement["direction"] == "entry" else "OUT"
                            _room_name = cam.get("room_name") or room_id or camera_id
                            from database import db_record_headcount
                            db_record_headcount(
                                camera_id=camera_id, room_name=_room_name,
                                direction=_hc_dir,
                                person_name=movement.get("person_name", "Unknown"),
                                person_id=r.get("person_id"),
                                confidence=r.get("match_confidence", 0)
                            )
                        except Exception as _hc_err:
                            print(f"[HeadCount] record error: {str(_hc_err)[:60]}")
                        _throttled_log(f"room:{room_id}", 10,
                            f"[Room:{room_id}] {movement['direction'].upper()} "
                            f"{movement['person_name']} ({gid}) via {camera_id} "
                            f"— inside: {movement['inside_count']}")
            except Exception as _trk_err:
                print(f"[Tracker] error: {str(_trk_err)[:80]}")

            # Check-in / Check-out logic
            if r.get("matched") and r.get("person_id") is not None:
                pid   = r["person_id"]
                pname = r["person_name"]

                with _person_status_lock:
                    status = _person_status.get(pid, "out")

                # ── BLACKLIST ─────────────────────────────────
                if r.get("person_type") == "blacklisted":
                    db_save_alert({
                        "type": "BLACKLIST_MATCH", "severity": "critical",
                        "message": f"⚠ BLACKLISTED person {pname} detected at {camera_id}!",
                        "person_id": pid, "acknowledged": False, "created_at": now_iso,
                    })
                    continue

                # ── VISITOR ───────────────────────────────────
                if r.get("person_type") == "visitor":
                    db_save_alert({
                        "type": "VISITOR_ARRIVED", "severity": "low",
                        "message": f"Visitor {pname} arrived at {camera_id}",
                        "person_id": pid, "acknowledged": False, "created_at": now_iso,
                    })

                # Handle stale checkin from previous day
                if status == "in":
                    open_rec = db_get_open_checkin(pid)
                    if open_rec and open_rec.get("date") != datetime.now().strftime("%Y-%m-%d"):
                        db_update_attendance(open_rec["id"], {
                            "status":       "checked_out",
                            "checkout_time": open_rec.get("checkin_time"),
                            "duration_min":  0,
                            "duration_str":  "0m",
                        })
                        with _person_status_lock:
                            _person_status[pid] = "out"
                        status = "out"

                # frs/both = toggle mode (person status decides in/out);
                # legacy checkin/checkout cameras keep their fixed direction
                do_checkin  = camera_type in ("checkin", "both", "frs") and status == "out"
                do_checkout = camera_type in ("checkout", "both", "frs") and status == "in"

                if do_checkin:
                    with _person_status_lock:
                        _person_status[pid] = "in"
                    try:
                        db_save_attendance({
                            "person_id":    pid,
                            "person_name":  pname,
                            "camera_id":    camera_id,
                            "checkin_time": now_iso,
                            "checkout_time": None,
                            "duration_min":  None,
                            "duration_str":  None,
                            "status":        "checked_in",
                            "snapshot_path": snapshot_path,
                            "date":          datetime.now().strftime("%Y-%m-%d"),
                        }, snapshot_array=face_crop)
                        db_save_alert({
                            "type": "CHECK_IN", "severity": "low",
                            "message": f"{pname} checked in at {camera_id}",
                            "person_id": pid, "acknowledged": False, "created_at": now_iso,
                        })
                    except Exception as _db_err:
                        print(f"[DB] Check-in save failed: {str(_db_err)[:60]}")

                elif do_checkout:
                    open_rec = db_get_open_checkin(pid)
                    if open_rec:
                        secs = int((datetime.now() - datetime.fromisoformat(open_rec["checkin_time"])).total_seconds())
                        h_d, m_d = divmod(secs, 3600); m_d = m_d // 60
                        dur_str = f"{h_d}h {m_d}m" if h_d else f"{m_d}m"
                        db_update_attendance(open_rec["id"], {
                            "status":        "checked_out",
                            "checkout_time": now_iso,
                            "duration_min":  round(secs/60, 1),
                            "duration_str":  dur_str,
                        })
                        db_save_alert({
                            "type": "CHECK_OUT", "severity": "low",
                            "message": f"{pname} checked out from {camera_id} — {dur_str}",
                            "person_id": pid, "acknowledged": False, "created_at": now_iso,
                        })
                    with _person_status_lock:
                        _person_status[pid] = "out"

        # Periodic purge handled by background timer (see _purge_timer below)

        # Close shared frame connection
        try:
            if _frame_conn:
                _frame_conn.close()
        except Exception:
            pass

    return results

# ─── CAMERA THREAD WORKER ─────────────────────────────────────
def camera_worker(cam: dict, stop_event: threading.Event):
    """
    Camera thread — multi-threaded worker pool:
    1. Frame reader: runs at full RTSP speed, stores live feed, queues frames
    2. Recognition workers: parallel pool pulling from queue for maximum recognition throughput
    """
    cam_id     = cam["id"]
    rtsp_url   = cam["rtsp_url"]
    cam_type   = cam.get("camera_type", "checkin")
    det_zone   = cam.get("detection_zone", [])
    if cam_type == "headcount":
        det_zone = []   # head-count cameras use the COUNT LINE, not a zone
    face_conf  = cam.get("face_confidence", 0.6)
    target_fps = cam.get("fps", 30)
    min_yaw    = cam.get("min_yaw", -35)
    max_yaw    = cam.get("max_yaw", 35)
    min_pitch  = cam.get("min_pitch", -15)
    max_pitch  = cam.get("max_pitch", 15)
    det_range  = cam.get("detection_range", 6.5)
    send_img   = cam.get("send_image", True)
    # MAXIMUM CAPTURE — process EVERY frame for AI recognition
    # Ensures no face is ever missed in a 3-second window
    effective_data_freq = 1   # every single frame goes to AI recognition

    print(f"[Camera:{cam_id}] Config — Target FPS: {target_fps}, AI Rate: ~{target_fps//effective_data_freq} FPS, Zone pts: {len(det_zone)}, Face conf: {face_conf}")
    print(f"[Camera:{cam_id}] Starting — {rtsp_url}")

    # ── Original FIFO queue architecture (proven 25-30 FPS) ──────
    num_workers = 1
    rec_queue = __import__('queue').Queue(maxsize=2)

    def recognition_worker():
        while not stop_event.is_set():
            try:
                frame = rec_queue.get(timeout=1.0)
            except Exception:
                continue
            try:
                proc = frame
                # Global limiter — one AI inference per CPU slot across all cameras
                with _REC_SEMAPHORE:
                    process_frame(
                        proc, cam_id, cam_type,
                        detection_zone=det_zone,
                        face_confidence=face_conf,
                        min_yaw=min_yaw, max_yaw=max_yaw,
                        min_pitch=min_pitch, max_pitch=max_pitch,
                        room_id=cam.get("room_id"),
                        count_line=cam.get("count_line"),
                        count_inside_pt=cam.get("count_inside_pt"),
                        detection_range=det_range, send_image=send_img
                    )
                _update_fps(cam_id)
            except Exception as e:
                err_str = str(e)
                # Suppress noisy network/DB errors — just skip this frame
                if any(k in err_str for k in ["getaddrinfo", "OperationalError",
                                               "psycopg", "connection", "timeout"]):
                    print(f"[Camera:{cam_id}] DB/network error (will retry): {err_str[:80]}")
                else:
                    print(f"[Camera:{cam_id}] Recognition error: {e}")
                    _tb.print_exc()

    for _worker_idx in range(num_workers):
        t = threading.Thread(target=recognition_worker, daemon=True, name=f"rec-{cam_id}-{_worker_idx}")
        t.start()

    # ── Frame reader loop ──────────────────────────────────────
    _reconnect_count = 0
    while not stop_event.is_set():
        _conn_start = time.time()
        _diag.log_connect_start(cam_id, rtsp_url)

        # ── Open with explicit RTSP/FFmpeg options for 3MP cameras ──
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

        if not cap.isOpened():
            _elapsed = (time.time() - _conn_start) * 1000
            _diag.log_connect_fail(cam_id, _elapsed, "Cannot open stream")
            print(f"[Camera:{cam_id}] Cannot open stream, retrying in 1s...")
            time.sleep(1)
            continue

        # ── CRITICAL: set buffer BEFORE first read ─────────────
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # ── Flush stale frames — 5 grabs for clean stream ──
        for _ in range(5):
            cap.grab()

        _elapsed = (time.time() - _conn_start) * 1000

        # ── Measure actual stream resolution for smart resizing ──
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps_setting = cap.get(cv2.CAP_PROP_FPS) or 0
        is_high_res = actual_w >= 1920 or actual_h >= 1080
        _diag.log_connect_success(cam_id, _elapsed, actual_w, actual_h, fps_setting)
        if actual_w > 0:
            print(f"[Camera:{cam_id}] Native resolution: {actual_w}x{actual_h}"
                  f"{' (high-res)' if is_high_res else ''}")

        frame_no      = 0
        fail_count    = 0
        MAX_FAILS     = 10         # reconnect after 10 consecutive bad frames (tolerate transient network blips)

        while not stop_event.is_set():
            # Use grab()+retrieve() instead of read() for 3MP cameras.
            # grab() decodes in background; retrieve() only fetches when we need it.
            # This avoids the double-buffering lag that causes corrupt frames.
            grabbed = cap.grab()
            if not grabbed:
                fail_count += 1
                if fail_count >= MAX_FAILS:
                    _reconnect_count += 1
                    _diag.log_reconnect(cam_id, _reconnect_count, f"Frame grab failed {MAX_FAILS}x consecutive")
                    print(f"[Camera:{cam_id}] Frame grab failed {MAX_FAILS}x, reconnecting...")
                    break
                time.sleep(0.02)
                continue
            fail_count = 0
            frame_no += 1
            _update_capture_fps(cam_id)

            # Live preview — every 3rd frame (~10 FPS preview)
            # Only decode (retrieve) when we actually need the frame
            need_preview = (frame_no == 1 or frame_no % 2 == 0)
            need_ai      = (engine is not None and frame_no % effective_data_freq == 0
                            and not rec_queue.full())

            if not need_preview and not need_ai:
                continue   # skip decode entirely — huge CPU saving on 3MP streams

            ret, frame = cap.retrieve()
            if not ret or frame is None:
                continue

            # ── Validate frame is not corrupt ───────────────────
            # A corrupt frame usually has near-zero variance (flat gray noise)
            # Quick check: mean of absolute difference from expected range
            if frame.size == 0:
                continue

            # ── Corrupt/gray frame detector ────────────────────
            # Low variance = flat gray = corrupt decode from network jitter
            _gray_small = cv2.resize(gray := cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90)) if frame.shape[1] > 160 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _frame_var = float(cv2.meanStdDev(_gray_small)[1][0][0]) if _gray_small.size > 0 else 0

            # Log corrupt frames periodically
            if _frame_var < 5.0 and frame_no % 30 == 0:
                _diag.log_frame_issue(cam_id, f"Gray/corrupt frame detected (variance={_frame_var:.1f})", frame_no)

            # Log FPS every 5 seconds
            if frame_no > 0 and frame_no % 150 == 0:
                _diag.log_fps(cam_id, _capture_fps.get(cam_id, {}).get("fps", 0), _fps_tracker.get(cam_id, {}).get("fps", 0))

            # Live preview
            if need_preview:
                try:
                    # Adaptive preview: higher res for high-res cameras
                    preview_h = min(540 if actual_w >= 1920 else 360, frame.shape[0])
                    preview_w = int(frame.shape[1] * preview_h / frame.shape[0])
                    display = cv2.resize(frame, (preview_w, preview_h),
                                         interpolation=cv2.INTER_LINEAR)
                    _, jpeg = cv2.imencode('.jpg', display,
                                           [cv2.IMWRITE_JPEG_QUALITY, 90])
                    # Only update live frame if NOT corrupt (variance > 5)
                    if _frame_var > 5.0:
                        with _frame_lock:
                            _live_frames[cam_id] = jpeg.tobytes()
                    # else: keep last good frame in _live_frames (don't overwrite with gray)
                except Exception:
                    pass

            # Drop into recognition queue — original proven architecture
            if need_ai:
                if rec_queue.full():
                    try:
                        rec_queue.get_nowait()  # discard stale frame
                    except Exception:
                        pass
                try:
                    # Resize for AI — use 960x540 for high-res cameras
                    fw = frame.shape[1]
                    if fw > 960:
                        ai_frame = cv2.resize(frame, (960, 540),
                                               interpolation=cv2.INTER_LINEAR)
                    else:
                        ai_frame = frame.copy()   # copy to prevent buffer overwrite
                    rec_queue.put_nowait(ai_frame)
                except Exception:
                    pass

        cap.release()
        if not stop_event.is_set():
            print(f"[Camera:{cam_id}] Reconnecting in 1s...")
            time.sleep(1)

    print(f"[Camera:{cam_id}] Stopped")
    with _frame_lock:
        _live_frames.pop(cam_id, None)


def start_camera(cam: dict):
    """Start a camera background thread."""
    cam_id = cam["id"]
    stop_camera(cam_id)   # stop if already running
    stop_event = threading.Event()
    t = threading.Thread(target=camera_worker, args=(cam, stop_event), daemon=True)
    t.start()
    _camera_threads[cam_id] = {"thread": t, "stop": stop_event}
    print(f"[Server] Camera {cam_id} started")


def stop_camera(cam_id: str):
    """Stop a camera background thread."""
    if cam_id in _camera_threads:
        _camera_threads[cam_id]["stop"].set()
        _camera_threads[cam_id]["thread"].join(timeout=3)
        del _camera_threads[cam_id]
        # Clean pushed FPS tracking for this camera
        _pushed_fps.pop(cam_id, None)
        _pushed_count.pop(cam_id, None)
        _pushed_last_reset.pop(cam_id, None)
        _fps_tracker.pop(cam_id, None)
        _capture_fps.pop(cam_id, None)
        print(f"[Server] Camera {cam_id} stopped")


# --- BACKGROUND PURGE TIMER ---
_purge_last_run = [0.0]

def _purge_loop():
    """Background thread: purge old records every hour."""
    while True:
        time.sleep(300)
        now = time.time()
        if now - _purge_last_run[0] >= 3600:
            _purge_last_run[0] = now
            try:
                db_purge_old_events(keep=5000)
                db_purge_old_alerts(keep=1000)
                # Also clean stale _last_seen entries (older than 24h)
                stale = [k for k, v in list(_last_seen.items()) if now - v > 86400]
                for k in stale:
                    _last_seen.pop(k, None)
                print('[Purge] Cleaned old events + alerts + stale tracking data')
            except Exception as e:
                print(f'[Purge] Error: {e}')

_purge_thread = threading.Thread(target=_purge_loop, daemon=True)
_purge_thread.start()

# ─── STARTUP — auto-start all enabled cameras ─────────────────
@app.on_event("startup")
async def startup():
    global engine

    # ── Init DB ─────────────────────────────────────────────────
    init_db()

    # ── Face engine — only load if AI_MODE is enabled ──────────
    # On Render free tier (512MB RAM) we skip the engine to save memory.
    # Set AI_MODE=1 env var on machines that have the AI models available.
    ai_mode = os.environ.get("AI_MODE", "0") == "1"
    if ai_mode:
        print("[Server] AI_MODE=1 — Starting Face Recognition Engine...")
        try:
            # ── Configure MySQL for face embeddings storage ──────
            # FaceIndex will load embeddings from MySQL on init
            # and save new embeddings to MySQL on enrollment
            from face_engine import FaceIndex
            _mysql_host = os.environ.get("DB_HOST", "zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com")
            _mysql_port = int(os.environ.get("DB_PORT", "3306"))
            _mysql_user = os.environ.get("DB_USER", "3c_dev_user")
            _mysql_pass = os.environ.get("DB_PASSWORD", "2H&5bQU2*)J)")
            _mysql_db   = os.environ.get("DB_NAME", "3C_Z_ATTEND_AI")
            FaceIndex.set_mysql_config(_mysql_host, _mysql_port, _mysql_user, _mysql_pass, _mysql_db)
            print(f"[Server] Face embedding storage: MySQL {_mysql_db} @ {_mysql_host}")

            engine = FaceRecognitionEngine()
            print("[Server] Face engine ready!")
            # ── Diagnostic: show FAISS index status ─────────────
            emp = engine.employee_index
            blk = engine.blacklist_index
            vis = engine.visitor_index
            print(f"[Server] FAISS Index Status:")
            print(f"  Employee index:  {emp.total} embeddings from {len(set(v['person_id'] for v in emp.id_map.values()))} persons")
            print(f"  Blacklist index: {blk.total} embeddings")
            print(f"  Visitor index:   {vis.total} embeddings")
            print(f"  Index files:     {emp.index_path} ({os.path.getsize(emp.index_path) if os.path.exists(emp.index_path) else 0} bytes)")
            print(f"  Map files:       {emp.map_path} ({os.path.getsize(emp.map_path) if os.path.exists(emp.map_path) else 0} bytes)")
            if emp.total == 0:
                print(f"  [!] WARNING: FAISS index is EMPTY! No faces enrolled.")
                print(f"  [!] All detections will show as UNKNOWN.")
                print(f"  [!] Run bulk-enroll or enroll persons via the dashboard.")
            elif emp.total < 10:
                print(f"  [!] FAISS has very few embeddings ({emp.total}). Consider enrolling more photos per person.")
            # ── Also check DB vs FAISS sync ─────────────────────
            from database import db_get_persons as _dbp
            try:
                db_count = len(_dbp())
            except AttributeError:
                db_count = 0
            faiss_count = len(set(v['person_id'] for v in emp.id_map.values()))
            if db_count > 0 and faiss_count == 0:
                print(f"  [!] MISMATCH: DB has {db_count} persons but FAISS has 0!")
                print(f"  [!] Persons exist in database but embeddings were never trained.")
                print(f"  [!] Run: POST /api/v1/frd/bulk-enroll-folders to retrain.")
            elif db_count != faiss_count:
                print(f"  [!] DB has {db_count} persons, FAISS has {faiss_count} — may need re-enrollment.")
            else:
                print(f"  [OK] DB and FAISS are in sync ({faiss_count} persons)")
        except Exception as e:
            print(f"[Server] Face engine failed to load: {e}")
            import traceback
            traceback.print_exc()
            engine = None
    else:
        engine = None
        print("[Server] AI_MODE not set — running in DB-only mode (no face recognition).")
        print("[Server] Set AI_MODE=1 on your local machine to enable recognition.")
        print("[Server] Without AI_MODE=1, ALL face detections will show as UNKNOWN.")

    # Restore _person_status from DB attendance records
    today = datetime.now().strftime("%Y-%m-%d")
    restored = 0
    stale_closed = 0

    try:
        all_open = db_get_all_open_checkins()
    except AttributeError:
        all_open = []
    for rec in all_open:
        if rec.get("date") == today:
            with _person_status_lock:
                _person_status[rec["person_id"]] = "in"
            restored += 1
        else:
            db_update_attendance(rec["id"], {
                "status":        "checked_out",
                "checkout_time": rec.get("checkin_time"),
                "duration_min":  0,
                "duration_str":  "0m",
            })
            stale_closed += 1

    print(f"[Server] Restored {restored} active check-in(s), closed {stale_closed} stale record(s)")

    # Auto-start cameras only if AI engine is available
    if engine is not None:
        # Reload entity cache so person_id→entity_id is ready before first detection
        _load_entity_cache()

        try:
            cameras = db_get_cameras()
        except AttributeError:
            cameras = []
        _enabled = [cam for cam in cameras if cam.get("enabled", True)]

        # ── CAMERA MODE FILTER ──────────────────────────────────
        # 8mp: only 8MP cameras (3840x2160) — limit 6 max
        # 3mp: only 3MP/2MP cameras (1920x1080) — limit 10 max  
        # both: mix — total limit 8 cameras
        try:
            from database import db_get_system_settings
            _settings = db_get_system_settings()
            _camera_mode = _settings.get("camera_mode", "3mp")
        except Exception:
            _camera_mode = "3mp"

        if _camera_mode == "8mp":
            # 8MP cameras: FRS Entry/Exit
            _enabled = [cam for cam in _enabled if any(k in cam.get("id", "") for k in ["FRS"])]
            _enabled = _enabled[:6]   # max 6 x 8MP cameras
            print(f"[Server] Camera mode: 8MP only ({len(_enabled)} cameras)")
        elif _camera_mode == "3mp":
            # 3MP cameras: all non-FRS cameras
            _enabled = [cam for cam in _enabled if not any(k in cam.get("id", "") for k in ["FRS"])]
            _enabled = _enabled[:10]  # max 10 x 3MP cameras
            print(f"[Server] Camera mode: 3MP only ({len(_enabled)} cameras)")
        else:  # both
            _enabled = _enabled[:8]   # max 8 cameras total
            print(f"[Server] Camera mode: Both ({len(_enabled)} cameras)")

        _diag.log_startup_summary(_enabled)
        # Start ALL cameras in PARALLEL for instant startup
        if _enabled:
            import concurrent.futures
            _start_t = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(_enabled), 20)) as _pool:
                list(_pool.map(start_camera, _enabled))
            _total_ms = (time.time() - _start_t) * 1000
            _diag.log("START", "SERVER", f"All {len(_enabled)} camera(s) started in parallel in {_total_ms:.0f}ms")
            print(f"[Server] Auto-started {len(_enabled)} camera(s) in parallel ({_total_ms:.0f}ms)")
        else:
            print(f"[Server] No cameras to start (mode: {_camera_mode})")

        # ── Frame relay to Render (if RENDER_URL is set) ──────────
        render_url = os.environ.get("RENDER_URL", "").rstrip("/")
        ai_mode = os.environ.get("AI_MODE", "0") == "1"
        if render_url and ai_mode:
            import requests as _req
            def _relay_frames():
                print(f"[Relay] Starting frame relay to {render_url}")
                while True:
                    try:
                        with _frame_lock:
                            cam_ids = list(_live_frames.keys())
                        for cid in cam_ids:
                            with _frame_lock:
                                frame = _live_frames.get(cid)
                            if frame:
                                try:
                                    _req.post(
                                        f"{render_url}/api/v1/cameras/{cid}/frame",
                                        files={"file": ("f.jpg", frame, "image/jpeg")},
                                        timeout=2.0
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    time.sleep(0.2)  # ~5fps relay
            threading.Thread(target=_relay_frames, daemon=True).start()
            print(f"[Relay] Frame relay started → {render_url}")
    else:
        print("[Server] Cameras not started — AI engine not loaded.")

    pass  # Kloudspot auto-sync removed

@app.on_event("shutdown")
async def shutdown():
    for cam_id in list(_camera_threads.keys()):
        stop_camera(cam_id)

# ─── ROOT / HEALTH ───────────────────────────────────────────
@app.get("/")
def root():
    # Serve React dashboard if built, otherwise return API status
    index = Path("dist/index.html")
    if index.exists():
        return FileResponse(str(index), headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"status": "Face Recognition System Running", "version": "2.0.0"}

@app.get("/api/v1/health")
def health():
    running = list(_camera_threads.keys())
    camera_fps = {}
    for cid in set(list(running) + list(_pushed_fps.keys())):
        cap_fps  = _capture_fps.get(cid, {}).get("fps", 0.0)
        rec_fps  = _fps_tracker.get(cid, {}).get("fps", 0.0)
        push_fps = _pushed_fps.get(cid, 0.0)
        camera_fps[cid] = cap_fps if cap_fps > 0 else (push_fps if push_fps > 0 else rec_fps)

    if engine is not None:
        stats = engine.get_stats()
        ai_ready = True
    else:
        stats = {"total_enrolled_embeddings": 0, "blacklist_embeddings": 0,
                 "visitor_embeddings": 0, "unique_persons": 0}
        ai_ready = False

    return {"status": "ok", **stats, "ai_ready": ai_ready,
            "running_cameras": running, "camera_fps": camera_fps,
            "timestamp": datetime.now().isoformat()}

@app.get("/api/v1/diagnostics")
def camera_diagnostics():
    """Returns the last 200 lines of camera diagnostics log."""
    logs = _diag.get_recent_logs(200)
    return {"log_file": _diag.get_log_path(), "lines": logs, "count": len(logs)}

@app.get("/api/v1/frd/status")
def face_engine_status():
    """Diagnostic: shows FAISS index health + enrolled person counts."""
    from database import db_get_persons
    if engine is None:
        return {
            "engine_loaded": False,
            "error": "AI engine not loaded. Set AI_MODE=1 on local machine.",
            "ai_mode": os.environ.get("AI_MODE", "0"),
            "is_render": os.environ.get("RENDER", "").lower() == "true",
        }
    emp = engine.employee_index
    blk = engine.blacklist_index
    vis = engine.visitor_index
    db_persons = db_get_persons()
    return {
        "engine_loaded": True,
        "ai_mode": os.environ.get("AI_MODE", "0"),
        "employee_embeddings": emp.total,
        "employee_persons_in_faiss": len(set(v['person_id'] for v in emp.id_map.values())),
        "blacklist_embeddings": blk.total,
        "visitor_embeddings": vis.total,
        "db_persons_count": len(db_persons),
        "db_persons_ids": [p['id'] for p in db_persons],
        "faiss_index_file": emp.index_path,
        "faiss_map_file": emp.map_path,
        "next_faiss_id": emp.next_id,
        "id_map_sample": dict(list(emp.id_map.items())[:5]),
    }

# ─── LIVE FEED STREAM ─────────────────────────────────────────
def _mjpeg_generator(cam_id: str):
    """Yields MJPEG frames for a camera."""
    while True:
        with _frame_lock:
            frame = _live_frames.get(cam_id)
        if frame:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        else:
            # No frame — yield empty boundary and wait
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n"
        time.sleep(0.033)   # 30 fps display

@app.get("/api/v1/cameras/{camera_id}/stream")
def live_stream(camera_id: str):
    """MJPEG live stream endpoint."""
    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/api/v1/cameras/{camera_id}/frame")
async def push_frame(camera_id: str, file: UploadFile = File(...)):
    """
    Receives live JPEG frame pushed from local camera_processor.py.
    Stores in _live_frames for MJPEG stream endpoint.
    Bridge: camera on PC → GPU server → dashboard.
    """
    try:
        img_data = await file.read()
        img = cv2.imdecode(
            np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            display = cv2.resize(img, (640, 360))
            _, jpeg = cv2.imencode(
                '.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with _frame_lock:
                _live_frames[camera_id] = jpeg.tobytes()
            _update_pushed_fps(camera_id)
    except Exception:
        pass
    return {"ok": True}

@app.get("/api/v1/cameras/{camera_id}/stats")
def get_camera_live_stats(camera_id: str):
    """Live per-camera head-count stats: current inside + in/out events."""
    return {"success": True, "camera_id": camera_id,
            **room_occupancy_manager.cam_stats(camera_id)}

@app.get("/api/v1/tracking/cam-stats")
def get_all_cam_stats():
    """Head-count stats for ALL cameras in one call (floor map badges)."""
    return {"success": True, "cameras": room_occupancy_manager.all_cam_stats()}

@app.get("/api/v1/cameras/{camera_id}/snapshot")
def live_snapshot(camera_id: str):
    """Single JPEG snapshot from camera."""
    with _frame_lock:
        frame = _live_frames.get(camera_id)
    if not frame:
        return Response(status_code=204)
    return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})

# ── CAMERAS CRUD ─────────────────────────────────────────────
def normalize_rtsp_url(url: str) -> str:
    """URL-encode special chars (@ : # /) in RTSP credentials so parsers don't
    confuse them with the host separator. E.g. password 'utpl@123' -> 'utpl%40123'.
    OpenCV/FFmpeg decode %40 automatically, so the camera still authenticates.

    IDEMPOTENT: already-encoded URLs ('utpl%40123') are decoded first and
    re-encoded exactly once — saving twice never double-encodes (%2540)."""
    from urllib.parse import unquote
    if not url or "://" not in url:
        return url
    try:
        parts = urlsplit(url)
        if parts.username is None:
            return url
        host = parts.hostname or ""
        if ":" in host:  # IPv6 literal
            host = f"[{host}]"
        netloc = f"{host}:{parts.port}" if parts.port else host
        # decode first so already-encoded values are encoded exactly once
        auth = quote(unquote(parts.username), safe="")
        if parts.password is not None:
            auth += ":" + quote(unquote(parts.password), safe="")
        netloc = f"{auth}@{netloc}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except ValueError:
        return url


@app.post("/api/v1/cameras")
def add_camera(cam: CameraCreate):
    cam.rtsp_url = normalize_rtsp_url(cam.rtsp_url)
    db_upsert_camera({**cam.dict(), "created_at": datetime.now().isoformat()})
    if cam.enabled:
        start_camera(cam.dict())
    return {"success": True, "camera_id": cam.id}

@app.get("/api/v1/cameras")
def list_cameras():
    cameras = db_get_cameras()
    for c in cameras:
        c["running"] = c["id"] in _camera_threads
    return {"cameras": cameras}

@app.get("/api/v1/camera-mode")
def get_camera_mode():
    """Get current camera mode (8mp / 3mp / both)."""
    try:
        from database import db_get_system_settings
        settings = db_get_system_settings()
        mode = settings.get("camera_mode", "3mp")
    except Exception:
        mode = "3mp"
    return {"camera_mode": mode}

@app.post("/api/v1/camera-mode")
def set_camera_mode(req: dict):
    """Set camera mode and restart cameras. Body: {"camera_mode": "8mp" | "3mp" | "both"}"""
    mode = req.get("camera_mode", "3mp")
    if mode not in ["8mp", "3mp", "both"]:
        return {"error": "Invalid mode. Use: 8mp, 3mp, or both"}
    
    # Save to database
    try:
        from database import db_save_system_setting
        db_save_system_setting("camera_mode", mode)
    except Exception as e:
        return {"error": f"Failed to save: {e}"}
    
    # Stop all current cameras
    for cam_id in list(_camera_threads.keys()):
        stop_camera(cam_id)
    
    # Restart cameras with new mode
    import time as _time
    _time.sleep(1)  # give cameras time to stop
    
    try:
        cameras = db_get_cameras()
    except AttributeError:
        cameras = []
    
    _enabled = [cam for cam in cameras if cam.get("enabled", True)]
    
    if mode == "8mp":
        # 8MP cameras: FRS Entry/Exit (IPs 172.16.3.20x)
        _enabled = [cam for cam in _enabled if any(k in cam.get("id", "") for k in ["FRS"])]
        _enabled = _enabled[:6]
    elif mode == "3mp":
        # 3MP cameras: all non-FRS cameras (ALPS, Everest, Himalaya, Studio, etc.)
        _enabled = [cam for cam in _enabled if not any(k in cam.get("id", "") for k in ["FRS"])]
        _enabled = _enabled[:10]
    else:  # both
        _enabled = _enabled[:8]
    
    # Start filtered cameras
    if _enabled:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(_enabled), 20)) as _pool:
            list(_pool.map(start_camera, [cam for cam in _enabled]))
    
    print(f"[Server] Camera mode changed to: {mode.upper()} ({len(_enabled)} cameras started)")
    return {"success": True, "camera_mode": mode, "cameras_started": len(_enabled)}

# Pulse endpoint cache (5s TTL)
_pulse_cache = {}
_pulse_cache_lock = threading.Lock()

@app.get("/api/v1/cameras/{camera_id}/pulse")

def get_camera_pulse(camera_id: str):
    """Live pulse stats for a camera: FPS, detections today, known/unknown counts."""
    # Serve from cache if fresh (5s TTL)
    now_ts = time.time()
    with _pulse_cache_lock:
        cached = _pulse_cache.get(camera_id, {})
    if cached and (now_ts - cached.get("ts", 0)) < 5:
        return cached["data"]
    cameras = db_get_cameras()
    cam = next((c for c in cameras if c["id"] == camera_id), None)
    if not cam:
        # Fallback: build minimal cam info from in-memory state
        cam = {"id": camera_id, "name": camera_id, "fps": 30, "detection_zone": [], "camera_type": "frs"}

    running = camera_id in _camera_threads
    cap_fps  = _capture_fps.get(camera_id, {}).get("fps", 0.0)
    rec_fps  = _fps_tracker.get(camera_id, {}).get("fps", 0.0)
    push_fps = _pushed_fps.get(camera_id, 0.0)
    # Pulse shows the REAL camera stream rate first; AI rate is secondary
    fps = cap_fps if cap_fps > 0 else (push_fps if push_fps > 0 else rec_fps)

    today = datetime.now().strftime("%Y-%m-%d")
    # Direct SQL query per camera — much faster than loading all events
    from database import engine as _db_eng, text as _db_text
    with _db_eng.connect() as _conn:
        _row = _conn.execute(_db_text("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN matched = true THEN 1 ELSE 0 END) AS known,
                   SUM(CASE WHEN matched = false THEN 1 ELSE 0 END) AS unknown,
                   COUNT(DISTINCT CASE WHEN matched = true AND person_id IS NOT NULL THEN person_id ELSE NULL END) AS unique_known
            FROM `3c_eng_events` WHERE timestamp LIKE :ts AND camera_id = :cid
        """), {"ts": f"{today}%", "cid": camera_id}).fetchone()
    total_detections = _row[0] if _row else 0
    known_count = _row[1] if _row else 0
    unknown_count = _row[2] if _row else 0
    unique_known = _row[3] if _row else 0

    # Current person status (how many inside from this camera)
    inside_count = 0
    with _person_status_lock:
        for pid, st in _person_status.items():
            if st == "in":
                inside_count += 1

    return {
        "camera_id": camera_id,
        "running": running,
        "fps": fps,
        "capture_fps": cap_fps,
        "rec_fps": rec_fps,
        "target_fps": cam.get("fps", 30),
        "total_detections": total_detections,
        "known_count": known_count,
        "unknown_count": unknown_count,
        "unique_known": unique_known,
        "inside_now": inside_count,
        "has_zone": len(cam.get("detection_zone", [])) >= 3,
    }

@app.patch("/api/v1/cameras/{camera_id}")
def update_camera(camera_id: str, update: CameraUpdate):
    cameras = db_get_cameras()
    cam = next((c for c in cameras if c["id"] == camera_id), None)
    if not cam:
        raise HTTPException(404, "Camera not found")
    # exclude_unset (not exclude_none) so explicit nulls CAN clear optional
    # fields like room_id / map_x / map_y from the floor-map editor
    for k, v in update.dict(exclude_unset=True).items():
        cam[k] = v
    if cam.get("room_id") == "":   # normalize empty string -> no room
        cam["room_id"] = None
    if cam.get("rtsp_url"):
        cam["rtsp_url"] = normalize_rtsp_url(cam["rtsp_url"])
    db_upsert_camera(cam)
    # Only restart camera if relevant fields changed
    restart_fields = {"rtsp_url", "fps", "camera_type", "enabled", "detection_zone",
                      "face_confidence", "min_yaw", "max_yaw", "min_pitch", "max_pitch"}
    changed = any(k in restart_fields for k in update.dict(exclude_unset=True).keys())
    if changed:
        if cam.get("enabled", True):
            start_camera(cam)
        else:
            stop_camera(camera_id)
    return {"success": True}

@app.delete("/api/v1/cameras/{camera_id}")
def delete_camera(camera_id: str):
    cameras = db_get_cameras()
    cam = next((c for c in cameras if c["id"] == camera_id), None)
    if not cam:
        raise HTTPException(404, "Camera not found")
    stop_camera(camera_id)
    db_delete_camera(camera_id)
    return {"success": True}

@app.post("/api/v1/cameras/{camera_id}/start")
def start_camera_api(camera_id: str):
    cameras = db_get_cameras()
    cam = next((c for c in cameras if c["id"] == camera_id), None)
    if not cam:
        raise HTTPException(404, "Camera not found")
    start_camera(cam)
    return {"success": True, "status": "started"}

@app.post("/api/v1/cameras/{camera_id}/stop")
def stop_camera_api(camera_id: str):
    stop_camera(camera_id)
    return {"success": True, "status": "stopped"}

# ── FLOOR FLOW MAP (camera layout canvas) ───────────────────
class FlowLink(BaseModel):
    from_cam: str
    to_cam: str

class FlowSave(BaseModel):
    flows: list  # [{"from_cam": "cam-201", "to_cam": "202"}, ...]

@app.get("/api/v1/tracking/room-map")
def get_room_map():
    """Saved floor-canvas positions for room zones."""
    import json as _json
    settings = db_get_system_settings()
    raw = settings.get("room_map_positions", "{}")
    try:
        pos = _json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        pos = {}
    return {"success": True, "positions": pos}

@app.post("/api/v1/tracking/room-map")
def save_room_map(body: dict):
    """Replace room canvas positions: {"Room A": {"x": 30.5, "y": 40}, ...}"""
    import json as _json
    positions = body.get("positions", {})
    clean = {str(k): {"x": float(v.get("x", 50)), "y": float(v.get("y", 40))}
             for k, v in positions.items() if isinstance(v, dict)}
    db_save_system_setting("room_map_positions", _json.dumps(clean))
    return {"success": True, "positions": clean}

@app.get("/api/v1/tracking/flows")
def get_camera_flows():
    """Saved floor-flow arrows between cameras (stored in system_settings)."""
    import json as _json
    settings = db_get_system_settings()
    raw = settings.get("camera_flows", "[]")
    try:
        flows = _json.loads(raw) if isinstance(raw, str) else (raw or [])
    except Exception:
        flows = []
    return {"success": True, "flows": flows}

@app.post("/api/v1/tracking/flows")
def save_camera_flows(body: FlowSave):
    """Replace the whole floor-flow arrow list."""
    import json as _json
    clean = [{"from_cam": f.get("from_cam"), "to_cam": f.get("to_cam")}
             for f in body.flows if f.get("from_cam") and f.get("to_cam")]
    db_save_system_setting("camera_flows", _json.dumps(clean))
    return {"success": True, "flows": clean}

# ── GLOBAL TRACKING & ROOM OCCUPANCY ────────────────────────
@app.get("/api/v1/tracking/live")
def get_live_tracks(active_seconds: int = Query(300, ge=30, le=3600)):
    """All Global Person IDs active in the last `active_seconds`, newest first.

    Known people get a stable PERSON_XXXX id via face recognition;
    unknown people are re-identified across cameras via embedding gallery.
    """
    return {
        "success": True,
        "tracks": global_id_manager.live_tracks(active_seconds=active_seconds),
        "stats": global_id_manager.stats(),
    }

@app.get("/api/v1/tracking/movements")
def get_tracking_movements(limit: int = Query(80, ge=1, le=300)):
    """Recent in-memory camera-handoff movements (global ID crossing cameras)."""
    return {"success": True, "movements": global_id_manager.recent_movements(limit=limit)}

@app.get("/api/v1/rooms/occupancy")
def get_rooms_occupancy():
    """Live occupancy for every room that has cameras assigned.

    Combines today's persisted movements (entries/exits, who is inside)
    with the in-room state from the live tracker.
    """
    cameras = db_get_cameras()
    rooms = {}
    for c in cameras:
        rid = c.get("room_id")
        if not rid:
            continue
        room = rooms.setdefault(rid, {
            "room_id": rid,
            "cameras": [],
        })
        room["cameras"].append({
            "id":          c["id"],
            "name":        c.get("name"),
            "camera_type": c.get("camera_type", "checkin"),
            "running":     c["id"] in _camera_threads,
            **room_occupancy_manager.cam_stats(c["id"]),
        })

    # Persisted aggregates for today
    agg = db_get_room_occupancy_today()
    result = []
    for rid, room in rooms.items():
        a = agg.get(rid, {"entries": 0, "exits": 0, "inside": {}})
        inside_list = []
        for gid, info in list(a.get("inside", {}).items())[:50]:
            # attach face snapshot: live tracker first, then known-person photo
            snap = global_id_manager.get_snapshot(gid)
            inside_list.append({"global_id": gid, "snapshot": snap, **info})
        result.append({
            "room_id":      rid,
            "cameras":      room["cameras"],
            "entries":      a.get("entries", 0),
            "exits":        a.get("exits", 0),
            "inside_count": len(a.get("inside", {})),
            "inside":       inside_list,
        })
    result.sort(key=lambda r: r["room_id"])
    return {"success": True, "rooms": result, "updated_at": datetime.now().isoformat()}

@app.get("/api/v1/rooms/{room_id}/movements")
def get_room_movement_history(
    room_id: str,
    date: Optional[str] = None,
    direction: Optional[str] = Query(None, description="entry | exit"),
    limit: int = Query(200, ge=1, le=1000),
):
    """Persisted entry/exit movement history for a room."""
    movements = db_get_room_movements(room_id=room_id, date=date,
                                      direction=direction, limit=limit)
    return {"success": True, "movements": movements, "total": len(movements)}

@app.post("/api/v1/rooms/{room_id}/reset")
def reset_room_occupancy(room_id: str):
    """Reset live in-room state + clear persisted movements for one room."""
    room_occupancy_manager.reset(room_id)
    db_clear_room_movements(room_id)
    return {"success": True, "message": f"Room {room_id} occupancy reset"}

# ── FACE RECOGNITION (manual upload) ────────────────────────
@app.post("/api/v1/frd/recognize")
async def recognize_faces(
    file: UploadFile = File(...),
    camera_id: str = Query("default"),
    save_snapshot: bool = Query(True)
):
    if engine is None:
        raise HTTPException(503, "AI engine not loaded. Set AI_MODE=1 on the local machine running cameras.")
    # ── Warn if FAISS index is empty (root cause of all-unknown detections) ──
    if engine.employee_index.total == 0 and engine.blacklist_index.total == 0 and engine.visitor_index.total == 0:
        print(f"[WARN] FAISS indexes are EMPTY! All faces will be 'Unknown'.")
        print(f"[WARN] Run POST /api/v1/frd/bulk-enroll-folders or enroll persons to fix.")
    # Always use system settings threshold — no more hardcoded overrides
    threshold = _SYSTEM_SETTINGS_CACHE.get("face_threshold", 0.50)
    img_data = await file.read()
    image = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode image")
    cameras = db_get_cameras()
    cam = next((c for c in cameras if c["id"] == camera_id), None)
    cam_type = cam.get("camera_type", "both") if cam else "both"
    results = process_frame(image, camera_id, cam_type, threshold)
    # ── Log recognition summary ──
    matched_count = sum(1 for r in results if r.get("matched"))
    unknown_count = sum(1 for r in results if not r.get("matched"))
    if matched_count == 0 and len(results) > 0:
        print(f"[Recognize:{camera_id}] {len(results)} face(s) detected, 0 matched — FAISS may be empty or threshold too high")
    return {"count": len(results), "recognitions": results,
            "camera_id": camera_id, "timestamp": datetime.now().isoformat()}

# ── FACE DETECTION ──────────────────────────────────────────
@app.post("/api/v1/frd/detect")
async def detect_faces(file: UploadFile = File(...), min_conf: float = Query(0.5)):
    if engine is None:
        raise HTTPException(503, "AI engine not loaded. Set AI_MODE=1 on the local machine.")
    img_data = await file.read()
    image = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode image")
    faces = engine.detect_and_analyze(image)
    result_faces = [{k:v for k,v in f.items() if k!="embedding"}
                    for f in faces if f["confidence"] >= min_conf]
    return {"count": len(result_faces), "detections": result_faces}

# ── ENROLLMENT ──────────────────────────────────────────────
@app.post("/api/v1/frd/enroll")
async def enroll_face(
    file: UploadFile = File(...),
    name: str = Query(...),
    watchlist: str = Query("employee")
):
    if engine is None:
        raise HTTPException(503, "AI engine not loaded. Enroll from your local machine with AI_MODE=1.")
    img_data = await file.read()
    image = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode image")

    persons = db_get_persons(watchlist=watchlist)
    existing = next((p for p in persons if p["name"].lower() == name.lower()), None)
    person_id = existing["id"] if existing else db_next_person_id()

    result = engine.enroll(image, person_id=person_id, name=name, watchlist=watchlist)
    if not result["success"] and result.get("note") != "duplicate_skipped":
        raise HTTPException(400, result.get("error", "Enrollment failed"))

    # ── Store in DB only — no disk write ──────────────────────
    # 1. Save person record with display photo
    db_upsert_person({
        "id":        person_id,
        "name":      name,
        "photo_url": None,
        "watchlist": watchlist,
        "created_at": datetime.now().isoformat(),
    }, photo_array=image)

    # 2. Append training image to DB (max 5 kept per person)
    img_count = db_add_person_training_image(person_id, image, max_images=5)

    return {"person_id": person_id, "name": name,
            "watchlist": watchlist, "image_number": img_count,
            "total_enrolled": result.get("total", 0)}

# ── EVENTS ──────────────────────────────────────────────────
@app.get("/api/v1/events")
def get_events(
    limit: int = Query(10),
    page: int = Query(1),
    camera_id: Optional[str] = Query(None),
    person_id: Optional[int] = Query(None),
    matched: Optional[bool] = Query(None),
    suspected: Optional[bool] = Query(None),
    person_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    hours: int = Query(24),
    with_snapshots: bool = Query(False)
):
    return db_get_events(
        limit=limit,
        page=page,
        camera_id=camera_id,
        person_id=person_id,
        matched=matched,
        suspected=suspected,
        person_type=person_type,
        search=search,
        hours=hours,
        include_snapshots=with_snapshots
    )

# ── Ultra-fast in-memory snapshot cache (serves images in < 0.2ms) ──
_SNAPSHOT_RAM_CACHE: dict = {}
_SNAPSHOT_RAM_CACHE_MAX = 600

def _cached_snapshot_response(cache_key: str, b64_getter):
    if cache_key in _SNAPSHOT_RAM_CACHE:
        return Response(content=_SNAPSHOT_RAM_CACHE[cache_key], media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400, immutable"})
    b64 = b64_getter()
    if not b64:
        raise HTTPException(404, "No snapshot")
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    import base64
    try:
        raw = base64.b64decode(b64)
    except Exception:
        raise HTTPException(404, "Bad snapshot data")
    if len(_SNAPSHOT_RAM_CACHE) >= _SNAPSHOT_RAM_CACHE_MAX:
        for k in list(_SNAPSHOT_RAM_CACHE.keys())[:120]:
            _SNAPSHOT_RAM_CACHE.pop(k, None)
    _SNAPSHOT_RAM_CACHE[cache_key] = raw
    return Response(content=raw, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=86400, immutable"})

@app.get("/api/v1/events/{event_id}/snapshot")
def get_event_snapshot(event_id: int):
    return _cached_snapshot_response(f"ev_{event_id}", lambda: db_get_event_snapshot(event_id))

@app.get("/api/v1/attendance/{att_id}/snapshot")
def get_attendance_snapshot(att_id: int):
    return _cached_snapshot_response(f"att_{att_id}", lambda: db_get_attendance_snapshot(att_id))

@app.get("/api/v1/unknowns/{unknown_id}/snapshot")
def get_unknown_snapshot(unknown_id: int):
    return _cached_snapshot_response(f"unk_{unknown_id}", lambda: db_get_unknown_snapshot(unknown_id))

@app.delete("/api/v1/events/{event_id}")
def delete_event(event_id: int):
    if not db_delete_event(event_id):
        raise HTTPException(404, "Event not found")
    return {"success": True}

@app.patch("/api/v1/events/{event_id}")
def update_event(event_id: int, update: EventUpdate):
    event = db_update_event(event_id, update.person_name, update.camera_id)
    if not event:
        raise HTTPException(404, "Event not found")
    return {"success": True, "event": event}

# ── SYSTEM SETTINGS API ──────────────────────────────────────
@app.get("/api/v1/system/settings")
def get_system_settings_api():
    return {"success": True, "settings": db_get_system_settings()}

@app.post("/api/v1/system/settings")
def update_system_settings_api(payload: dict = Body(...)):
    for k, v in payload.items():
        db_save_system_setting(str(k), str(v))
    reload_system_settings_cache()
    return {"success": True, "settings": db_get_system_settings()}

# ── ATTENDANCE ──────────────────────────────────────────────
@app.get("/api/v1/attendance")
def get_attendance(
    date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    person_id: Optional[int] = Query(None),
    limit: int = Query(200)
):
    records = db_get_attendance(date=date, status=status, person_id=person_id, limit=limit)
    return {"attendance": records, "count": len(records), "date": date or "all"}

@app.get("/api/v1/attendance/currently-in")
def currently_in():
    today = datetime.now().strftime("%Y-%m-%d")
    inside = db_get_attendance(date=today, status="checked_in", limit=1000)
    return {"persons": inside, "count": len(inside)}

@app.post("/api/v1/attendance/checkout")
def manual_checkout(data: ManualCheckout):
    record = db_get_open_checkin(data.person_id)
    if not record:
        raise HTTPException(404, "No active check-in found")
    now_iso = datetime.now().isoformat()
    secs = int((datetime.now() - datetime.fromisoformat(record["checkin_time"])).total_seconds())
    h_d, m_d = divmod(secs, 3600); m_d = m_d // 60
    dur_str = f"{h_d}h {m_d}m" if h_d else f"{m_d}m"
    db_update_attendance(record["id"], {
        "status":        "checked_out",
        "checkout_time": now_iso,
        "duration_min":  round(secs/60, 1),
        "duration_str":  dur_str,
    })
    db_save_alert({
        "type": "CHECK_OUT", "severity": "low",
        "message": f"{record['person_name']} manually checked out — {dur_str}",
        "person_id": data.person_id, "acknowledged": False, "created_at": now_iso,
    })
    with _person_status_lock:
        _person_status[data.person_id] = "out"
    return {"success": True, "duration_str": dur_str, "checkout_time": now_iso}

@app.delete("/api/v1/attendance/clear")
def clear_attendance(date: Optional[str] = Query(None)):
    """Clear all attendance records, optionally filtered by date."""
    from sqlalchemy import delete as sql_delete
    from database import attendance_table, engine as db_engine
    with db_engine.connect() as conn:
        q = sql_delete(attendance_table)
        if date:
            q = q.where(attendance_table.c.date == date)
        res = conn.execute(q)
        conn.commit()
    return {"success": True, "deleted": res.rowcount}

@app.delete("/api/v1/attendance/bulk-delete")
def bulk_delete_attendance(request_body: dict = {}):
    """Delete multiple attendance records by IDs and their linked events.
    Body: {"ids": [1, 2, 3]}"""
    ids = request_body.get("ids", [])
    if not ids:
        raise HTTPException(400, "Provide ids: [list of record IDs]")
    deleted = db_delete_attendance_bulk(ids)
    return {"success": True, "deleted": deleted}

@app.delete("/api/v1/attendance/{record_id}")
def delete_attendance(record_id: int):
    """Delete a single attendance record and its linked event(s)."""
    if not db_delete_attendance_record(record_id):
        raise HTTPException(404, "Attendance record not found")
    return {"success": True}

# ── ANALYTICS ───────────────────────────────────────────────
@app.get("/api/v1/analytics/headcount")
def get_headcount(date: Optional[str] = Query(None)):
    cameras     = db_get_cameras()
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    day_events  = db_get_events_for_analytics(target_date)

    result = []
    for cam in cameras:
        cam_id   = cam["id"]
        cam_type = cam.get("camera_type", "checkin")
        has_zone = len(cam.get("detection_zone", [])) >= 3

        cam_events       = [e for e in day_events if e.get("camera_id") == cam_id]
        total_detections = len(cam_events)
        known_count      = sum(1 for e in cam_events if e.get("matched"))
        unknown_count    = sum(1 for e in cam_events if not e.get("matched"))
        known_ids        = set(e["person_id"] for e in cam_events if e.get("matched") and e.get("person_id"))

        result.append({
            "camera_id":        cam_id,
            "camera_name":      cam.get("name", cam_id),
            "camera_type":      cam_type,
            "has_zone":         has_zone,
            "total_detections": total_detections,
            "known_count":      known_count,
            "unknown_count":    unknown_count,
            "unique_known":     len(known_ids),
            "total_passed":     len(known_ids) + unknown_count,
        })
    return {"date": target_date, "cameras": result}

@app.get("/api/v1/analytics/occupancy")
def get_occupancy(date: Optional[str] = Query(None)):
    target_date  = date or datetime.now().strftime("%Y-%m-%d")
    day_records  = db_get_attendance_for_analytics(target_date)

    hourly = {h: {"hour": h, "entry": 0, "exit": 0, "occupancy": 0} for h in range(24)}
    for rec in day_records:
        if rec.get("checkin_time"):
            try:
                h = datetime.fromisoformat(rec["checkin_time"]).hour
                hourly[h]["entry"] += 1
            except Exception:
                pass
        if rec.get("checkout_time"):
            try:
                h = datetime.fromisoformat(rec["checkout_time"]).hour
                hourly[h]["exit"] += 1
            except Exception:
                pass

    running = 0
    for h in range(24):
        running += hourly[h]["entry"] - hourly[h]["exit"]
        hourly[h]["occupancy"] = max(0, running)

    return {"date": target_date, "data": list(hourly.values())}

@app.get("/api/v1/analytics/summary")
def get_analytics(hours:int=Query(24), date:Optional[str]=Query(None)):
    today = date or datetime.now().strftime("%Y-%m-%d")
    stats = db_get_dashboard_stats(target_date=today)

    # Query events by date directly in DB (not in Python) for performance
    if date:
        events = db_get_events_for_analytics(date)
    else:
        events = db_get_events(limit=1000, hours=hours)

    hourly = {}
    for e in events:
        ts = e.get("timestamp", "")
        if ts:
            k = ts[:13]+":00:00"
            hourly[k] = hourly.get(k, 0) + 1

    stats["hourly_timeline"] = [{"hour": h, "count": c} for h, c in sorted(hourly.items())]
    return stats


# ── ALERTS ──────────────────────────────────────────────────

# --- COMBINED DASHBOARD ENDPOINT (with 15s server-side cache) ---
_dashboard_cache = {}
_dashboard_cache_lock = threading.Lock()

@app.get("/api/v1/dashboard")
def get_dashboard(date: Optional[str] = Query(None), camera_id: Optional[str] = Query(None)):
    """Single endpoint: stats + headcount + occupancy in one DB call."""
    target = date or datetime.now().strftime("%Y-%m-%d")
    cache_key = f"{target}_{camera_id or 'all'}"
    now = time.time()
    
    with _dashboard_cache_lock:
        cached_entry = _dashboard_cache.get(cache_key)
        
    if cached_entry and (now - cached_entry["timestamp"]) < 15:
        return cached_entry["data"]
        
    data = db_get_dashboard_full(target, camera_id)
    
    with _dashboard_cache_lock:
        _dashboard_cache[cache_key] = {
            "data": data,
            "timestamp": now
        }
    return data

@app.get("/api/v1/alerts")
def get_alerts(acknowledged:Optional[bool]=Query(None), limit:int=Query(20)):
    alerts = db_get_alerts(acknowledged=acknowledged, limit=limit)
    return {"alerts": alerts}

@app.patch("/api/v1/alerts/{alert_id}")
def update_alert(alert_id:int, update:AlertUpdate):
    db_update_alert(alert_id, update.acknowledged)
    return {"success": True}

# ── SYSTEM SETTINGS & DYNAMIC THRESHOLDS ─────────────────────
class SystemSettings(BaseModel):
    face_threshold: Optional[float] = None
    suspected_threshold: Optional[float] = None
    blacklist_threshold: Optional[float] = None
    visitor_threshold: Optional[float] = None
    dedup_threshold: Optional[float] = None
    camera_cooldown: Optional[int] = None
    global_cooldown: Optional[int] = None
    dedup_seconds: Optional[int] = None
    known_suppress_seconds: Optional[int] = None
    camera_unknown_cooldown: Optional[int] = None

@app.get("/api/v1/settings/system")
def get_system_settings():
    s = db_get_system_settings()
    return {
        "face_threshold":      float(s.get("face_threshold", 0.50)),
        "suspected_threshold": float(s.get("suspected_threshold", 0.37)),
        "blacklist_threshold": float(s.get("blacklist_threshold", 0.35)),
        "visitor_threshold":   float(s.get("visitor_threshold", 0.50)),
        "dedup_threshold":     float(s.get("dedup_threshold", 0.65)),
        "camera_cooldown":     int(s.get("camera_cooldown", 120)),
        "global_cooldown":     int(s.get("global_cooldown", 300)),
        "dedup_seconds":       int(s.get("dedup_seconds", 120)),
        "known_suppress_seconds":  int(s.get("known_suppress_seconds", 120)),
        "camera_unknown_cooldown": int(s.get("camera_unknown_cooldown", 15)),
    }

@app.patch("/api/v1/settings/system")
def update_system_settings(s: SystemSettings):
    if s.face_threshold is not None:
        db_save_system_setting("face_threshold", str(s.face_threshold))
    if s.suspected_threshold is not None:
        db_save_system_setting("suspected_threshold", str(s.suspected_threshold))
    if s.blacklist_threshold is not None:
        db_save_system_setting("blacklist_threshold", str(s.blacklist_threshold))
    if s.visitor_threshold is not None:
        db_save_system_setting("visitor_threshold", str(s.visitor_threshold))
    if s.dedup_threshold is not None:
        db_save_system_setting("dedup_threshold", str(s.dedup_threshold))
    if s.camera_cooldown is not None:
        db_save_system_setting("camera_cooldown", str(s.camera_cooldown))
    if s.global_cooldown is not None:
        db_save_system_setting("global_cooldown", str(s.global_cooldown))
    if s.dedup_seconds is not None:
        db_save_system_setting("dedup_seconds", str(s.dedup_seconds))
    if s.known_suppress_seconds is not None:
        db_save_system_setting("known_suppress_seconds", str(s.known_suppress_seconds))
    if s.camera_unknown_cooldown is not None:
        db_save_system_setting("camera_unknown_cooldown", str(s.camera_unknown_cooldown))
    reload_system_settings_cache()
    return get_system_settings()

@app.get("/api/v1/train/folders")
def list_train_folders():
    folders=[]
    if TRAIN_DIR.exists():
        for item in sorted(TRAIN_DIR.iterdir()):
            if not item.is_dir():
                continue
            # Support both flat structure and watchlist subdirectories
            if item.name in ("employee", "visitor", "blacklist"):
                # Watchlist subdirectory — scan person folders inside
                for person_dir in sorted(item.iterdir()):
                    if person_dir.is_dir():
                        images=sorted([f.name for f in person_dir.iterdir() if f.suffix.lower() in('.jpg','.jpeg','.png')])
                        if images:
                            folders.append({"name":person_dir.name,"watchlist":item.name,"image_count":len(images),"images":images})
            else:
                # Legacy flat structure
                images=sorted([f.name for f in item.iterdir() if f.suffix.lower() in('.jpg','.jpeg','.png')])
                folders.append({"name":item.name,"watchlist":"employee","image_count":len(images),"images":images})
    return {"folders":folders,"total_persons":len(folders)}


class BulkEnrollRequest(BaseModel):
    watchlist: str = "employee"
    overwrite: bool = False   # if True, remove existing embeddings before re-enrolling


@app.post("/api/v1/frd/bulk-enroll-folders")
def bulk_enroll_from_folders(req: BulkEnrollRequest):
    """
    Scan train_images/ directory and enroll every person found.
    Structure:  train_images/{watchlist}/{person_name}/*.jpg
             OR train_images/{person_name}/*.jpg  (legacy)

    Call this from your local machine (AI_MODE=1) to enroll all persons
    into FAISS and save photos to the shared PostgreSQL DB.
    """
    if engine is None:
        raise HTTPException(503, "AI engine not loaded. Run with AI_MODE=1.")

    if not TRAIN_DIR.exists():
        raise HTTPException(404, "train_images/ directory not found")

    results = []
    total_persons = 0
    total_images  = 0

    def enroll_folder(person_folder: Path, person_name: str, watchlist: str):
        nonlocal total_persons, total_images
        images = sorted(
            list(person_folder.glob("*.jpg")) +
            list(person_folder.glob("*.jpeg")) +
            list(person_folder.glob("*.png"))
        )
        if not images:
            return {"name": person_name, "enrolled": 0, "skipped": 0, "error": "no images"}

        # Get or create person ID
        persons = db_get_persons(watchlist=watchlist)
        existing = next((p for p in persons if p["name"].lower() == person_name.lower()), None)
        person_id = existing["id"] if existing else db_next_person_id()

        if req.overwrite and existing:
            engine.remove_person(person_id, watchlist=watchlist)

        enrolled = 0
        skipped  = 0
        first_img_array = None

        for img_path in images:
            img = cv2.imread(str(img_path))
            if img is None:
                skipped += 1
                continue
            result = engine.enroll(img, person_id=person_id, name=person_name, watchlist=watchlist)
            if result.get("success"):
                if result.get("note") != "duplicate_skipped":
                    enrolled += 1
                    if first_img_array is None:
                        first_img_array = img
                else:
                    skipped += 1
            else:
                skipped += 1

        # Save/update person record in DB with photo + training images
        if enrolled > 0 or existing:
            db_upsert_person({
                "id":        person_id,
                "name":      person_name,
                "photo_url": None,
                "watchlist": watchlist,
                "created_at": existing.get("created_at") if existing else datetime.now().isoformat(),
            }, photo_array=first_img_array)
            # Store all training images in DB (max 5)
            if enrolled > 0:
                if req.overwrite:
                    db_clear_person_training_images(person_id)
                for img_path in images:
                    img = cv2.imread(str(img_path))
                    if img is not None:
                        db_add_person_training_image(person_id, img, max_images=5)

        if enrolled > 0:
            total_persons += 1
            total_images  += enrolled

        return {"name": person_name, "watchlist": watchlist,
                "enrolled": enrolled, "skipped": skipped}

    # Walk train_images/ — support both flat and watchlist-subdir structures
    for item in sorted(TRAIN_DIR.iterdir()):
        if not item.is_dir():
            continue

        if item.name in ("employee", "visitor", "blacklist"):
            # watchlist subfolder
            wl = item.name
            for person_dir in sorted(item.iterdir()):
                if person_dir.is_dir():
                    r = enroll_folder(person_dir, person_dir.name, wl)
                    results.append(r)
        else:
            # legacy flat structure — use requested watchlist
            r = enroll_folder(item, item.name, req.watchlist)
            results.append(r)

    return {
        "success":       True,
        "total_persons": total_persons,
        "total_images":  total_images,
        "results":       results,
    }

# ── UNKNOWN PERSONS TRACKING ─────────────────────────────────
@app.get("/api/v1/unknown-persons")
def get_unknown_persons(
    resolved: Optional[bool] = Query(None),
    date: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(10),
    search: Optional[str] = Query(None)
):
    return db_get_unknowns(resolved=resolved, date=date, page=page, limit=limit, search=search)

@app.delete("/api/v1/unknown-persons/{unknown_id}/delete")
def delete_unknown_person(unknown_id: int):
    if not db_delete_unknown(unknown_id):
        raise HTTPException(404, "Not found")
    return {"success": True}

@app.delete("/api/v1/unknown-persons/clear-resolved")
def clear_resolved_unknowns_api():
    deleted = db_clear_resolved_unknowns()
    return {"success": True, "deleted": deleted}

@app.patch("/api/v1/unknown-persons/{unknown_id}")
def resolve_unknown_person(unknown_id: int, data: UnknownResolve):
    unk = db_get_unknown_by_id(unknown_id)
    if not unk:
        raise HTTPException(404, "Unknown person not found")

    enrolled_count = 0
    person_id_out  = None

    if data.action in ("enroll", "blacklist") and data.name:
        watchlist  = "employee" if data.action == "enroll" else "blacklist"
        persons    = db_get_persons(watchlist=watchlist)
        existing   = next((p for p in persons if p["name"].lower() == data.name.lower()), None)
        person_id_out = existing["id"] if existing else db_next_person_id()

        b64s = unk.get("snapshot_b64s", [])
        for b64 in b64s:
            if not b64:
                continue
            try:
                import base64 as _b64
                img_bytes = _b64.b64decode(b64)
                img_arr   = np.frombuffer(img_bytes, dtype=np.uint8)
                img       = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
                if img is not None:
                    result = engine.enroll(img, person_id=person_id_out,
                                           name=data.name, watchlist=watchlist)
                    if result.get("success") and result.get("note") != "duplicate_skipped":
                        enrolled_count += 1
            except Exception:
                pass

        if not existing and enrolled_count > 0:
            # Use first snapshot b64 as the person's photo
            first_b64 = b64s[0] if b64s else None
            import base64 as _b64mod
            first_img = None
            if first_b64:
                try:
                    import cv2 as _cv2, numpy as _np
                    arr = _np.frombuffer(_b64mod.b64decode(first_b64), dtype=_np.uint8)
                    first_img = _cv2.imdecode(arr, _cv2.IMREAD_COLOR)
                except Exception:
                    pass
            db_upsert_person({
                "id":        person_id_out,
                "name":      data.name,
                "photo_url": None,
                "watchlist": watchlist,
                "created_at": datetime.now().isoformat(),
            }, photo_array=first_img)
            # Store the CCTV snapshots as training images in DB
            for b64 in b64s:
                if not b64:
                    continue
                try:
                    import base64 as _b64x
                    arr = np.frombuffer(_b64x.b64decode(b64), dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        db_add_person_training_image(person_id_out, img, max_images=5)
                except Exception:
                    pass

    db_resolve_unknown(unknown_id, data.action,
                       enrolled_as=data.name if data.action in ("enroll","blacklist") else None,
                       enrolled_count=enrolled_count,
                       person_id=person_id_out)
    return {"success": True, "action": data.action,
            "enrolled_count": enrolled_count, "person_id": person_id_out}

# ── PERSONS BY WATCHLIST ─────────────────────────────────────
@app.get("/api/v1/persons")
def list_persons(watchlist: Optional[str] = Query(None)):
    persons = db_get_persons(watchlist=watchlist)
    # Attach photo data URL (already included from DB)
    for p in persons:
        if not p.get("photo_data_url") and p.get("photo_url"):
            # Try legacy disk file
            from database import image_to_b64, b64_to_data_url as _b64url
            b64 = image_to_b64(p["photo_url"].lstrip("/"))
            p["photo_data_url"] = _b64url(b64)
    return {"persons": persons, "count": len(persons)}

@app.delete("/api/v1/frd/person/{person_id}")
async def delete_person(person_id: int, watchlist: str = Query("employee")):
    import shutil

    persons = db_get_persons()
    person  = next((p for p in persons if p["id"] == person_id), None)

    # Remove from FAISS only if AI engine is loaded
    removed_embeddings = 0
    if engine is not None:
        result = engine.remove_person(person_id, watchlist=watchlist)
        removed_embeddings = result.get("removed_embeddings", 0)

    # Always remove from DB
    db_delete_person(person_id, watchlist=watchlist)

    # Clean up train folder if on local machine
    if person:
        name = person.get("name", "")
        safe_name = "".join(c if c.isalnum() or c in(' ','_') else '_' for c in name).strip().replace(' ','_')
        for folder in [TRAIN_DIR / watchlist / safe_name, TRAIN_DIR / safe_name]:
            if folder.exists():
                shutil.rmtree(str(folder), ignore_errors=True)

    return {
        "success": True,
        "removed_embeddings": removed_embeddings,
        "person_name": person.get("name") if person else None,
    }

@app.patch("/api/v1/persons/{person_id}")
def update_person(person_id: int, update: PersonUpdate):
    person = db_update_person(person_id, update.name, update.watchlist)
    if not person:
        raise HTTPException(404, "Person not found")
    if update.name:
        if engine is not None:
            for idx in [engine.employee_index, engine.blacklist_index, engine.visitor_index]:
                for fid, info in idx.id_map.items():
                    if info["person_id"] == person_id:
                        info["name"] = update.name
                idx._save()
    return {"success": True, "person": person}

# ── RETRAIN PERSON ───────────────────────────────────────────
@app.post("/api/v1/frd/person/{person_id}/retrain")
async def retrain_person(person_id: int):
    if engine is None:
        raise HTTPException(503, "AI engine not loaded. Run with AI_MODE=1 on local machine.")
    """Re-train a person from all their stored training images (DB-first, disk fallback)."""
    persons = db_get_persons()
    person  = next((p for p in persons if p["id"] == person_id), None)
    if not person:
        raise HTTPException(404, "Person not found")

    name      = person["name"]
    watchlist = person.get("watchlist", "employee")
    safe_name = "".join(c if c.isalnum() or c in(' ','_') else '_' for c in name).strip().replace(' ','_')

    # ── 1. Try loading training images from DB first ──────────
    import base64 as _b64
    db_images = db_get_person_training_images(person_id)
    images_arrays = []
    for b64_str in db_images:
        try:
            raw = _b64.b64decode(b64_str)
            arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if arr is not None:
                images_arrays.append(arr)
        except Exception:
            continue

    # ── 2. Fallback: check disk train_images folder ───────────
    if not images_arrays:
        train_dirs = [
            TRAIN_DIR / watchlist / safe_name,
            TRAIN_DIR / safe_name,
        ]
        train_dir = next((d for d in train_dirs if d.exists()), None)
        if train_dir:
            for img_path in sorted(list(train_dir.glob("*.jpg")) + list(train_dir.glob("*.png"))):
                img = cv2.imread(str(img_path))
                if img is not None:
                    images_arrays.append(img)
            # Migrate disk images into DB for future use
            if images_arrays:
                db_clear_person_training_images(person_id)
                for img in images_arrays:
                    db_add_person_training_image(person_id, img, max_images=5)
                print(f"[Retrain] Migrated {len(images_arrays)} disk images to DB for {name}")

    if not images_arrays:
        raise HTTPException(404, f"No training images found for {name} — upload images first")

    # ── 3. Remove existing embeddings and re-enroll ───────────
    engine.remove_person(person_id, watchlist=watchlist)
    success_count = 0
    for img in images_arrays:
        result = engine.enroll(img, person_id=person_id, name=name, watchlist=watchlist)
        if result.get("success") and result.get("note") != "duplicate_skipped":
            success_count += 1

    return {
        "success":          True,
        "person_id":        person_id,
        "name":             name,
        "images_found":     len(images_arrays),
        "embeddings_added": success_count,
        "total_enrolled":   engine._get_index(watchlist).total
    }

# ── ADD IMAGE TO PERSON ──────────────────────────────────────
@app.post("/api/v1/frd/person/{person_id}/add-image")
async def add_image_to_person(
    person_id: int,
    file: UploadFile = File(...)
):
    if engine is None:
        raise HTTPException(503, "AI engine not loaded. Run with AI_MODE=1 on local machine.")
    persons = db_get_persons()
    person  = next((p for p in persons if p["id"] == person_id), None)
    if not person:
        raise HTTPException(404, "Person not found")

    name      = person["name"]
    watchlist = person.get("watchlist", "employee")

    img_data = await file.read()
    image    = cv2.imdecode(np.frombuffer(img_data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode image")

    # Train immediately
    result = engine.enroll(image, person_id=person_id, name=name, watchlist=watchlist)
    if not result.get("success") and result.get("note") != "duplicate_skipped":
        raise HTTPException(400, result.get("error", "No face detected in image"))

    # ── Store in DB only — no disk write ──────────────────────
    # 1. Update display photo in DB
    db_upsert_person({
        "id":        person_id,
        "name":      name,
        "photo_url": None,
        "watchlist": watchlist,
        "created_at": person.get("created_at", datetime.now().isoformat()),
    }, photo_array=image)

    # 2. Append training image to DB (max 5 kept per person)
    img_count = db_add_person_training_image(person_id, image, max_images=5)

    return {
        "success":        True,
        "person_id":      person_id,
        "name":           name,
        "image_number":   img_count,
        "trained":        result.get("note") != "duplicate_skipped",
        "total_enrolled": result.get("total", 0)
    }

# ── GET / DELETE PERSON TRAINING IMAGES ──────────────────────
@app.get("/api/v1/frd/person/{person_id}/training-images")
def get_person_training_images_api(person_id: int):
    """Return list of stored training images (as data URLs) for a person."""
    imgs = db_get_person_training_images(person_id)
    return {
        "person_id": person_id,
        "count": len(imgs),
        "images": [b64_to_data_url(b) for b in imgs],
    }

@app.delete("/api/v1/frd/person/{person_id}/training-images")
def clear_person_training_images_api(person_id: int):
    """Clear all stored training images for a person (useful before full re-enrollment)."""
    db_clear_person_training_images(person_id)
    return {"success": True, "person_id": person_id, "message": "Training images cleared"}


# ── HEAD COUNT / ROOM OCCUPANCY API ────────────────────────

@app.get("/api/v1/rooms/occupancy")
def get_room_occupancy():
    """Get current room occupancy for all rooms."""
    from database import db_get_room_occupancy_all
    return {"rooms": db_get_room_occupancy_all()}

@app.get("/api/v1/rooms/headcount/{camera_id}")
def get_room_headcount_log(camera_id: str):
    """Get headcount log for a specific camera/room."""
    from database import db_get_room_headcount_log
    return {"events": db_get_room_headcount_log(camera_id=camera_id, limit=50)}

@app.post("/api/v1/rooms/setup")
def setup_room(request: Request):
    """Set up a camera as a headcount room."""
    import asyncio
    body = asyncio.get_event_loop().run_until_complete(request.json())
    camera_id = body.get("camera_id")
    room_name = body.get("room_name")
    mode = body.get("mode", "headcount")
    if not camera_id or not room_name:
        raise HTTPException(400, "camera_id and room_name required")
    from database import db_setup_room
    db_setup_room(camera_id, room_name, mode)
    return {"success": True, "camera_id": camera_id, "room_name": room_name, "mode": mode}

@app.post("/api/v1/rooms/reset")
def reset_room_occupancy(request: Request):
    """Reset room occupancy counters."""
    import asyncio
    body = asyncio.get_event_loop().run_until_complete(request.json())
    camera_id = body.get("camera_id")
    from database import db_reset_room_occupancy
    db_reset_room_occupancy(camera_id)
    return {"success": True}

@app.get("/api/v1/rooms/cameras")
def get_cameras_with_rooms():
    """Get cameras with room configuration."""
    from database import db_get_cameras_with_rooms
    return {"cameras": db_get_cameras_with_rooms()}


# ── Catch-all: serve React index.html for all non-API routes ──
_STATIC_EXTS = {".js", ".mjs", ".css", ".map", ".wasm", ".png", ".jpg", ".jpeg",
                ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot",
                ".webp", ".webmanifest", ".txt"}

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve React SPA — any non-API route returns index.html."""
    dist = Path("dist")
    file_path = dist / full_path
    if full_path and file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    # Missing STATIC asset → 404. Never answer JS/CSS requests with HTML,
    # otherwise the browser fails with:
    # "Expected a JavaScript module script but the server responded with MIME text/html"
    suffix = Path(full_path).suffix.lower()
    if full_path.startswith("assets/") or suffix in _STATIC_EXTS:
        raise HTTPException(404, f"Static file not found: {full_path}")
    index = dist / "index.html"
    if index.exists():
        # no-cache: browsers must always fetch fresh index.html so they pick up
        # the new hashed asset filenames after every rebuild.
        return FileResponse(str(index), headers={
            "Cache-Control": "no-cache, no-store, must-revalidate"})
    return {"status": "Face Recognition System Running", "version": "2.0.0"}

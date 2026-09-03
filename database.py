"""
database.py — MySQL database layer for FRS
Uses SQLAlchemy Core (no ORM) for simplicity.
Images stored as Base64 TEXT — no cloud storage needed.

Single database: MySQL (AWS RDS).
Set DATABASE_URL env var to your MySQL connection string.
Falls back to SQLite (local file) if DATABASE_URL is not set.
"""

import os
import base64
import time
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    create_engine, text, MetaData, Table, Column,
    Integer, String, Boolean, Float, Text, DateTime,
    insert, update, delete, select, and_, or_
)
from sqlalchemy.pool import QueuePool
from sqlalchemy.dialects.mysql import MEDIUMTEXT as _MySQLMediumText
# Use Text with MySQL variant so it works on both MySQL and SQLite fallback
LargeText = Text().with_variant(_MySQLMediumText(), 'mysql')

# ─── CONNECTION ───────────────────────────────────────────────
# Priority: DATABASE_URL env var → individual DB_* vars → MySQL defaults → None
_RAW_URL = os.environ.get("DATABASE_URL", "")

# Fallback: build DATABASE_URL from individual env vars
if not _RAW_URL:
    _db_host = os.environ.get("DB_HOST", "zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com")
    _db_port = os.environ.get("DB_PORT", "3306")
    _db_user = os.environ.get("DB_USER", "3c_dev_user")
    _db_pass = os.environ.get("DB_PASSWORD", "2H&5bQU2*)J)")
    _db_name = os.environ.get("DB_NAME", "3C_Z_ATTEND_AI")
    if _db_host and _db_user and _db_name:
        from urllib.parse import quote_plus
        _pass = quote_plus(_db_pass) if _db_pass else ""
        _RAW_URL = f"mysql+pymysql://{_db_user}:{_pass}@{_db_host}:{_db_port}/{_db_name}"
        print(f"[DB] Built DATABASE_URL from DB_* env vars: {_db_user}@{_db_host}:{_db_port}/{_db_name}")

DB_TYPE = "sqlite"
engine = None

class EngineProxy:
    def __init__(self, target_engine):
        self._target = target_engine

    def __getattr__(self, name):
        return getattr(self._target, name)

    def connect(self):
        global DB_TYPE, engine
        if DB_TYPE in ("mysql", "postgresql"):
            try:
                return self._target.connect()
            except Exception as e:
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in [
                    'max_user_connections', 'too many connections',
                    'connection limit', 'pool timeout', 'queuepool limit'
                ])
                if is_transient:
                    print(f"[DB] {DB_TYPE.upper()} connection limit hit: {e}. Retrying next request.")
                    raise  # let caller handle gracefully
                # MySQL unreachable — log error but DO NOT fall back to SQLite
                print(f"[DB] {DB_TYPE.upper()} unreachable: {e}")
                raise  # propagate error — no SQLite fallback
        else:
            return self._target.connect()

if _RAW_URL:
    # Detect URL type and normalize for SQLAlchemy
    if _RAW_URL.startswith("mysql://"):
        _RAW_URL = _RAW_URL.replace("mysql://", "mysql+pymysql://", 1)
    elif _RAW_URL.startswith("mysql+pymysql://"):
        pass  # already correct
    elif _RAW_URL.startswith("postgres://"):
        _RAW_URL = _RAW_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif _RAW_URL.startswith("postgresql://"):
        _RAW_URL = _RAW_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    elif not _RAW_URL.startswith("mysql+") and not _RAW_URL.startswith("postgresql+"):
        # Assume MySQL if not postgres
        _RAW_URL = "mysql+pymysql://" + _RAW_URL.split("://", 1)[-1]

    _is_mysql = "mysql" in _RAW_URL
    _is_postgres = "postgresql" in _RAW_URL

    try:
        # Create engine IMMEDIATELY — test connection in background thread
        # This prevents the server from hanging during import
        real_engine = create_engine(
            _RAW_URL,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
            pool_recycle=180,
            pool_timeout=8,
            connect_args={"connect_timeout": 5}
        )
        # Use the engine immediately — pool will reconnect on first use
        DB_TYPE = "mysql" if _is_mysql else "postgresql"
        engine = EngineProxy(real_engine)
        print(f"[DB] {DB_TYPE.upper()} engine created (connection will be verified on first use)")

        # Verify connection in background (non-blocking)
        def _verify_db():
            try:
                with real_engine.connect() as _test_conn:
                    _test_conn.execute(text("SELECT 1"))
                print(f"[DB] {DB_TYPE.upper()} connection verified OK")
            except Exception as e:
                print(f"[DB] {DB_TYPE.upper()} connection failed: {e}")
        import threading as _t
        _t.Thread(target=_verify_db, daemon=True).start()
    except Exception as e:
        err_str = str(e).lower()
        is_transient = any(k in err_str for k in [
            'max_user_connections', 'too many connections',
            'connection limit', 'pool timeout'
        ])
        if is_transient:
            # Connection limit hit during startup — still use MySQL, it will work later
            print(f"[DB] MySQL connection limit at startup: {e}")
            print(f"[DB] Proceeding with MySQL — will work once connections free up")
            real_engine = create_engine(
                _RAW_URL,
                pool_size=1,
                max_overflow=2,
                pool_pre_ping=True,
                pool_recycle=180,
                pool_timeout=10,
                connect_args={"connect_timeout": 10}
            )
            DB_TYPE = "mysql" if _is_mysql else "postgresql"
            engine = EngineProxy(real_engine)
        else:
            print(f"[DB] MySQL unreachable: {e}")
            print(f"[DB] Creating engine anyway — will auto-reconnect when MySQL is available")
            real_engine = create_engine(
                _RAW_URL,
                pool_size=1,
                max_overflow=2,
                pool_pre_ping=True,
                pool_recycle=180,
                pool_timeout=10,
                connect_args={"connect_timeout": 10}
            )
            DB_TYPE = "mysql" if _is_mysql else "postgresql"
            engine = EngineProxy(real_engine)

if not _RAW_URL:
    print(f"[DB] FATAL: No database connection configured.")
    print(f"[DB] Set DATABASE_URL in .env, or set DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME")
    print(f"[DB] Example: DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbname")

# ─── AUTO-CLEAN IDLE CONNECTIONS ──────────────────────────────
# Background thread that kills idle MySQL connections every 60s
# Prevents "max_user_connections" errors automatically
def _connection_cleaner():
    """Background thread: recycle idle MySQL connections every 60s.
    Prevents max_user_connections errors by closing stale pool connections
    and killing server-side idle sessions older than 5 minutes."""
    import time as _time
    while True:
        _time.sleep(60)
        try:
            if DB_TYPE == "mysql" and engine and hasattr(engine, '_target'):
                pool = engine._target.pool
                # 1. Clear any broken connections from the pool
                pool._invalidate_pool()
                # 2. Kill server-side idle connections (>5 min sleep)
                try:
                    with engine._target.connect() as conn:
                        rows = conn.execute(text(
                            "SELECT id FROM information_schema.processlist "
                            "WHERE user = :usr AND command = 'Sleep' AND time > 300"
                        ), {"usr": DATABASE_USER}).fetchall()
                        for row in rows:
                            try:
                                conn.execute(text(f"KILL {row[0]}"))
                            except Exception:
                                pass
                        if rows:
                            print(f"[DB] Cleaned {len(rows)} idle connections")
                except Exception:
                    pass
        except Exception:
            pass

try:
    _cleaner_thread = threading.Thread(target=_connection_cleaner, daemon=True)
    _cleaner_thread.start()
except Exception:
    pass

DATABASE_USER = os.environ.get("DB_USER", "3c_dev_user")
metadata = MetaData()

# ─── SCHEMA ───────────────────────────────────────────────────

persons_table = Table("3c_eng_persons", metadata,
    Column("id",                    Integer,  primary_key=True),
    Column("name",                  String(200), nullable=False),
    Column("watchlist",             String(50),  default="employee"),
    Column("company",               String(200), nullable=True),        # company/organisation
    Column("photo_b64",             LargeText,  nullable=True),
    Column("photo_url",             String(500), nullable=True),
    Column("train_folder",          String(500), nullable=True),
    Column("training_images_b64",   LargeText,  nullable=True),  # JSON array of base64 training images
    Column("created_at",            String(50),  nullable=True),
)

cameras_table = Table("3c_eng_cameras", metadata,
    Column("id",             String(100), primary_key=True),
    Column("name",           String(200), nullable=False),
    Column("rtsp_url",       String(500), nullable=False),
    Column("camera_type",    String(50),  default="checkin"),
    Column("fps",            Integer,     default=30),
    Column("enabled",        Boolean,     default=True),
    Column("notes",          Text,        default=""),
    Column("face_confidence",Float,       default=0.4),
    Column("detection_range",Float,       default=6.5),
    Column("min_yaw",        Integer,     default=-45),
    Column("max_yaw",        Integer,     default=45),
    Column("min_pitch",      Integer,     default=-25),
    Column("max_pitch",      Integer,     default=25),
    Column("detection_zone", Text,        default="[]"),   # JSON string
    Column("send_image",     Boolean,     default=True),
    Column("data_frequency", Integer,     default=2),
    Column("room_id",        String(100), nullable=True),  # room for occupancy counting
    Column("map_x",          Float,       nullable=True),  # floor-flow canvas position (%)
    Column("map_y",          Float,       nullable=True),  # floor-flow canvas position (%)
    Column("entry_zone",     Text,        nullable=True),  # legacy: entry rect
    Column("exit_zone",      Text,        nullable=True),  # legacy: exit rect
    Column("count_line",     Text,        nullable=True),  # head-count line [x1,y1,x2,y2] % of frame
    Column("count_inside_pt",Text,        nullable=True),  # [x,y] % of frame
    Column("created_at",     String(50),  nullable=True),
    Column("room_name",      String(100), nullable=True),
    Column("head_count_mode",String(50),  nullable=True),
    Column("head_count_line",Text,        nullable=True),
)

events_table = Table("3c_eng_events", metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("event_id",      String(100), nullable=True),
    Column("camera_id",     String(100), nullable=True),
    Column("person_id",     Integer,     nullable=True),
    Column("entity_id",     String(200), nullable=True),
    Column("person_name",   String(200), default="Unknown"),
    Column("person_type",   String(50),  default="unknown"),
    Column("confidence",    Float,       default=0.0),
    Column("matched",       Boolean,     default=False),
    Column("suspected",     Boolean,     default=False),
    Column("bbox",          Text,        default="[]"),         # JSON [x1,y1,x2,y2]
    Column("timestamp",     String(50),  nullable=True),
    Column("snapshot_b64",  LargeText,  nullable=True),        # base64 jpeg face crop
    Column("snapshot_path", String(500), nullable=True),        # legacy compat
    Column("synced_at",     String(50),  nullable=True),
    Column("tracker_id",    String(200), nullable=True),  # dedup: hash of camera+person+bbox+timestamp
)

attendance_table = Table("3c_eng_attendance", metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("person_id",     Integer,     nullable=True),
    Column("person_name",   String(200), nullable=True),
    Column("camera_id",     String(100), nullable=True),
    Column("checkin_time",  String(50),  nullable=True),
    Column("checkout_time", String(50),  nullable=True),
    Column("duration_min",  Float,       nullable=True),
    Column("duration_str",  String(50),  nullable=True),
    Column("status",        String(50),  default="checked_in"),
    Column("snapshot_b64",  LargeText,  nullable=True),
    Column("snapshot_path", String(500), nullable=True),
    Column("date",          String(20),  nullable=True),
)

alerts_table = Table("3c_eng_alerts", metadata,
    Column("id",           Integer, primary_key=True, autoincrement=True),
    Column("type",         String(100), nullable=True),
    Column("severity",     String(50),  default="low"),
    Column("message",      Text,        nullable=True),
    Column("person_id",    Integer,     nullable=True),
    Column("acknowledged", Boolean,     default=False),
    Column("created_at",   String(50),  nullable=True),
)

unknown_persons_table = Table("3c_eng_unknown_persons", metadata,
    Column("id",             Integer, primary_key=True, autoincrement=True),
    Column("tracking_id",    String(200), nullable=True),
    Column("first_seen",     String(50),  nullable=True),
    Column("last_seen",      String(50),  nullable=True),
    Column("camera_ids",     Text,        default="[]"),     # JSON list
    Column("snapshots",      Text,        default="[]"),     # JSON list of paths (legacy)
    Column("snapshot_b64s",  LargeText,  default="[]"),     # JSON list of base64 strings
    Column("event_count",    Integer,     default=1),
    Column("embedding",      Text,        nullable=True),    # JSON float list
    Column("resolved",       Boolean,     default=False),
    Column("resolved_action",String(50),  nullable=True),
    Column("resolved_at",    String(50),  nullable=True),
    Column("enrolled_as",    String(200), nullable=True),
    Column("enrolled_count", Integer,     nullable=True),
    Column("person_id",      Integer,     nullable=True),
    Column("date",           String(20),  nullable=True),
)

settings_table = Table("3c_eng_settings", metadata,
    Column("key_name",   String(100), primary_key=True),
    Column("value", Text,        nullable=True),
)

# KloudSpot ↔ Our DB person entity ID mapping table
# Stores the KloudSpot entityId for each of our enrolled persons
persons_ks_map_table = Table("3c_eng_ks_map", metadata,
    Column("person_id",    Integer,     primary_key=True),
    Column("ks_entity_id", String(200), nullable=True),   # KloudSpot entityId
    Column("ks_name",      String(200), nullable=True),   # Person name in KloudSpot DB
    Column("mapped_at",    String(50),  nullable=True),
    Column("mapped_by",    String(50),  default="manual"),  # "manual" | "auto_name" | "auto_entity"
)

# ── 3C ENGINE MAPPING TABLE ──────────────────────────────────
# KS-centric bridge: entity_id → our person_id
# Populated from today's KloudSpot events matched by full name to our 102 persons.
# Both this table AND persons_ks_map coexist — they are complementary:
#   persons_ks_map      : our DB centric  (person_id  → entity_id)
#   three_c_eng_mapping : KS centric      (entity_id  → person_id)
three_c_eng_mapping_table = Table("3c_eng_entity_mapping", metadata,
    Column("entity_id",   String(200), primary_key=True),   # KloudSpot entityId
    Column("full_name",   String(200), nullable=True),       # name as it appears in KloudSpot
    Column("first_name",  String(100), nullable=True),
    Column("last_name",   String(100), nullable=True),
    Column("person_id",   Integer,     nullable=True),       # our DB persons.id (NULL if unmatched)
    Column("our_name",    String(200), nullable=True),       # our DB persons.name for quick display
    Column("company",     String(200), nullable=True),       # our DB persons.company
    Column("match_method",String(50),  default="auto_name"), # "auto_name" | "manual" | "unmatched"
    Column("mapped_at",   String(50),  nullable=True),       # when this row was created/updated
)

kloudspot_events_table = Table("3c_eng_kloudspot_events", metadata,
    Column("id",            String(100), primary_key=True),
    Column("tracking_id",   String(100), nullable=True),
    Column("entity_id",     String(100), nullable=True),
    Column("first_name",    String(100), nullable=True),
    Column("last_name",     String(100), nullable=True),
    Column("full_name",     String(200), nullable=True),
    Column("location_id",   String(100), nullable=True),
    Column("location_type", String(50),  nullable=True),
    Column("direction",     String(20),  default="in"),
    Column("object_type",   String(50),  default="human"),
    Column("timestamp_ms",  Float,       nullable=True),
    Column("timestamp_iso", String(50),  nullable=True),
    Column("date",          String(20),  nullable=True),
    Column("image_b64",     LargeText,  nullable=True),
    Column("raw_json",      Text,        nullable=True),
    Column("created_at",    String(50),  nullable=True),
)

# ── GLOBAL TRACKING / ROOM OCCUPANCY ─────────────────────────
# One row per entry/exit movement of a Global Person ID in a room.
room_movements_table = Table("3c_eng_room_movements", metadata,
    Column("id",           Integer,     primary_key=True, autoincrement=True),
    Column("room_id",      String(100), nullable=False),
    Column("global_id",    String(100), nullable=True),    # PERSON_0001 / UNK_20260826_003
    Column("person_name",  String(200), default="Unknown"),
    Column("person_type",  String(50),  default="unknown"),
    Column("camera_id",    String(100), nullable=True),
    Column("direction",    String(20),  default="entry"),   # entry | exit
    Column("confidence",   Float,       default=0.0),
    Column("snapshot_b64", LargeText,  nullable=True),
    Column("timestamp",    String(50),  nullable=True),
    Column("date",         String(20),  nullable=True),
)

# ── HEAD COUNT TABLES ──────────────────────────────────────
room_headcount_table = Table("3c_eng_room_headcount", metadata,
    Column("id",           Integer,     primary_key=True, autoincrement=True),
    Column("camera_id",    String(100), nullable=False),
    Column("room_name",    String(100), nullable=False),
    Column("person_name",  String(200), nullable=True),
    Column("person_id",    Integer,     nullable=True),
    Column("direction",    String(10),  nullable=False),     # IN or OUT
    Column("confidence",   Float,       default=0),
    Column("timestamp",    String(50),  nullable=True),
)

room_occupancy_table = Table("3c_eng_room_occupancy", metadata,
    Column("camera_id",     String(100), primary_key=True),
    Column("room_name",     String(100), nullable=False),
    Column("current_count", Integer,     default=0),
    Column("total_in",      Integer,     default=0),
    Column("total_out",     Integer,     default=0),
    Column("last_updated",  String(50),  nullable=True),
)

# ─── INIT ─────────────────────────────────────────────────────
def init_db():
    """Create all tables if they don't exist. Also runs safe migrations."""
    try:
        metadata.create_all(engine)
    except Exception as e:
        print(f"[DB] init_db: table creation deferred (MySQL unreachable: {str(e)[:80]})")
        return
    # ── Safe migrations: add columns that may not exist in older DBs ──
    with engine.connect() as conn:
        # Safe migrations — silently ignore if column/index already exists
        _safe_alter = [
            "ALTER TABLE `3c_eng_events` ADD COLUMN suspected BOOLEAN DEFAULT FALSE",
            "ALTER TABLE `3c_eng_persons` ADD COLUMN company VARCHAR(200)",
            "ALTER TABLE `3c_eng_persons` ADD COLUMN training_images_b64 TEXT",
            "ALTER TABLE `3c_eng_cameras` ADD COLUMN room_id VARCHAR(100)",
            "ALTER TABLE `3c_eng_cameras` ADD COLUMN map_x FLOAT",
            "ALTER TABLE `3c_eng_cameras` ADD COLUMN map_y FLOAT",
            "ALTER TABLE `3c_eng_cameras` ADD COLUMN entry_zone TEXT",
            "ALTER TABLE `3c_eng_cameras` ADD COLUMN exit_zone TEXT",
            "ALTER TABLE `3c_eng_cameras` ADD COLUMN count_line TEXT",
            "ALTER TABLE `3c_eng_cameras` ADD COLUMN count_inside_pt TEXT",
            "ALTER TABLE `3c_eng_events` ADD COLUMN tracker_id VARCHAR(200)",
        ]
        for _sql in _safe_alter:
            try:
                conn.execute(text(_sql))
                conn.commit()
            except Exception:
                pass  # Column already exists

        # Performance indexes
        for _idx in [
            "CREATE INDEX idx_events_ts ON `3c_eng_events` (timestamp)",
            "CREATE INDEX idx_events_cam ON `3c_eng_events` (camera_id)",
            "CREATE INDEX idx_events_matched ON `3c_eng_events` (matched)",
            "CREATE INDEX idx_events_person ON `3c_eng_events` (person_id)",
            "CREATE UNIQUE INDEX idx_events_tracker ON `3c_eng_events` (tracker_id)",
            "CREATE INDEX idx_unk_last_seen ON `3c_eng_unknown_persons` (last_seen)",
            "CREATE INDEX idx_att_date ON `3c_eng_attendance` (date)"
        ]:
            try:
                conn.execute(text(_idx))
                conn.commit()
            except Exception:
                pass  # Index already exists
    print("[DB] Tables ready")

# ─── PERSON ↔ KLOUDSPOT ENTITY ID MAPPING ────────────────────

def db_get_person_ks_map() -> List[dict]:
    """Get all persons with their KloudSpot entity ID mapping."""
    with engine.connect() as conn:
        # Join persons with ks_map to get full picture
        persons = _rows_to_list(conn.execute(
            select(persons_table).order_by(persons_table.c.id)
        ))
        ks_rows = {r["person_id"]: r for r in _rows_to_list(
            conn.execute(select(persons_ks_map_table))
        )}
    result = []
    for p in persons:
        km = ks_rows.get(p["id"], {})
        result.append({
            "person_id":    p["id"],
            "person_name":  p["name"],
            "company":      p.get("company"),
            "watchlist":    p.get("watchlist", "employee"),
            "ks_entity_id": km.get("ks_entity_id"),
            "ks_name":      km.get("ks_name"),
            "mapped_at":    km.get("mapped_at"),
            "mapped_by":    km.get("mapped_by"),
            "photo_data_url": b64_to_data_url(p.get("photo_b64")),
        })
    return result

def db_set_person_ks_entity(person_id: int, ks_entity_id: Optional[str],
                             ks_name: Optional[str] = None,
                             mapped_by: str = "manual") -> bool:
    """Set or update the KloudSpot entity ID for a person."""
    now = datetime.now().isoformat()
    with engine.connect() as conn:
        existing = conn.execute(
            select(persons_ks_map_table)
            .where(persons_ks_map_table.c.person_id == person_id)
        ).fetchone()
        if existing:
            conn.execute(
                update(persons_ks_map_table)
                .where(persons_ks_map_table.c.person_id == person_id)
                .values(ks_entity_id=ks_entity_id, ks_name=ks_name,
                        mapped_at=now, mapped_by=mapped_by)
            )
        else:
            conn.execute(insert(persons_ks_map_table).values(
                person_id=person_id, ks_entity_id=ks_entity_id,
                ks_name=ks_name, mapped_at=now, mapped_by=mapped_by
            ))
        conn.commit()
    return True

def db_bulk_set_ks_entity_map(mappings: List[dict]) -> int:
    """
    Bulk upsert KloudSpot entity ID mappings.
    Each item: {"person_id": int, "ks_entity_id": str, "ks_name": str, "mapped_by": str}
    """
    now = datetime.now().isoformat()
    count = 0
    with engine.connect() as conn:
        for m in mappings:
            pid = m.get("person_id")
            if not pid:
                continue
            existing = conn.execute(
                select(persons_ks_map_table)
                .where(persons_ks_map_table.c.person_id == pid)
            ).fetchone()
            if existing:
                conn.execute(
                    update(persons_ks_map_table)
                    .where(persons_ks_map_table.c.person_id == pid)
                    .values(
                        ks_entity_id=m.get("ks_entity_id"),
                        ks_name=m.get("ks_name"),
                        mapped_at=now,
                        mapped_by=m.get("mapped_by", "auto_name")
                    )
                )
            else:
                conn.execute(insert(persons_ks_map_table).values(
                    person_id=pid,
                    ks_entity_id=m.get("ks_entity_id"),
                    ks_name=m.get("ks_name"),
                    mapped_at=now,
                    mapped_by=m.get("mapped_by", "auto_name")
                ))
            count += 1
        conn.commit()
    return count

def db_get_ks_entity_map_by_entity_id(ks_entity_id: str) -> Optional[dict]:
    """Look up our person for a given KloudSpot entity ID."""
    with engine.connect() as conn:
        row = conn.execute(
            select(persons_ks_map_table)
            .where(persons_ks_map_table.c.ks_entity_id == ks_entity_id)
        ).fetchone()
    return _row_to_dict(row) if row else None

# ─── 3C ENGINE MAPPING HELPERS ───────────────────────────────

def db_get_three_c_mapping(person_id: Optional[int] = None) -> List[dict]:
    """Get all rows from three_c_eng_mapping, optionally filtered by person_id."""
    with engine.connect() as conn:
        q = select(three_c_eng_mapping_table).order_by(
            three_c_eng_mapping_table.c.full_name)
        if person_id is not None:
            q = q.where(three_c_eng_mapping_table.c.person_id == person_id)
        return _rows_to_list(conn.execute(q))

def db_get_three_c_by_entity_id(entity_id: str) -> Optional[dict]:
    """Look up our person_id for a KloudSpot entityId."""
    with engine.connect() as conn:
        row = conn.execute(
            select(three_c_eng_mapping_table)
            .where(three_c_eng_mapping_table.c.entity_id == entity_id)
        ).fetchone()
    return _row_to_dict(row) if row else None

_PERSON_ENTITY_CACHE: dict = {}

def db_get_entity_id_for_person(person_id: Optional[int]) -> Optional[str]:
    """Look up entity_id for a given person_id with in-memory caching."""
    if not person_id:
        return None
    if person_id in _PERSON_ENTITY_CACHE:
        return _PERSON_ENTITY_CACHE[person_id]
    try:
        with engine.connect() as conn:
            # Check three_c_eng_mapping first
            row = conn.execute(
                select(three_c_eng_mapping_table.c.entity_id)
                .where(three_c_eng_mapping_table.c.person_id == person_id)
                .limit(1)
            ).fetchone()
            if row and row[0]:
                _PERSON_ENTITY_CACHE[person_id] = str(row[0])
                return _PERSON_ENTITY_CACHE[person_id]

            # Fallback to persons_ks_map
            row2 = conn.execute(
                select(persons_ks_map_table.c.ks_entity_id)
                .where(persons_ks_map_table.c.person_id == person_id)
                .limit(1)
            ).fetchone()
            if row2 and row2[0]:
                _PERSON_ENTITY_CACHE[person_id] = str(row2[0])
                return _PERSON_ENTITY_CACHE[person_id]
    except Exception:
        pass
    return None

def db_upsert_three_c_mapping(rows: List[dict]) -> int:
    """
    Upsert rows into three_c_eng_mapping.
    Each row: {entity_id, full_name, first_name, last_name,
               person_id, our_name, company, match_method}
    Uses upsert (delete + insert) so re-running is safe and idempotent.
    Does NOT touch any other table.
    """
    if not rows:
        return 0
    now = datetime.now().isoformat()
    count = 0
    with engine.connect() as conn:
        for r in rows:
            eid = r.get("entity_id")
            if not eid:
                continue
            # Delete existing row for this entity_id (safe — no cascade)
            conn.execute(
                delete(three_c_eng_mapping_table)
                .where(three_c_eng_mapping_table.c.entity_id == eid)
            )
            conn.execute(insert(three_c_eng_mapping_table).values(
                entity_id    = eid,
                full_name    = r.get("full_name"),
                first_name   = r.get("first_name"),
                last_name    = r.get("last_name"),
                person_id    = r.get("person_id"),
                our_name     = r.get("our_name"),
                company      = r.get("company"),
                match_method = r.get("match_method", "auto_name"),
                mapped_at    = now,
            ))
            count += 1
        conn.commit()
    return count

def db_build_three_c_mapping_from_today() -> dict:
    """
    Reads today's KloudSpot events, extracts unique entity IDs with names,
    matches them against our enrolled persons by name (fuzzy),
    and upserts the result into three_c_eng_mapping.
    Returns a summary dict.
    """
    from kloudspot_service import normalize_name, is_name_match
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Get unique entities from today's KS events
    with engine.connect() as conn:
        ks_rows = _rows_to_list(conn.execute(
            select(
                kloudspot_events_table.c.entity_id,
                kloudspot_events_table.c.full_name,
                kloudspot_events_table.c.first_name,
                kloudspot_events_table.c.last_name,
            ).where(kloudspot_events_table.c.date == today)
        ))

    # Deduplicate by entity_id
    ks_entities = {}
    for r in ks_rows:
        eid = r.get("entity_id") or ""
        if eid and eid not in ks_entities:
            ks_entities[eid] = {
                "entity_id":  eid,
                "full_name":  r.get("full_name") or "",
                "first_name": r.get("first_name") or "",
                "last_name":  r.get("last_name") or "",
            }

    # 2. Get our enrolled persons
    our_persons = db_get_persons()
    our_norm = {normalize_name(p["name"]): p for p in our_persons if normalize_name(p["name"])}

    # 3. Match by name
    rows_to_upsert = []
    used_pids = set()
    matched = 0
    unmatched = 0

    for eid, info in ks_entities.items():
        ks_name = info["full_name"]
        best_p = None

        # Exact normalised match first
        n = normalize_name(ks_name)
        if n and n in our_norm and our_norm[n]["id"] not in used_pids:
            best_p = our_norm[n]

        # Fuzzy token match
        if not best_p:
            for p in our_persons:
                if p["id"] not in used_pids and is_name_match(ks_name, p["name"]):
                    best_p = p
                    break

        if best_p:
            used_pids.add(best_p["id"])
            matched += 1
            rows_to_upsert.append({
                "entity_id":    eid,
                "full_name":    ks_name,
                "first_name":   info["first_name"],
                "last_name":    info["last_name"],
                "person_id":    best_p["id"],
                "our_name":     best_p["name"],
                "company":      best_p.get("company"),
                "match_method": "auto_name",
            })
        else:
            unmatched += 1
            rows_to_upsert.append({
                "entity_id":    eid,
                "full_name":    ks_name,
                "first_name":   info["first_name"],
                "last_name":    info["last_name"],
                "person_id":    None,
                "our_name":     None,
                "company":      None,
                "match_method": "unmatched",
            })

    saved = db_upsert_three_c_mapping(rows_to_upsert)
    return {
        "date":       today,
        "ks_entities": len(ks_entities),
        "matched":    matched,
        "unmatched":  unmatched,
        "saved":      saved,
    }

# ─── IMAGE HELPERS ────────────────────────────────────────────

def image_to_b64(image_path: str) -> Optional[str]:
    """Read a file from disk and return base64 string."""
    try:
        p = Path(image_path)
        if not p.exists():
            p = Path("snapshots") / p.name
        if p.exists():
            return base64.b64encode(p.read_bytes()).decode("utf-8")
    except Exception:
        pass
    return None

def numpy_to_b64(img_array) -> Optional[str]:
    """Convert a numpy BGR image to base64 JPEG string."""
    if img_array is None:
        return None
    try:
        import cv2
        _, buf = cv2.imencode(".jpg", img_array, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(buf.tobytes()).decode("utf-8")
    except ImportError:
        return None
    except Exception:
        return None

def b64_to_data_url(b64: Optional[str]) -> Optional[str]:
    """Convert raw base64 to a data URL for frontend use."""
    if b64:
        return f"data:image/jpeg;base64,{b64}"
    return None

# ─── GENERIC HELPERS ──────────────────────────────────────────

def _row_to_dict(row) -> dict:
    """Convert a SQLAlchemy Row to plain dict."""
    if row is None:
        return {}
    return dict(row._mapping)

def _rows_to_list(rows) -> list:
    return [dict(r._mapping) for r in rows]

def _json_field(value: Any, default="[]") -> Any:
    """Parse a JSON text field back to Python object."""
    if value is None:
        return json.loads(default)
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return json.loads(default)

def _to_json(value) -> str:
    return json.dumps(value, default=str)

# ─── PERSONS ──────────────────────────────────────────────────

def db_get_persons(watchlist: Optional[str] = None) -> List[dict]:
    with engine.connect() as conn:
        q = select(persons_table)
        if watchlist:
            q = q.where(persons_table.c.watchlist == watchlist)
        q = q.order_by(persons_table.c.created_at.desc())
        rows = _rows_to_list(conn.execute(q))
    for r in rows:
        r["photo_data_url"] = b64_to_data_url(r.get("photo_b64"))
    return rows

def db_upsert_person(person: dict, photo_array=None) -> dict:
    """Insert or update a person. photo_array = numpy image for b64 storage."""
    b64 = numpy_to_b64(photo_array) if photo_array is not None else None
    now = datetime.now().isoformat()
    with engine.connect() as conn:
        existing = conn.execute(
            select(persons_table).where(persons_table.c.id == person["id"])
        ).fetchone()

        data = {
            "name":         person.get("name"),
            "watchlist":    person.get("watchlist", "employee"),
            "company":      person.get("company"),
            "photo_url":    person.get("photo_url"),
            "train_folder": person.get("train_folder"),
        }
        if b64:
            data["photo_b64"] = b64

        if existing:
            conn.execute(
                update(persons_table)
                .where(persons_table.c.id == person["id"])
                .values(**data)
            )
        else:
            data["id"]         = person["id"]
            data["created_at"] = person.get("created_at", now)
            conn.execute(insert(persons_table).values(**data))
        conn.commit()
    return {"success": True, "person_id": person["id"]}

def db_delete_person(person_id: int, watchlist: str = "employee") -> bool:
    with engine.connect() as conn:
        conn.execute(
            delete(persons_table).where(
                and_(persons_table.c.id == person_id,
                     persons_table.c.watchlist == watchlist)
            )
        )
        conn.commit()
    return True

def db_update_person(person_id: int, name: Optional[str], watchlist: Optional[str]) -> Optional[dict]:
    with engine.connect() as conn:
        data = {}
        if name:
            data["name"] = name
        if watchlist:
            data["watchlist"] = watchlist
        if data:
            conn.execute(
                update(persons_table).where(persons_table.c.id == person_id).values(**data)
            )
            conn.commit()
        row = conn.execute(
            select(persons_table).where(persons_table.c.id == person_id)
        ).fetchone()
    return _row_to_dict(row) if row else None

def db_next_person_id() -> int:
    with engine.connect() as conn:
        row = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM `3c_eng_persons`")).fetchone()
    return int(row[0])

def db_get_person_training_images(person_id: int) -> List[str]:
    """Return list of base64 training image strings for a person."""
    with engine.connect() as conn:
        row = conn.execute(
            select(persons_table.c.training_images_b64)
            .where(persons_table.c.id == person_id)
        ).fetchone()
    if not row or not row[0]:
        return []
    try:
        imgs = json.loads(row[0])
        return imgs if isinstance(imgs, list) else []
    except Exception:
        return []

def db_add_person_training_image(person_id: int, img_array, max_images: int = 5) -> int:
    """
    Append a training image (numpy array) to the person's DB record.
    Enforces max_images limit — oldest is dropped if exceeded.
    Returns new count of stored training images.
    """
    b64 = numpy_to_b64(img_array)
    if not b64:
        return 0
    existing = db_get_person_training_images(person_id)
    existing.append(b64)
    if len(existing) > max_images:
        existing = existing[-max_images:]  # keep newest N
    with engine.connect() as conn:
        conn.execute(
            update(persons_table)
            .where(persons_table.c.id == person_id)
            .values(training_images_b64=json.dumps(existing))
        )
        conn.commit()
    return len(existing)

def db_clear_person_training_images(person_id: int):
    """Remove all stored training images for a person (e.g. before re-enroll)."""
    with engine.connect() as conn:
        conn.execute(
            update(persons_table)
            .where(persons_table.c.id == person_id)
            .values(training_images_b64=json.dumps([]))
        )
        conn.commit()

# ─── CAMERAS ──────────────────────────────────────────────────

def db_get_cameras() -> List[dict]:
    with engine.connect() as conn:
        rows = _rows_to_list(conn.execute(select(cameras_table)))
    for r in rows:
        r["detection_zone"] = _json_field(r.get("detection_zone"), "[]")
        r["entry_zone"] = _json_field(r.get("entry_zone"), None) if r.get("entry_zone") else None
        r["exit_zone"] = _json_field(r.get("exit_zone"), None) if r.get("exit_zone") else None
        r["count_line"] = _json_field(r.get("count_line"), None) if r.get("count_line") else None
        r["count_inside_pt"] = _json_field(r.get("count_inside_pt"), None) if r.get("count_inside_pt") else None
    return rows

def db_upsert_camera(cam: dict):
    now = datetime.now().isoformat()
    zone = _to_json(cam.get("detection_zone", []))
    with engine.connect() as conn:
        existing = conn.execute(
            select(cameras_table).where(cameras_table.c.id == cam["id"])
        ).fetchone()

        data = {
            "name":             cam.get("name"),
            "rtsp_url":         cam.get("rtsp_url"),
            "camera_type":      cam.get("camera_type", "checkin"),
            "fps":              cam.get("fps", 30),
            "enabled":          cam.get("enabled", True),
            "notes":            cam.get("notes", ""),
            "face_confidence":  cam.get("face_confidence", 0.6),
            "detection_range":  cam.get("detection_range", 6.5),
            "min_yaw":          cam.get("min_yaw", -35),
            "max_yaw":          cam.get("max_yaw", 35),
            "min_pitch":        cam.get("min_pitch", -15),
            "max_pitch":        cam.get("max_pitch", 15),
            "detection_zone":   zone,
            "send_image":       cam.get("send_image", True),
            "data_frequency":   cam.get("data_frequency", 2),
            "room_id":          cam.get("room_id"),
            "map_x":            cam.get("map_x"),
            "map_y":            cam.get("map_y"),
            "entry_zone":       _to_json(cam.get("entry_zone")) if cam.get("entry_zone") else None,
            "exit_zone":        _to_json(cam.get("exit_zone")) if cam.get("exit_zone") else None,
            "count_line":       _to_json(cam.get("count_line")) if cam.get("count_line") else None,
            "count_inside_pt":  _to_json(cam.get("count_inside_pt")) if cam.get("count_inside_pt") else None,
        }
        if existing:
            conn.execute(
                update(cameras_table).where(cameras_table.c.id == cam["id"]).values(**data)
            )
        else:
            data["id"]         = cam["id"]
            data["created_at"] = cam.get("created_at", now)
            conn.execute(insert(cameras_table).values(**data))
        conn.commit()

def db_delete_camera(camera_id: str):
    with engine.connect() as conn:
        conn.execute(delete(cameras_table).where(cameras_table.c.id == camera_id))
        conn.commit()

# ─── LAZY SNAPSHOT FETCHERS (for /snapshot endpoints) ────────

def db_get_event_snapshot(event_id: int) -> Optional[str]:
    with engine.connect() as conn:
        row = conn.execute(select(events_table.c.snapshot_b64).where(events_table.c.id == event_id)).fetchone()
    return row[0] if row else None

def db_get_attendance_snapshot(att_id: int) -> Optional[str]:
    with engine.connect() as conn:
        row = conn.execute(select(attendance_table.c.snapshot_b64).where(attendance_table.c.id == att_id)).fetchone()
    return row[0] if row else None

def db_get_unknown_snapshot(unknown_id: int) -> Optional[str]:
    """First stored snapshot of an unknown person."""
    with engine.connect() as conn:
        row = conn.execute(select(unknown_persons_table.c.snapshot_b64s).where(unknown_persons_table.c.id == unknown_id)).fetchone()
    if not row or not row[0]:
        return None
    b64s = _json_field(row[0], "[]")
    return b64s[0] if b64s else None

# ─── ROOM MOVEMENTS (Global tracking / occupancy) ────────────

def db_save_room_movement(m: dict, snapshot_array=None) -> int:
    """Save one room entry/exit movement. snapshot_array = numpy face crop."""
    b64 = numpy_to_b64(snapshot_array) if snapshot_array is not None else m.get("snapshot_b64")
    with engine.connect() as conn:
        result = conn.execute(insert(room_movements_table).values(
            room_id      = m.get("room_id"),
            global_id    = m.get("global_id"),
            person_name  = m.get("person_name", "Unknown"),
            person_type  = m.get("person_type", "unknown"),
            camera_id    = m.get("camera_id"),
            direction    = m.get("direction", "entry"),
            confidence   = m.get("confidence", 0.0),
            snapshot_b64 = b64,
            timestamp    = m.get("timestamp") or datetime.now().isoformat(),
            date         = datetime.now().strftime("%Y-%m-%d"),
        ))
        conn.commit()
        return int(result.inserted_primary_key[0])

def db_get_room_movements(room_id: Optional[str] = None,
                          date: Optional[str] = None,
                          direction: Optional[str] = None,
                          limit: int = 200) -> List[dict]:
    with engine.connect() as conn:
        q = select(room_movements_table)
        if room_id:
            q = q.where(room_movements_table.c.room_id == room_id)
        if date:
            q = q.where(room_movements_table.c.date == date)
        if direction:
            q = q.where(room_movements_table.c.direction == direction)
        q = q.order_by(room_movements_table.c.id.desc()).limit(limit)
        rows = _rows_to_list(conn.execute(q))
    for r in rows:
        r["snapshot_data_url"] = b64_to_data_url(r.get("snapshot_b64"))
    return rows

def db_get_room_occupancy_today(room_id: Optional[str] = None) -> dict:
    """Aggregate today's movements: entries/exits per room + who is inside.

    Inside = global IDs whose latest movement today is 'entry'.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    with engine.connect() as conn:
        q = select(room_movements_table).where(room_movements_table.c.date == today)
        if room_id:
            q = q.where(room_movements_table.c.room_id == room_id)
        q = q.order_by(room_movements_table.c.id.asc())
        rows = _rows_to_list(conn.execute(q))

    rooms = {}
    for r in rows:
        rid = r["room_id"]
        room = rooms.setdefault(rid, {
            "entries": 0, "exits": 0,
            "inside": {},   # global_id -> {name, since}
        })
        gid = r.get("global_id") or f"evt_{r['id']}"
        if r["direction"] == "entry":
            room["entries"] += 1
            room["inside"][gid] = {
                "person_name": r.get("person_name", "Unknown"),
                "person_type": r.get("person_type", "unknown"),
                "since":       r.get("timestamp"),
            }
        else:
            room["exits"] += 1
            room["inside"].pop(gid, None)
    return rooms

def db_clear_room_movements(room_id: Optional[str] = None):
    with engine.connect() as conn:
        q = delete(room_movements_table)
        if room_id:
            q = q.where(room_movements_table.c.room_id == room_id)
        conn.execute(q)
        conn.commit()

# ─── HEAD COUNT FUNCTIONS ──────────────────────────────────

def db_record_headcount(camera_id: str, room_name: str, direction: str,
                        person_name: str = None, person_id: int = None,
                        confidence: float = 0) -> None:
    """Record a head count entry/exit for a room."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with engine.connect() as conn:
        # Insert headcount record
        conn.execute(insert(room_headcount_table).values(
            camera_id=camera_id, room_name=room_name,
            person_name=person_name or "Unknown", person_id=person_id,
            direction=direction, confidence=confidence, timestamp=now_str
        ))
        # Update occupancy
        occ = conn.execute(
            select(room_occupancy_table).where(room_occupancy_table.c.camera_id == camera_id)
        ).fetchone()
        if occ:
            cur_count = occ[2]  # current_count
            total_in = occ[3]
            total_out = occ[4]
            new_count = max(0, cur_count + (1 if direction == "IN" else -1))
            new_in = total_in + (1 if direction == "IN" else 0)
            new_out = total_out + (1 if direction == "OUT" else 0)
            conn.execute(
                room_occupancy_table.update()
                .where(room_occupancy_table.c.camera_id == camera_id)
                .values(current_count=new_count, total_in=new_in, total_out=new_out,
                        last_updated=now_str)
            )
        else:
            conn.execute(insert(room_occupancy_table).values(
                camera_id=camera_id, room_name=room_name,
                current_count=max(0, 1 if direction == "IN" else 0),
                total_in=1 if direction == "IN" else 0,
                total_out=1 if direction == "OUT" else 0,
                last_updated=now_str
            ))
        conn.commit()


def db_get_room_occupancy_all() -> List[dict]:
    """Get current occupancy for all rooms."""
    with engine.connect() as conn:
        rows = conn.execute(select(room_occupancy_table)).fetchall()
    result = []
    for r in rows:
        result.append({
            "camera_id": r[0], "room_name": r[1],
            "current_count": r[2], "total_in": r[3],
            "total_out": r[4], "last_updated": r[5],
        })
    return result


def db_get_room_headcount_log(camera_id: str = None, room_name: str = None,
                               limit: int = 50) -> List[dict]:
    """Get recent headcount log entries."""
    with engine.connect() as conn:
        q = select(room_headcount_table)
        if camera_id:
            q = q.where(room_headcount_table.c.camera_id == camera_id)
        if room_name:
            q = q.where(room_headcount_table.c.room_name == room_name)
        q = q.order_by(room_headcount_table.c.id.desc()).limit(limit)
        rows = _rows_to_list(conn.execute(q))
    return rows


def db_reset_room_occupancy(camera_id: str = None):
    """Reset room occupancy counters."""
    with engine.connect() as conn:
        if camera_id:
            conn.execute(
                room_occupancy_table.update()
                .where(room_occupancy_table.c.camera_id == camera_id)
                .values(current_count=0, total_in=0, total_out=0)
            )
        else:
            conn.execute(room_occupancy_table.update().values(
                current_count=0, total_in=0, total_out=0
            ))
        conn.commit()


def db_setup_room(camera_id: str, room_name: str, mode: str = "headcount"):
    """Set up a camera as a headcount room."""
    with engine.connect() as conn:
        # Update camera
        conn.execute(
            cameras_table.update()
            .where(cameras_table.c.id == camera_id)
            .values(room_name=room_name, head_count_mode=mode)
        )
        # Create occupancy entry if not exists
        occ = conn.execute(
            select(room_occupancy_table).where(room_occupancy_table.c.camera_id == camera_id)
        ).fetchone()
        if not occ:
            conn.execute(insert(room_occupancy_table).values(
                camera_id=camera_id, room_name=room_name,
                current_count=0, total_in=0, total_out=0,
                last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
        conn.commit()


def db_get_cameras_with_rooms() -> List[dict]:
    """Get cameras with their room configuration."""
    with engine.connect() as conn:
        rows = _rows_to_list(conn.execute(select(cameras_table)))
    result = []
    for r in rows:
        result.append({
            "id": r["id"], "name": r["name"], "camera_type": r["camera_type"],
            "enabled": r["enabled"], "room_name": r.get("room_name"),
            "head_count_mode": r.get("head_count_mode") or "off",
        })
    return result


# ─── EVENTS ───────────────────────────────────────────────────

import hashlib as _hashlib

def _make_tracker_id(camera_id, person_id, bbox, timestamp):
    """Generate a deterministic tracker_id from detection characteristics.
    Same face in same frame → same tracker_id → dedup catches it."""
    # Round bbox to nearest 5px to group overlapping detections
    _bbox_str = ""
    if bbox and len(bbox) >= 4:
        _bbox_str = ":".join(str(round(b / 5) * 5) for b in bbox[:4])
    # Truncate timestamp to the second
    _ts_sec = timestamp[:19] if timestamp else ""
    _raw = f"{camera_id}:{person_id}:{_bbox_str}:{_ts_sec}"
    return _hashlib.md5(_raw.encode()).hexdigest()[:32]


def db_save_event(event: dict, snapshot_array=None, shared_conn=None) -> int:
    """Save a recognition event. Dedup by tracker_id — deterministic, no race conditions."""
    b64 = numpy_to_b64(snapshot_array) if snapshot_array is not None else None
    _ts = event.get("timestamp", datetime.now().isoformat())

    # Generate tracker_id: same face + same frame = same tracker_id
    _tid = _make_tracker_id(
        event.get("camera_id", ""),
        event.get("person_id"),
        event.get("bbox", []),
        _ts
    )

    def _do_save(conn):
        # DEDUP: if tracker_id already exists, skip entirely
        _exists = conn.execute(
            select(events_table.c.id).where(
                events_table.c.tracker_id == _tid
            ).limit(1)
        ).fetchone()
        if _exists:
            return _exists[0]  # DUPLICATE — skip

        result = conn.execute(insert(events_table).values(
            event_id     = event.get("event_id"),
            camera_id    = event.get("camera_id"),
            person_id    = event.get("person_id"),
            entity_id    = event.get("entity_id"),
            person_name  = event.get("person_name", "Unknown"),
            person_type  = event.get("person_type", "unknown"),
            confidence   = event.get("confidence", 0.0),
            matched      = event.get("matched", False),
            suspected    = event.get("suspected", False),
            bbox         = _to_json(event.get("bbox", [])),
            snapshot_b64 = b64,
            snapshot_path= event.get("snapshot_path"),
            timestamp    = _ts,
            tracker_id   = _tid,
        ))
        conn.commit()
        return result.inserted_primary_key[0]

    try:
        if shared_conn:
            return _do_save(shared_conn)
        else:
            with engine.connect() as conn:
                return _do_save(conn)
    except Exception as _err:
        err_str = str(_err).lower()
        # Unique constraint violation = duplicate tracker_id
        if 'duplicate' in err_str or 'unique' in err_str:
            print(f"[Dedup] tracker_id collision blocked: {_tid[:12]}...")
            return -1
        print(f"[DB] Event save failed: {str(_err)[:80]}")
        return -1

    # ── Mirror to external 3C MySQL DB (fire-and-forget, never raises) ──
    try:
        from external_events_db import mirror_event
        eid = event.get("entity_id") or db_get_entity_id_for_person(event.get("person_id"))
        ev_copy = dict(event)
        ev_copy["entity_id"] = eid
        mirror_event(ev_copy, event_id=event_id, snapshot_b64=b64)
    except Exception as _mir_err:
        print(f"[3c_eng] mirror import failed (ignored): {str(_mir_err)[:80]}")

    return event_id

def db_get_events(
    limit: int = 10,
    page: int = 1,
    camera_id: Optional[str] = None,
    person_id: Optional[int] = None,
    matched: Optional[bool] = None,
    suspected: Optional[bool] = None,
    person_type: Optional[str] = None,
    search: Optional[str] = None,
    hours: int = 24,
    include_snapshots: bool = False
) -> dict:
    """List events with backend pagination (10 per page by default).
    Snapshots are EXCLUDED by default to keep payloads tiny and fast."""
    from sqlalchemy import func
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    offset = max(0, (page - 1) * limit)
    
    with engine.connect() as conn:
        base_filters = [events_table.c.timestamp >= cutoff]
        if camera_id and camera_id != "all":
            base_filters.append(events_table.c.camera_id == camera_id)
        if person_id is not None:
            base_filters.append(events_table.c.person_id == person_id)
        if matched is not None:
            base_filters.append(events_table.c.matched == matched)
        if suspected is not None:
            base_filters.append(events_table.c.suspected == suspected)
        if person_type:
            base_filters.append(events_table.c.person_type == person_type)
        if search:
            s_pattern = f"%{search.strip()}%"
            base_filters.append(
                (events_table.c.person_name.like(s_pattern)) | (events_table.c.camera_id.like(s_pattern))
            )

        # Count total matching rows
        count_q = select(func.count()).select_from(events_table).where(*base_filters)
        total_count = conn.execute(count_q).scalar() or 0

        # Paginated events
        q = select(events_table).where(*base_filters).order_by(events_table.c.timestamp.desc()).offset(offset).limit(limit)
        rows = _rows_to_list(conn.execute(q))

    for r in rows:
        r["bbox"] = _json_field(r.get("bbox"), "[]")
        if include_snapshots:
            r["snapshot_data_url"] = b64_to_data_url(r.get("snapshot_b64"))
        else:
            r.pop("snapshot_b64", None)   # keep payload small

    total_pages = max(1, (total_count + limit - 1) // limit) if total_count > 0 else 1
    return {
        "events": rows,
        "total_count": total_count,
        "count": len(rows),
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

def db_delete_event(event_id: int) -> bool:
    """Delete an event and its linked attendance record (cascade delete)."""
    with engine.connect() as conn:
        # First fetch the event to find linked attendance
        ev = conn.execute(
            select(events_table).where(events_table.c.id == event_id)
        ).fetchone()
        if not ev:
            return False
        ev_dict = _row_to_dict(ev)
        # Delete the event
        conn.execute(
            delete(events_table).where(events_table.c.id == event_id)
        )
        # Also delete linked attendance record (same person + camera + same day)
        pid = ev_dict.get("person_id")
        cam = ev_dict.get("camera_id")
        ts  = ev_dict.get("timestamp", "")
        day = ts[:10] if ts else None
        if pid and cam and day:
            conn.execute(
                delete(attendance_table).where(and_(
                    attendance_table.c.person_id == pid,
                    attendance_table.c.camera_id == cam,
                    attendance_table.c.date == day,
                ))
            )
        conn.commit()
    return True

def db_update_event(event_id: int, person_name: Optional[str], camera_id: Optional[str]):
    data = {}
    if person_name:
        data["person_name"] = person_name
    if camera_id:
        data["camera_id"] = camera_id
    if not data:
        return None
    with engine.connect() as conn:
        conn.execute(
            update(events_table).where(events_table.c.id == event_id).values(**data)
        )
        conn.commit()
        row = conn.execute(
            select(events_table).where(events_table.c.id == event_id)
        ).fetchone()
    return _row_to_dict(row) if row else None

def db_purge_old_events(keep: int = 5000):
    """Keep only the latest `keep` events to control DB size."""
    with engine.connect() as conn:
        # MySQL doesn't support LIMIT in subquery for DELETE
        # Step 1: find the cutoff id
        cutoff_row = conn.execute(text(
            f"SELECT id FROM `3c_eng_events` ORDER BY id DESC LIMIT 1 OFFSET {keep}"
        )).fetchone()
        if cutoff_row:
            conn.execute(text(
                "DELETE FROM `3c_eng_events` WHERE id <= :cutoff"
            ), {"cutoff": cutoff_row[0]})
            conn.commit()

# ─── ATTENDANCE ───────────────────────────────────────────────

def db_get_attendance(
    date: Optional[str] = None,
    status: Optional[str] = None,
    person_id: Optional[int] = None,
    limit: int = 200
) -> List[dict]:
    with engine.connect() as conn:
        q = select(attendance_table)
        if date:
            q = q.where(attendance_table.c.date == date)
        if status:
            q = q.where(attendance_table.c.status == status)
        if person_id is not None:
            q = q.where(attendance_table.c.person_id == person_id)
        q = q.order_by(attendance_table.c.checkin_time.desc()).limit(limit)
        rows = _rows_to_list(conn.execute(q))
    for r in rows:
        # keep payload small — thumbnails lazy-load via /api/v1/attendance/{id}/snapshot
        r.pop("snapshot_b64", None)
    return rows

def db_save_attendance(record: dict, snapshot_array=None) -> int:
    b64 = numpy_to_b64(snapshot_array) if snapshot_array is not None else None
    with engine.connect() as conn:
        result = conn.execute(insert(attendance_table).values(
            person_id    = record.get("person_id"),
            person_name  = record.get("person_name"),
            camera_id    = record.get("camera_id"),
            checkin_time = record.get("checkin_time"),
            checkout_time= record.get("checkout_time"),
            duration_min = record.get("duration_min"),
            duration_str = record.get("duration_str"),
            status       = record.get("status", "checked_in"),
            snapshot_b64 = b64,
            snapshot_path= record.get("snapshot_path"),
            date         = record.get("date"),
        ))
        conn.commit()
        return result.inserted_primary_key[0]

def db_update_attendance(record_id: int, data: dict):
    with engine.connect() as conn:
        conn.execute(
            update(attendance_table)
            .where(attendance_table.c.id == record_id)
            .values(**data)
        )
        conn.commit()

def db_delete_attendance_record(record_id: int) -> bool:
    """Delete an attendance record and its linked event(s) (cascade delete)."""
    with engine.connect() as conn:
        row = conn.execute(
            select(attendance_table).where(attendance_table.c.id == record_id)
        ).fetchone()
        if not row:
            return False
        rec = _row_to_dict(row)
        # Delete the attendance record
        conn.execute(
            delete(attendance_table).where(attendance_table.c.id == record_id)
        )
        # Also delete linked events (same person + camera + same day)
        pid = rec.get("person_id")
        cam = rec.get("camera_id")
        day = rec.get("date")
        if pid and cam and day:
            conn.execute(
                delete(events_table).where(and_(
                    events_table.c.person_id == pid,
                    events_table.c.camera_id == cam,
                    events_table.c.timestamp.like(f"{day}%"),
                ))
            )
        conn.commit()
    return True

def db_delete_attendance_bulk(ids: List[int]) -> int:
    """Delete multiple attendance records and their linked events."""
    if not ids:
        return 0
    with engine.connect() as conn:
        # Fetch records to find linked events
        rows = conn.execute(
            select(attendance_table).where(attendance_table.c.id.in_(ids))
        ).fetchall()
        deleted = 0
        for row in rows:
            rec = _row_to_dict(row)
            pid = rec.get("person_id")
            cam = rec.get("camera_id")
            day = rec.get("date")
            if pid and cam and day:
                conn.execute(
                    delete(events_table).where(and_(
                        events_table.c.person_id == pid,
                        events_table.c.camera_id == cam,
                        events_table.c.timestamp.like(f"{day}%"),
                    ))
                )
        # Delete attendance records
        res = conn.execute(
            delete(attendance_table).where(attendance_table.c.id.in_(ids))
        )
        deleted = res.rowcount
        conn.commit()
    return deleted

def db_get_open_checkin(person_id: int) -> Optional[dict]:
    """Get the most recent checked_in record for a person."""
    with engine.connect() as conn:
        row = conn.execute(
            select(attendance_table)
            .where(and_(
                attendance_table.c.person_id == person_id,
                attendance_table.c.status == "checked_in"
            ))
            .order_by(attendance_table.c.checkin_time.desc())
            .limit(1)
        ).fetchone()
    return _row_to_dict(row) if row else None

def db_get_all_open_checkins() -> List[dict]:
    with engine.connect() as conn:
        rows = _rows_to_list(conn.execute(
            select(attendance_table).where(attendance_table.c.status == "checked_in")
        ))
    return rows

def db_get_todays_attendance() -> List[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    return db_get_attendance(date=today, limit=5000)

# ─── ALERTS ───────────────────────────────────────────────────

def db_save_alert(alert: dict) -> int:
    with engine.connect() as conn:
        result = conn.execute(insert(alerts_table).values(
            type         = alert.get("type"),
            severity     = alert.get("severity", "low"),
            message      = alert.get("message"),
            person_id    = alert.get("person_id"),
            acknowledged = alert.get("acknowledged", False),
            created_at   = alert.get("created_at", datetime.now().isoformat()),
        ))
        conn.commit()
        return result.inserted_primary_key[0]

def db_get_alerts(acknowledged: Optional[bool] = None, limit: int = 20) -> List[dict]:
    with engine.connect() as conn:
        q = select(alerts_table)
        if acknowledged is not None:
            q = q.where(alerts_table.c.acknowledged == acknowledged)
        q = q.order_by(alerts_table.c.created_at.desc()).limit(limit)
        return _rows_to_list(conn.execute(q))

def db_update_alert(alert_id: int, acknowledged: bool):
    with engine.connect() as conn:
        conn.execute(
            update(alerts_table)
            .where(alerts_table.c.id == alert_id)
            .values(acknowledged=acknowledged)
        )
        conn.commit()

def db_purge_old_alerts(keep: int = 1000):
    with engine.connect() as conn:
        cutoff_row = conn.execute(text(
            f"SELECT id FROM `3c_eng_alerts` ORDER BY id DESC LIMIT 1 OFFSET {keep}"
        )).fetchone()
        if cutoff_row:
            conn.execute(text(
                "DELETE FROM `3c_eng_alerts` WHERE id <= :cutoff"
            ), {"cutoff": cutoff_row[0]})
            conn.commit()

# ─── UNKNOWN PERSONS ──────────────────────────────────────────

def db_save_unknown(unknown: dict, snapshot_array=None) -> int:
    b64 = numpy_to_b64(snapshot_array) if snapshot_array is not None else None
    b64s = [b64] if b64 else []
    with engine.connect() as conn:
        result = conn.execute(insert(unknown_persons_table).values(
            tracking_id   = unknown.get("tracking_id"),
            first_seen    = unknown.get("first_seen"),
            last_seen     = unknown.get("last_seen"),
            camera_ids    = _to_json(unknown.get("camera_ids", [])),
            snapshots     = _to_json(unknown.get("snapshots", [])),
            snapshot_b64s = _to_json(b64s),
            event_count   = unknown.get("event_count", 1),
            embedding     = _to_json(unknown.get("embedding")) if unknown.get("embedding") else None,
            resolved      = False,
            date          = unknown.get("date"),
        ))
        conn.commit()
        return result.inserted_primary_key[0]

def db_get_unknowns(
    resolved: Optional[bool] = None,
    date: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None
) -> dict:
    from sqlalchemy import func
    offset = max(0, (page - 1) * limit)
    with engine.connect() as conn:
        base_filters = []
        if resolved is not None:
            base_filters.append(unknown_persons_table.c.resolved == resolved)
        if date:
            base_filters.append(unknown_persons_table.c.date == date)
        if search:
            s_pattern = f"%{search.strip()}%"
            base_filters.append(
                (unknown_persons_table.c.tracking_id.like(s_pattern)) |
                (unknown_persons_table.c.camera_ids.like(s_pattern))
            )

        count_q = select(func.count()).select_from(unknown_persons_table)
        if base_filters:
            count_q = count_q.where(*base_filters)
        total_count = conn.execute(count_q).scalar() or 0

        q = select(unknown_persons_table)
        if base_filters:
            q = q.where(*base_filters)
        q = q.order_by(unknown_persons_table.c.last_seen.desc()).offset(offset).limit(limit)
        rows = _rows_to_list(conn.execute(q))

    for r in rows:
        r["camera_ids"]  = _json_field(r.get("camera_ids"), "[]")
        r["snapshots"]   = _json_field(r.get("snapshots"),  "[]")
        # keep payload small — thumbnail lazy-loads via /api/v1/unknowns/{id}/snapshot
        r.pop("snapshot_b64s", None)
        r.pop("embedding", None)   # don't send large embeddings to UI

    total_pages = max(1, (total_count + limit - 1) // limit) if total_count > 0 else 1
    return {
        "unknown_persons": rows,
        "total_count": total_count,
        "count": len(rows),
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }

def db_get_unknown_by_id(unknown_id: int) -> Optional[dict]:
    with engine.connect() as conn:
        row = conn.execute(
            select(unknown_persons_table)
            .where(unknown_persons_table.c.id == unknown_id)
        ).fetchone()
    if not row:
        return None
    r = _row_to_dict(row)
    r["camera_ids"]  = _json_field(r.get("camera_ids"), "[]")
    r["snapshots"]   = _json_field(r.get("snapshots"),  "[]")
    r["snapshot_b64s"] = _json_field(r.get("snapshot_b64s"), "[]")
    r["embedding"]   = _json_field(r.get("embedding"),  "null")
    return r

def db_resolve_unknown(unknown_id: int, action: str,
                       enrolled_as: Optional[str] = None,
                       enrolled_count: int = 0,
                       person_id: Optional[int] = None):
    data = {
        "resolved":        True,
        "resolved_action": action,
        "resolved_at":     datetime.now().isoformat(),
    }
    if enrolled_as:
        data["enrolled_as"]    = enrolled_as
        data["enrolled_count"] = enrolled_count
    if person_id:
        data["person_id"] = person_id
    with engine.connect() as conn:
        conn.execute(
            update(unknown_persons_table)
            .where(unknown_persons_table.c.id == unknown_id)
            .values(**data)
        )
        conn.commit()

def db_delete_unknown(unknown_id: int) -> bool:
    with engine.connect() as conn:
        res = conn.execute(
            delete(unknown_persons_table)
            .where(unknown_persons_table.c.id == unknown_id)
        )
        conn.commit()
    return res.rowcount > 0

def db_clear_resolved_unknowns() -> int:
    with engine.connect() as conn:
        res = conn.execute(
            delete(unknown_persons_table)
            .where(unknown_persons_table.c.resolved == True)
        )
        conn.commit()
    return res.rowcount

# ─── ANALYTICS HELPERS ────────────────────────────────────────

def db_get_events_for_analytics(target_date: str) -> List[dict]:
    """Get all events for a specific date (for headcount/occupancy)."""
    with engine.connect() as conn:
        q = select(
            events_table.c.id,
            events_table.c.camera_id,
            events_table.c.person_id,
            events_table.c.person_type,
            events_table.c.matched,
            events_table.c.timestamp,
            events_table.c.bbox,
        ).where(events_table.c.timestamp.like(f"{target_date}%"))
        rows = _rows_to_list(conn.execute(q))
    for r in rows:
        r["bbox"] = _json_field(r.get("bbox"), "[]")
    return rows

def db_get_attendance_for_analytics(target_date: str) -> List[dict]:
    with engine.connect() as conn:
        rows = _rows_to_list(conn.execute(
            select(
                attendance_table.c.id,
                attendance_table.c.person_id,
                attendance_table.c.status,
                attendance_table.c.checkin_time,
                attendance_table.c.checkout_time,
                attendance_table.c.date,
            ).where(attendance_table.c.date == target_date)
        ))
    return rows

def db_get_all_attendance_dates() -> List[dict]:
    """Get attendance count per date (last 7 days) for daily chart."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT date, COUNT(*) as count
            FROM `3c_eng_attendance`
            GROUP BY date
            ORDER BY date DESC
            LIMIT 7
        """)).fetchall()
    return [{"date": r[0], "count": r[1]} for r in rows]

def db_get_dashboard_stats(target_date: Optional[str] = None) -> dict:
    """Get fast exact database count aggregations for dashboard stat cards."""
    today = target_date or datetime.now().strftime("%Y-%m-%d")
    with engine.connect() as conn:
        att_in = conn.execute(select(text("COUNT(*)")).select_from(attendance_table).where(and_(attendance_table.c.date == today, attendance_table.c.status == "checked_in"))).scalar() or 0
        att_out = conn.execute(select(text("COUNT(*)")).select_from(attendance_table).where(and_(attendance_table.c.date == today, attendance_table.c.status == "checked_out"))).scalar() or 0
        att_total = conn.execute(select(text("COUNT(*)")).select_from(attendance_table).where(attendance_table.c.date == today)).scalar() or 0

        total_det = conn.execute(select(text("COUNT(*)")).select_from(events_table).where(events_table.c.timestamp.like(f"{today}%"))).scalar() or 0
        rec_det = conn.execute(select(text("COUNT(*)")).select_from(events_table).where(and_(events_table.c.timestamp.like(f"{today}%"), events_table.c.matched == True, events_table.c.person_type == "employee"))).scalar() or 0
        vis_det = conn.execute(select(text("COUNT(*)")).select_from(events_table).where(and_(events_table.c.timestamp.like(f"{today}%"), events_table.c.person_type == "visitor"))).scalar() or 0
        blk_det = conn.execute(select(text("COUNT(*)")).select_from(events_table).where(and_(events_table.c.timestamp.like(f"{today}%"), events_table.c.person_type == "blacklisted"))).scalar() or 0
        unk_det = conn.execute(select(text("COUNT(*)")).select_from(events_table).where(and_(events_table.c.timestamp.like(f"{today}%"), events_table.c.matched == False))).scalar() or 0

        enrolled_cnt = conn.execute(select(text("COUNT(*)")).select_from(persons_table).where(or_(persons_table.c.watchlist == "employee", persons_table.c.watchlist == None))).scalar() or 0
        blk_cnt = conn.execute(select(text("COUNT(*)")).select_from(persons_table).where(persons_table.c.watchlist == "blacklist")).scalar() or 0
        vis_cnt = conn.execute(select(text("COUNT(*)")).select_from(persons_table).where(persons_table.c.watchlist == "visitor")).scalar() or 0

        unres_unk = conn.execute(select(text("COUNT(*)")).select_from(unknown_persons_table).where(unknown_persons_table.c.resolved == False)).scalar() or 0

    daily = db_get_all_attendance_dates()

    return {
        "period_hours": 24,
        "total_detections": total_det,
        "recognized": rec_det,
        "visitors": vis_det,
        "blacklisted_detections": blk_det,
        "unknown": unk_det,
        "enrolled": enrolled_cnt,
        "blacklist_count": blk_cnt,
        "visitor_count": vis_cnt,
        "currently_in": att_in,
        "checked_out_today": att_out,
        "total_today": att_total,
        "unresolved_unknowns": unres_unk,
        "daily_attendance": daily,
    }


def db_get_dashboard_full(target_date: str = None, camera_id: Optional[str] = None) -> dict:
    """All-in-one dashboard data: stats + headcount + occupancy in minimal DB calls."""
    if not target_date:
        target_date = datetime.now().strftime("%Y-%m-%d")

    with engine.connect() as conn:
        att_sql = """
            SELECT
                COALESCE(SUM(CASE WHEN status = 'checked_in' THEN 1 ELSE 0 END), 0) AS att_in,
                COALESCE(SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END), 0) AS att_out,
                COUNT(*) AS att_total
            FROM `3c_eng_attendance` WHERE date = :d
        """
        att_params = {"d": target_date}
        if camera_id and camera_id != "all":
            att_sql += " AND camera_id = :cam"
            att_params["cam"] = camera_id
        att_row = conn.execute(text(att_sql), att_params).fetchone()

        ev_sql = """
            SELECT
                COUNT(*) AS total_det,
                COALESCE(SUM(CASE WHEN matched = :m_true AND person_type = 'employee' THEN 1 ELSE 0 END), 0) AS rec_det,
                COALESCE(SUM(CASE WHEN person_type = 'visitor' THEN 1 ELSE 0 END), 0) AS vis_det,
                COALESCE(SUM(CASE WHEN person_type = 'blacklisted' THEN 1 ELSE 0 END), 0) AS blk_det,
                COALESCE(SUM(CASE WHEN matched = :m_false THEN 1 ELSE 0 END), 0) AS unk_det
            FROM `3c_eng_events` WHERE timestamp LIKE :ts
        """
        ev_params = {"ts": f"{target_date}%", "m_true": True, "m_false": False}
        if camera_id and camera_id != "all":
            ev_sql += " AND camera_id = :cam"
            ev_params["cam"] = camera_id
        ev_row = conn.execute(text(ev_sql), ev_params).fetchone()

        pr_row = conn.execute(text("""
            SELECT
                COALESCE(SUM(CASE WHEN watchlist IN ('employee') OR watchlist IS NULL THEN 1 ELSE 0 END), 0) AS enrolled,
                COALESCE(SUM(CASE WHEN watchlist = 'blacklist' THEN 1 ELSE 0 END), 0) AS blk_cnt,
                COALESCE(SUM(CASE WHEN watchlist = 'visitor' THEN 1 ELSE 0 END), 0) AS vis_cnt
            FROM `3c_eng_persons`
        """)).fetchone()

        unres_unk = conn.execute(
            select(text("COUNT(*)")).select_from(unknown_persons_table)
            .where(unknown_persons_table.c.resolved == False)
        ).scalar() or 0

        if DB_TYPE == "mysql":
            hour_sql = """
                SELECT DATE_FORMAT(timestamp, '%Y-%m-%d %H:00:00') AS hour, COUNT(*) AS cnt
                FROM `3c_eng_events` WHERE timestamp LIKE :ts
            """
        else:
            hour_sql = """
                SELECT SUBSTR(timestamp, 1, 13) || ':00:00' AS hour, COUNT(*) AS cnt
                FROM `3c_eng_events` WHERE timestamp LIKE :ts
            """
        hour_params = {"ts": f"{target_date}%", "db_type": DB_TYPE}
        if camera_id and camera_id != "all":
            hour_sql += " AND camera_id = :cam"
            hour_params["cam"] = camera_id
        hour_sql += " GROUP BY hour ORDER BY hour"
        hour_rows = conn.execute(text(hour_sql), hour_params).fetchall()

        hc_rows = conn.execute(text("""
            SELECT camera_id,
                   COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN matched = :m_true THEN 1 ELSE 0 END), 0) AS known,
                   COALESCE(SUM(CASE WHEN matched = :m_false THEN 1 ELSE 0 END), 0) AS unknown,
                   COUNT(DISTINCT CASE WHEN matched = :m_true AND person_id IS NOT NULL THEN person_id ELSE NULL END) AS unique_known
            FROM `3c_eng_events` WHERE timestamp LIKE :ts
            GROUP BY camera_id
        """), {"ts": f"{target_date}%", "m_true": True, "m_false": False}).fetchall()

        att_rows_sql = "SELECT checkin_time, checkout_time FROM `3c_eng_attendance` WHERE date = :d"
        att_rows_params = {"d": target_date}
        if camera_id and camera_id != "all":
            att_rows_sql += " AND camera_id = :cam"
            att_rows_params["cam"] = camera_id
        att_rows = conn.execute(text(att_rows_sql), att_rows_params).fetchall()

    daily = db_get_all_attendance_dates()
    hourly_timeline = [{"hour": r[0], "count": r[1]} for r in hour_rows]
    hourly = {h: {"hour": h, "entry": 0, "exit": 0, "occupancy": 0} for h in range(24)}
    for row in att_rows:
        ci = row[0]
        co = row[1]
        try:
            if ci: hourly[int(ci[11:13])]["entry"] += 1
        except (ValueError, IndexError): pass
        try:
            if co: hourly[int(co[11:13])]["exit"] += 1
        except (ValueError, IndexError): pass
    running = 0
    for h in range(24):
        running += hourly[h]["entry"] - hourly[h]["exit"]
        hourly[h]["occupancy"] = max(0, running)

    cameras = db_get_cameras()
    cam_map = {c["id"]: c for c in cameras}
    headcount = []
    for r in hc_rows:
        cid = r[0]
        cam = cam_map.get(cid, {})
        headcount.append({
            "camera_id": cid,
            "camera_name": cam.get("name", cid),
            "camera_type": cam.get("camera_type", "checkin"),
            "has_zone": len(cam.get("detection_zone", [])) >= 3,
            "total_detections": r[1],
            "known_count": r[2],
            "unknown_count": r[3],
            "unique_known": r[4],
            "total_passed": (r[2] or 0) + (r[3] or 0),
        })

    return {
        "period_hours": 24,
        "total_detections": ev_row[0] if ev_row else 0,
        "recognized": ev_row[1] if ev_row else 0,
        "visitors": ev_row[2] if ev_row else 0,
        "blacklisted_detections": ev_row[3] if ev_row else 0,
        "unknown": ev_row[4] if ev_row else 0,
        "enrolled": pr_row[0] if pr_row else 0,
        "blacklist_count": pr_row[1] if pr_row else 0,
        "visitor_count": pr_row[2] if pr_row else 0,
        "currently_in": att_row[0] if att_row else 0,
        "checked_out_today": att_row[1] if att_row else 0,
        "total_today": att_row[2] if att_row else 0,
        "unresolved_unknowns": unres_unk,
        "daily_attendance": daily,
        "hourly_timeline": hourly_timeline,
        "occupancy": list(hourly.values()),
        "headcount": headcount,
        "date": target_date,
    }

# ─── JSON → DB MIGRATION ──────────────────────────────────────

def migrate_json_to_db():
    """
    DEPRECATED: All data is now stored directly in the database.
    This function is kept as a no-op for backward compatibility.
    """
    pass

# ─── SYSTEM SETTINGS HELPERS ──────────────────────────────────
DEFAULT_SETTINGS = {
    "face_threshold": "0.50",
    "blacklist_threshold": "0.35",
    "visitor_threshold": "0.50",
    "dedup_threshold": "0.65",
    "camera_cooldown": "120",
    "global_cooldown": "300",
    "dedup_seconds": "5",
    "known_suppress_seconds": "10",
    "camera_unknown_cooldown": "5",
    "capture_known_only": "false",
    "camera_mode": "3mp",   # 8mp | 3mp | both — controls which cameras are active
}

def db_get_system_settings() -> dict:
    """Retrieve all stored system settings with fallbacks."""
    res = dict(DEFAULT_SETTINGS)
    try:
        with engine.connect() as conn:
            rows = conn.execute(select(settings_table)).fetchall()
            for r in rows:
                res[r.key_name] = r.value
    except Exception as e:
        print(f"[DB] Error loading system settings: {e}")
    return res

def db_save_system_setting(key: str, value: str):
    """Save or update a system setting key-value pair."""
    try:
        with engine.connect() as conn:
            stmt = select(settings_table).where(settings_table.c.key_name == key)
            row = conn.execute(stmt).fetchone()
            if row:
                conn.execute(settings_table.update().where(settings_table.c.key_name == key).values(value=str(value)))
            else:
                conn.execute(settings_table.insert().values(key_name=key, value=str(value)))
            conn.commit()
    except Exception as e:
        print(f"[DB] Error saving system setting {key}: {e}")

# ─── KLOUDSPOT FRS COMPARISON HELPERS ─────────────────────────

def db_save_kloudspot_events_bulk(events_list: List[dict]) -> int:
    """
    Insert or update raw events fetched from Kloudspot API.
    Uses bulk delete+insert per batch for speed — avoids per-row SELECT over network.
    """
    if not events_list:
        return 0
    now_iso = datetime.now().isoformat()
    rows = []
    for ev in events_list:
        # KloudSpot's "id" field is NOT unique per event (same value for same-second batch).
        # Use trackingId as the unique row key — it's always unique (e.g. "7426::checkin").
        tracking_id = str(ev.get("trackingId") or "")
        ev_id = tracking_id or str(ev.get("id") or f"ks_{int(time.time()*1000)}")
        first = ev.get("firstName") or ev.get("first_name") or ""
        last  = ev.get("lastName")  or ev.get("last_name")  or ""
        full_name = ev.get("full_name") or f"{first} {last}".strip() or "Unknown"
        ts_ms = ev.get("timestamp") or ev.get("timestamp_ms") or (time.time() * 1000)
        if isinstance(ts_ms, str):
            try: ts_ms = float(ts_ms)
            except: ts_ms = time.time() * 1000
        ts_iso   = datetime.fromtimestamp(ts_ms / 1000.0).isoformat() if ts_ms > 0 else now_iso
        img_b64  = ev.get("image") or ev.get("image_b64")
        if img_b64 and img_b64.startswith("data:image"):
            img_b64 = img_b64.split(",", 1)[-1]
        rows.append({
            "id":           ev_id,
            "tracking_id":  tracking_id,
            "entity_id":    str(ev.get("entityId") or ""),
            "first_name":   first,
            "last_name":    last,
            "full_name":    full_name,
            "location_id":  str(ev.get("locationId") or "69f98ea807d81c618181ba50"),
            "location_type":str(ev.get("locationType") or "ENTRY"),
            "direction":    str(ev.get("direction") or "in").lower(),
            "object_type":  str(ev.get("objectType") or "human"),
            "timestamp_ms": float(ts_ms),
            "timestamp_iso":ts_iso,
            "date":         ts_iso[:10],
            "image_b64":    img_b64,
            "raw_json":     json.dumps(ev, default=str),
            "created_at":   now_iso
        })

    # Full refresh: clear table then bulk-insert in batches
    BATCH = 200
    saved = 0
    with engine.connect() as conn:
        conn.execute(delete(kloudspot_events_table))
        conn.commit()
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i+BATCH]
            # Deduplicate within chunk by id (keep last)
            seen_ids = {}
            for r in chunk:
                seen_ids[r["id"]] = r
            unique_chunk = list(seen_ids.values())
            for row in unique_chunk:
                conn.execute(insert(kloudspot_events_table).values(**row))
            conn.commit()
            saved += len(unique_chunk)
    return saved

def db_get_kloudspot_events(
    date: Optional[str] = None,
    location_id: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 2000
) -> List[dict]:
    """Retrieve Kloudspot synced events from DB."""
    with engine.connect() as conn:
        q = select(kloudspot_events_table)
        conditions = []
        if date:
            conditions.append(kloudspot_events_table.c.date == date)
        if location_id:
            conditions.append(kloudspot_events_table.c.location_id == location_id)
        if direction:
            conditions.append(kloudspot_events_table.c.direction == direction)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.order_by(kloudspot_events_table.c.timestamp_ms.desc()).limit(limit)
        rows = _rows_to_list(conn.execute(q))
    for r in rows:
        if r.get("image_b64"):
            r["image_data_url"] = b64_to_data_url(r["image_b64"])
    return rows

def db_clear_kloudspot_events():
    """Clear all Kloudspot events (e.g. for full resync)."""
    with engine.connect() as conn:
        conn.execute(delete(kloudspot_events_table))
        conn.commit()

def db_seed_sample_comparison_data():
    """Seed sample data to test and preview Kloudspot comparison immediately."""
    from datetime import datetime, timedelta
    import random
    
    # Get enrolled persons from DB or create a standard list
    persons = db_get_persons()
    person_names = [p["name"] for p in persons if p.get("name")] if persons else [
        "Chetan Kumar", "Bhargav R", "Siva Vara", "Anand Sharma",
        "Priya Patel", "Rahul Verma", "Deepak Rao", "Kavita Nair",
        "Vikram Singh", "Sunita Gupta", "Ramesh K", "Divya Menon"
    ]
    person_photos = {p["name"]: p.get("photo_b64") for p in persons if p.get("name") and p.get("photo_b64")}
    
    now = datetime.now()
    sample_ks = []
    sample_our = []
    
    locations = ["69f98ea807d81c618181ba50", "69f98f9907d81c618181ba5c"]
    
    for i in range(30):
        offset_mins = random.randint(5, 480)
        t = now - timedelta(minutes=offset_mins)
        ts_ms = t.timestamp() * 1000
        pname = random.choice(person_names)
        loc = random.choice(locations)
        direction = "in" if loc == locations[0] else "out"
        loc_type = "ENTRY" if direction == "in" else "EXIT"
        
        # Decide scenario:
        # 75% both match, 10% KS only, 10% Our only, 5% mismatch
        scenario = random.choices(["both", "ks_only", "our_only", "mismatch"], weights=[75, 10, 10, 5])[0]
        
        if scenario in ("both", "ks_only", "mismatch"):
            parts = pname.split()
            first = parts[0]
            last = parts[1] if len(parts) > 1 else ""
            sample_ks.append({
                "id": f"ks_{i}_{int(ts_ms)}",
                "trackingId": f"track_{i}",
                "entityId": f"ent_{i}",
                "firstName": first,
                "lastName": last,
                "full_name": pname,
                "locationId": loc,
                "locationType": loc_type,
                "direction": direction,
                "objectType": "human",
                "timestamp": ts_ms,
                "image": person_photos.get(pname)
            })
            
        if scenario in ("both", "our_only", "mismatch"):
            # our event
            detected_name = pname if scenario != "mismatch" else random.choice(person_names)
            # slight jitter of 1-4 seconds
            t_jitter = t + timedelta(seconds=random.randint(-3, 3))
            sample_our.append({
                "camera_id": "camera_entry" if direction == "in" else "camera_exit",
                "person_id": random.randint(1, 10),
                "person_name": detected_name,
                "person_type": "employee",
                "confidence": round(random.uniform(0.72, 0.96), 2),
                "bbox": [100, 100, 250, 300],
                "matched": True,
                "suspected": False,
                "timestamp": t_jitter.isoformat(),
                "snapshot_b64": person_photos.get(detected_name)
            })
            
    # Save KS events
    db_save_kloudspot_events_bulk(sample_ks)
    # Save local events
    for o in sample_our:
        db_save_event(o)
    return len(sample_ks), len(sample_our)



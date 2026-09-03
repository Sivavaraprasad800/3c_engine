"""
external_events_db.py — Mirror FRS events to the 3C MySQL database (AWS RDS).

Behavior:
  • Connects using DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME env vars.
  • Creates EXACTLY ONE table: `3c_eng_events` (CREATE TABLE IF NOT EXISTS).
  • NEVER runs migrations, NEVER reads or modifies any other table.
  • `mirror_event()` is fire-and-forget: any failure is logged and ignored so
    the main FRS pipeline is never affected.

Table: 3c_eng_events — one row per FRS detection event.
"""

import os
import json
import threading
from datetime import datetime

import pymysql

# ── Config from env (with the provided defaults) ─────────────────
MYSQL_HOST     = os.environ.get("DB_HOST", "zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com")
MYSQL_PORT     = int(os.environ.get("DB_PORT", "3306"))
MYSQL_USER     = os.environ.get("DB_USER", "3c_dev_user")
MYSQL_PASSWORD = os.environ.get("DB_PASSWORD", "2H&5bQU2*)J)")
MYSQL_DB       = os.environ.get("DB_NAME", "3C_Z_ATTEND_AI")

TABLE_NAME = "3c_eng_events"

_conn = None
_lock = threading.Lock()


def _get_connection():
    """Lazy singleton connection — reconnects if dropped."""
    global _conn
    if _conn is not None:
        try:
            with _conn.cursor() as c:
                c.execute("SELECT 1")
            return _conn
        except Exception:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
    _conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        connect_timeout=10,
        write_timeout=10,
        read_timeout=10,
        charset="utf8mb4",
        autocommit=True,
    )
    return _conn


def ensure_table():
    """
    Create ONLY our own table if it does not exist.
    No migrations, no other tables are read or modified.
    """
    ddl = f"""
    CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
        `id`           BIGINT       NOT NULL AUTO_INCREMENT,
        `event_id`     INT          NULL COMMENT 'FRS events.id from main DB',
        `camera_id`    VARCHAR(100) NULL,
        `person_id`    INT          NULL,
        `entity_id`    VARCHAR(100) NULL,
        `person_name`  VARCHAR(200) NULL,
        `person_type`  VARCHAR(50)  NULL,
        `confidence`   FLOAT        NULL,
        `matched`      TINYINT(1)   DEFAULT 0,
        `suspected`    TINYINT(1)   DEFAULT 0,
        `bbox`         VARCHAR(200) NULL,
        `timestamp`    VARCHAR(50)  NULL,
        `snapshot_b64` LONGTEXT     NULL,
        `synced_at`    DATETIME     DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `idx_3c_eng_ts` (`timestamp`),
        KEY `idx_3c_eng_person` (`person_id`),
        KEY `idx_3c_eng_entity` (`entity_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    with _lock:
        conn = _get_connection()
        with conn.cursor() as c:
            c.execute(ddl)
            # Safely ensure entity_id column exists if table was created previously without it
            try:
                c.execute(f"ALTER TABLE `{TABLE_NAME}` ADD COLUMN `entity_id` VARCHAR(100) NULL AFTER `person_id`")
            except Exception:
                pass
        conn.commit()


def mirror_event(event: dict, event_id=None, snapshot_b64=None) -> bool:
    """
    Copy one FRS event into `3c_eng_events`.
    Fire-and-forget: returns True on success, False on any failure
    (failures are logged but NEVER raised — main pipeline unaffected).
    """
    try:
        bbox = event.get("bbox")
        if isinstance(bbox, (list, dict)):
            bbox = json.dumps(bbox)
        sql = f"""
        INSERT INTO `{TABLE_NAME}`
            (event_id, camera_id, person_id, entity_id, person_name, person_type,
             confidence, matched, suspected, bbox, `timestamp`, snapshot_b64)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            event_id if event_id is not None else event.get("id"),
            event.get("camera_id"),
            event.get("person_id"),
            event.get("entity_id"),
            (event.get("person_name") or "Unknown")[:200],
            event.get("person_type") or "unknown",
            event.get("confidence", 0.0),
            1 if event.get("matched") else 0,
            1 if event.get("suspected") else 0,
            bbox,
            event.get("timestamp") or datetime.now().isoformat(),
            snapshot_b64,
        )
        with _lock:
            conn = _get_connection()
            with conn.cursor() as c:
                c.execute(sql, params)
            conn.commit()
        return True
    except Exception as e:
        print(f"[3c_eng] Event mirror failed (ignored): {str(e)[:100]}")
        # drop the connection so next call reconnects fresh
        global _conn
        try:
            if _conn is not None:
                _conn.close()
        except Exception:
            pass
        _conn = None
        return False


def test_connection():
    """Connect + create our table + verify. Returns (ok, info_str)."""
    try:
        ensure_table()
        with _lock:
            conn = _get_connection()
            with conn.cursor() as c:
                c.execute(f"SELECT COUNT(*) FROM `{TABLE_NAME}`")
                count = c.fetchone()[0]
        return True, f"table `{TABLE_NAME}` ready, rows: {count}"
    except Exception as e:
        return False, str(e)[:200]


if __name__ == "__main__":
    ok, info = test_connection()
    print(("OK — " if ok else "FAIL — ") + info)

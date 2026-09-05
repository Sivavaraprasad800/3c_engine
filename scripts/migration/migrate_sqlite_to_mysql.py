"""
migrate_sqlite_to_mysql.py
──────────────────────────
One-time migration: copies all data from local SQLite (data/frs.db)
into MySQL 3C_Z_ATTEND_AI (3c_eng_ tables).

Safe to run multiple times — skips rows that already exist.
Run: python migrate_sqlite_to_mysql.py
"""

import sqlite3
import pymysql
import json
from datetime import datetime

SQLITE_DB = r"data\frs.db"
MYSQL = dict(
    host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10
)

sq = sqlite3.connect(SQLITE_DB)
sq.row_factory = lambda cur, row: {col[0]: row[idx] for idx, col in enumerate(cur.description)}
sc = sq.cursor()

my = pymysql.connect(**MYSQL)
mc = my.cursor()

def safe(v):
    return v if v is not None else None

print("=" * 60)
print("  SQLite → MySQL migration")
print("=" * 60)

# ── 1. PERSONS ────────────────────────────────────────────────
sc.execute("SELECT * FROM persons")
persons = sc.fetchall()
ins = skip = 0
for p in persons:
    mc.execute("SELECT id FROM 3c_eng_persons WHERE id=%s", (p["id"],))
    if mc.fetchone():
        skip += 1
        continue
    try:
        mc.execute("""
            INSERT INTO 3c_eng_persons
                (id, name, watchlist, company, photo_b64, photo_url,
                 train_folder, training_images_b64, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            p["id"], p["name"], p.get("watchlist","employee"),
            p.get("company"), p.get("photo_b64"), p.get("photo_url"),
            p.get("train_folder"), p.get("training_images_b64"),
            p.get("created_at", datetime.now().isoformat())
        ))
        ins += 1
    except Exception as e:
        print(f"  [WARN] person id={p['id']}: {e}")
my.commit()
print(f"[persons]         inserted={ins}  skipped={skip}")

# ── 2. CAMERAS ────────────────────────────────────────────────
sc.execute("SELECT * FROM cameras")
cameras = sc.fetchall()
ins = skip = 0
for c in cameras:
    mc.execute("SELECT id FROM 3c_eng_cameras WHERE id=%s", (c["id"],))
    if mc.fetchone():
        skip += 1
        continue
    try:
        mc.execute("""
            INSERT INTO 3c_eng_cameras
                (id, name, rtsp_url, camera_type, fps, enabled, notes,
                 face_confidence, detection_range, min_yaw, max_yaw,
                 min_pitch, max_pitch, detection_zone, send_image,
                 data_frequency, room_id, map_x, map_y,
                 entry_zone, exit_zone, count_line, count_inside_pt, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            c["id"], c["name"], c["rtsp_url"],
            c.get("camera_type","checkin"), c.get("fps",30),
            bool(c.get("enabled",1)), c.get("notes",""),
            c.get("face_confidence",0.6), c.get("detection_range",6.5),
            c.get("min_yaw",-35), c.get("max_yaw",35),
            c.get("min_pitch",-15), c.get("max_pitch",15),
            c.get("detection_zone","[]"), bool(c.get("send_image",1)),
            c.get("data_frequency",2), c.get("room_id"),
            c.get("map_x"), c.get("map_y"),
            c.get("entry_zone"), c.get("exit_zone"),
            c.get("count_line"), c.get("count_inside_pt"),
            c.get("created_at", datetime.now().isoformat())
        ))
        ins += 1
    except Exception as e:
        print(f"  [WARN] camera id={c['id']}: {e}")
my.commit()
print(f"[cameras]         inserted={ins}  skipped={skip}")

# ── 3. EVENTS ─────────────────────────────────────────────────
sc.execute("SELECT * FROM events ORDER BY id")
events = sc.fetchall()
ins = skip = 0
for e in events:
    # check by event_id or timestamp+camera_id combo
    mc.execute("""
        SELECT id FROM 3c_eng_events
        WHERE camera_id=%s AND person_name=%s AND timestamp=%s
        LIMIT 1
    """, (e.get("camera_id"), e.get("person_name","Unknown"), e.get("timestamp","")))
    if mc.fetchone():
        skip += 1
        continue
    try:
        now_iso = datetime.now().isoformat()
        mc.execute("""
            INSERT INTO 3c_eng_events
                (event_id, camera_id, person_id, entity_id, person_name,
                 person_type, confidence, matched, suspected,
                 bbox, timestamp, snapshot_b64, synced_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            e.get("snapshot_path", f"sqlite_{e['id']}"),
            e.get("camera_id"), e.get("person_id"), None,
            e.get("person_name","Unknown"),
            e.get("person_type","unknown"),
            e.get("confidence", 0.0),
            bool(e.get("matched", False)),
            bool(e.get("suspected", False)),
            e.get("bbox","[]"),
            e.get("timestamp", now_iso),
            e.get("snapshot_b64"),
            now_iso
        ))
        ins += 1
    except Exception as ex:
        print(f"  [WARN] event id={e['id']}: {str(ex)[:60]}")
my.commit()
print(f"[events]          inserted={ins}  skipped={skip}")

# ── 4. ATTENDANCE ─────────────────────────────────────────────
sc.execute("SELECT * FROM attendance ORDER BY id")
atts = sc.fetchall()
ins = skip = 0
for a in atts:
    mc.execute("""
        SELECT id FROM 3c_eng_attendance
        WHERE person_id=%s AND date=%s AND checkin_time=%s
        LIMIT 1
    """, (a.get("person_id"), a.get("date",""), a.get("checkin_time","")))
    if mc.fetchone():
        skip += 1
        continue
    try:
        mc.execute("""
            INSERT INTO 3c_eng_attendance
                (person_id, person_name, camera_id, checkin_time,
                 checkout_time, duration_min, duration_str, status,
                 snapshot_b64, snapshot_path, date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            a.get("person_id"), a.get("person_name"),
            a.get("camera_id"), a.get("checkin_time"),
            a.get("checkout_time"), a.get("duration_min"),
            a.get("duration_str"), a.get("status","checked_in"),
            a.get("snapshot_b64"), a.get("snapshot_path"),
            a.get("date")
        ))
        ins += 1
    except Exception as ex:
        print(f"  [WARN] attendance id={a['id']}: {str(ex)[:60]}")
my.commit()
print(f"[attendance]      inserted={ins}  skipped={skip}")

# ── 5. ALERTS ─────────────────────────────────────────────────
sc.execute("SELECT * FROM alerts ORDER BY id")
alerts = sc.fetchall()
ins = skip = 0
for al in alerts:
    mc.execute("""
        SELECT id FROM 3c_eng_alerts
        WHERE type=%s AND created_at=%s
        LIMIT 1
    """, (al.get("type"), al.get("created_at","")))
    if mc.fetchone():
        skip += 1
        continue
    try:
        mc.execute("""
            INSERT INTO 3c_eng_alerts
                (type, severity, message, person_id, acknowledged, created_at)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            al.get("type"), al.get("severity","low"),
            al.get("message"), al.get("person_id"),
            bool(al.get("acknowledged", False)),
            al.get("created_at", datetime.now().isoformat())
        ))
        ins += 1
    except Exception as ex:
        print(f"  [WARN] alert: {str(ex)[:60]}")
my.commit()
print(f"[alerts]          inserted={ins}  skipped={skip}")

# ── 6. UNKNOWN PERSONS ────────────────────────────────────────
sc.execute("SELECT * FROM unknown_persons ORDER BY id")
unknowns = sc.fetchall()
ins = skip = 0
for u in unknowns:
    mc.execute("""
        SELECT id FROM 3c_eng_unknown_persons
        WHERE tracking_id=%s LIMIT 1
    """, (u.get("tracking_id",""),))
    if mc.fetchone():
        skip += 1
        continue
    try:
        mc.execute("""
            INSERT INTO 3c_eng_unknown_persons
                (tracking_id, first_seen, last_seen, camera_ids, snapshots,
                 snapshot_b64s, event_count, embedding, resolved,
                 resolved_action, resolved_at, enrolled_as,
                 enrolled_count, person_id, date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            u.get("tracking_id"), u.get("first_seen"), u.get("last_seen"),
            u.get("camera_ids","[]"), u.get("snapshots","[]"),
            u.get("snapshot_b64s","[]"), u.get("event_count",1),
            u.get("embedding"), bool(u.get("resolved",False)),
            u.get("resolved_action"), u.get("resolved_at"),
            u.get("enrolled_as"), u.get("enrolled_count"),
            u.get("person_id"), u.get("date")
        ))
        ins += 1
    except Exception as ex:
        print(f"  [WARN] unknown: {str(ex)[:60]}")
my.commit()
print(f"[unknown_persons] inserted={ins}  skipped={skip}")

# ── 7. SYSTEM SETTINGS ────────────────────────────────────────
sc.execute("SELECT key, value FROM system_settings")
settings = sc.fetchall()
ins = skip = 0
for s in settings:
    k = s.get("key") or s.get("key_name") or list(s.values())[0]
    v = s.get("value") or list(s.values())[1]
    mc.execute("SELECT key_name FROM 3c_eng_settings WHERE key_name=%s", (k,))
    if mc.fetchone():
        mc.execute("UPDATE 3c_eng_settings SET value=%s WHERE key_name=%s", (v, k))
        skip += 1
    else:
        mc.execute("INSERT INTO 3c_eng_settings (key_name, value) VALUES (%s,%s)", (k, v))
        ins += 1
my.commit()
print(f"[settings]        inserted={ins}  updated={skip}")

# ── 8. THREE_C_ENG_MAPPING ───────────────────────────────────
sc.execute("SELECT * FROM three_c_eng_mapping")
mappings = sc.fetchall()
ins = skip = 0
for m in mappings:
    mc.execute("SELECT entity_id FROM 3c_eng_entity_mapping WHERE entity_id=%s", (m["entity_id"],))
    if mc.fetchone():
        skip += 1
        continue
    try:
        mc.execute("""
            INSERT INTO 3c_eng_entity_mapping
                (entity_id, full_name, first_name, last_name,
                 person_id, our_name, company, match_method, mapped_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            m["entity_id"], m.get("full_name"), m.get("first_name"),
            m.get("last_name"), m.get("person_id"), m.get("our_name"),
            m.get("company"), m.get("match_method","manual"),
            m.get("mapped_at", datetime.now().isoformat())
        ))
        ins += 1
    except Exception as ex:
        print(f"  [WARN] mapping: {str(ex)[:60]}")
my.commit()
print(f"[entity_mapping]  inserted={ins}  skipped={skip}")

# ── Summary ───────────────────────────────────────────────────
mc.execute("SELECT COUNT(*) FROM 3c_eng_persons"); print(f"\nMySQL 3c_eng_persons   : {mc.fetchone()[0]}")
mc.execute("SELECT COUNT(*) FROM 3c_eng_cameras"); print(f"MySQL 3c_eng_cameras   : {mc.fetchone()[0]}")
mc.execute("SELECT COUNT(*) FROM 3c_eng_events");  print(f"MySQL 3c_eng_events    : {mc.fetchone()[0]}")
mc.execute("SELECT COUNT(*) FROM 3c_eng_attendance"); print(f"MySQL 3c_eng_attendance: {mc.fetchone()[0]}")
mc.execute("SELECT COUNT(*) FROM 3c_eng_alerts");  print(f"MySQL 3c_eng_alerts    : {mc.fetchone()[0]}")
mc.execute("SELECT COUNT(*) FROM 3c_eng_unknown_persons"); print(f"MySQL 3c_eng_unknowns  : {mc.fetchone()[0]}")
mc.execute("SELECT COUNT(*) FROM 3c_eng_settings"); print(f"MySQL 3c_eng_settings  : {mc.fetchone()[0]}")
mc.execute("SELECT COUNT(*) FROM 3c_eng_entity_mapping"); print(f"MySQL entity_mapping   : {mc.fetchone()[0]}")

my.close(); sq.close()
print("\n[DONE] Migration complete — MySQL is now the primary DB")

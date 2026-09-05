"""Migrate remaining tables: alerts, unknown_persons, settings, entity_mapping"""
import sqlite3, pymysql
from datetime import datetime

SQLITE_DB = r"data\frs.db"
MYSQL = dict(host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10)

sq = sqlite3.connect(SQLITE_DB)
sq.row_factory = lambda cur, row: {col[0]: row[idx] for idx, col in enumerate(cur.description)}
sc = sq.cursor()
my = pymysql.connect(**MYSQL)
mc = my.cursor()

# ── ALERTS (bulk insert) ──────────────────────────────────────
mc.execute("SELECT COUNT(*) FROM 3c_eng_alerts"); existing = mc.fetchone()[0]
sc.execute("SELECT * FROM alerts ORDER BY id")
alerts = sc.fetchall()
print(f"Alerts: SQLite={len(alerts)}, MySQL already={existing}")
new_alerts = []
for al in alerts:
    new_alerts.append((
        al.get("type"), al.get("severity","low"),
        al.get("message"), al.get("person_id"),
        bool(al.get("acknowledged", False)),
        al.get("created_at", datetime.now().isoformat())
    ))
# Bulk insert — fast
if new_alerts:
    try:
        mc.executemany("""
            INSERT IGNORE INTO 3c_eng_alerts
                (type, severity, message, person_id, acknowledged, created_at)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, new_alerts)
        my.commit()
        print(f"  Alerts inserted: {mc.rowcount}")
    except Exception as e:
        print(f"  Alerts error: {e}")

# ── UNKNOWN PERSONS ───────────────────────────────────────────
sc.execute("SELECT * FROM unknown_persons ORDER BY id")
unknowns = sc.fetchall()
ins = skip = 0
for u in unknowns:
    mc.execute("SELECT id FROM 3c_eng_unknown_persons WHERE tracking_id=%s LIMIT 1", (u.get("tracking_id",""),))
    if mc.fetchone(): skip += 1; continue
    try:
        mc.execute("""INSERT INTO 3c_eng_unknown_persons
            (tracking_id,first_seen,last_seen,camera_ids,snapshots,
             snapshot_b64s,event_count,embedding,resolved,
             resolved_action,resolved_at,enrolled_as,enrolled_count,person_id,date)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (u.get("tracking_id"),u.get("first_seen"),u.get("last_seen"),
             u.get("camera_ids","[]"),u.get("snapshots","[]"),
             u.get("snapshot_b64s","[]"),u.get("event_count",1),
             u.get("embedding"),bool(u.get("resolved",False)),
             u.get("resolved_action"),u.get("resolved_at"),
             u.get("enrolled_as"),u.get("enrolled_count"),
             u.get("person_id"),u.get("date")))
        ins += 1
    except Exception as e:
        print(f"  [WARN] unknown: {str(e)[:60]}")
my.commit()
print(f"[unknown_persons] inserted={ins}  skipped={skip}")

# ── SETTINGS ─────────────────────────────────────────────────
try:
    sc.execute("SELECT * FROM system_settings")
    settings = sc.fetchall()
    ins = skip = 0
    for s in settings:
        k = s.get("key") or s.get("key_name")
        v = s.get("value")
        if not k: continue
        mc.execute("SELECT key_name FROM 3c_eng_settings WHERE key_name=%s", (k,))
        if mc.fetchone():
            mc.execute("UPDATE 3c_eng_settings SET value=%s WHERE key_name=%s", (v, k))
            skip += 1
        else:
            mc.execute("INSERT INTO 3c_eng_settings (key_name,value) VALUES (%s,%s)", (k, v))
            ins += 1
    my.commit()
    print(f"[settings]        inserted={ins}  updated={skip}")
except Exception as e:
    print(f"[settings] error: {e}")

# ── ENTITY MAPPING ────────────────────────────────────────────
try:
    sc.execute("SELECT * FROM three_c_eng_mapping")
    mappings = sc.fetchall()
    ins = skip = 0
    for m in mappings:
        mc.execute("SELECT entity_id FROM 3c_eng_entity_mapping WHERE entity_id=%s", (m.get("entity_id"),))
        if mc.fetchone(): skip += 1; continue
        try:
            mc.execute("""INSERT INTO 3c_eng_entity_mapping
                (entity_id,full_name,first_name,last_name,
                 person_id,our_name,company,match_method,mapped_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (m.get("entity_id"),m.get("full_name"),m.get("first_name"),
                 m.get("last_name"),m.get("person_id"),m.get("our_name"),
                 m.get("company"),m.get("match_method","manual"),
                 m.get("mapped_at",datetime.now().isoformat())))
            ins += 1
        except Exception as e:
            print(f"  [WARN] mapping: {str(e)[:60]}")
    my.commit()
    print(f"[entity_mapping]  inserted={ins}  skipped={skip}")
except Exception as e:
    print(f"[entity_mapping] error: {e}")

# ── Final counts ──────────────────────────────────────────────
print()
for tbl in ["3c_eng_persons","3c_eng_cameras","3c_eng_events","3c_eng_attendance",
            "3c_eng_alerts","3c_eng_unknown_persons","3c_eng_settings","3c_eng_entity_mapping"]:
    mc.execute(f"SELECT COUNT(*) FROM `{tbl}`")
    print(f"  {tbl:<30} : {mc.fetchone()[0]}")

my.close(); sq.close()
print("\n[DONE] Migration complete")

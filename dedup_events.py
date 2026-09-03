"""
dedup_events.py
───────────────
Removes duplicate events from 3c_eng_events.
A duplicate = same person_id + same camera_id within 30 seconds.
Keeps the row with the highest confidence, deletes the rest.
"""
import pymysql
from datetime import datetime

MYSQL = dict(
    host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10
)

conn = pymysql.connect(**MYSQL)
cur  = conn.cursor()

today = datetime.now().strftime("%Y-%m-%d")

# ── 1. Show current state ──────────────────────────────────────
cur.execute("SELECT COUNT(*) FROM 3c_eng_events WHERE timestamp LIKE %s", (f"{today}%",))
total_before = cur.fetchone()[0]
print(f"Today's events BEFORE cleanup: {total_before}")

# ── 2. Find duplicates ────────────────────────────────────────
# Duplicate = same person_id + camera_id + timestamp within 30 seconds
# Strategy: for each group keep the row with MAX confidence (or lowest id if tie)
# Delete all others in the group.

cur.execute("""
    SELECT
        person_id,
        camera_id,
        LEFT(timestamp, 16) AS minute_bucket,
        COUNT(*) AS cnt,
        GROUP_CONCAT(id ORDER BY confidence DESC, id ASC) AS ids
    FROM 3c_eng_events
    WHERE timestamp LIKE %s
    GROUP BY person_id, camera_id, minute_bucket
    HAVING COUNT(*) > 1
""", (f"{today}%",))

dup_groups = cur.fetchall()
print(f"Duplicate groups found: {len(dup_groups)}")

ids_to_delete = []
for pid, cam, minute, cnt, ids_str in dup_groups:
    id_list = [int(x) for x in ids_str.split(",")]
    # Keep the first one (highest confidence), delete the rest
    keep = id_list[0]
    delete = id_list[1:]
    ids_to_delete.extend(delete)
    print(f"  person={pid} cam={cam} time={minute} | keep={keep} delete={delete}")

print(f"\nTotal rows to delete: {len(ids_to_delete)}")

if not ids_to_delete:
    print("No duplicates found — nothing to delete.")
    conn.close()
    exit(0)

# ── 3. Delete duplicates ──────────────────────────────────────
BATCH = 100
deleted = 0
for i in range(0, len(ids_to_delete), BATCH):
    batch = ids_to_delete[i:i+BATCH]
    placeholders = ",".join(["%s"] * len(batch))
    cur.execute(f"DELETE FROM 3c_eng_events WHERE id IN ({placeholders})", batch)
    deleted += cur.rowcount

conn.commit()

# ── 4. Final count ────────────────────────────────────────────
cur.execute("SELECT COUNT(*) FROM 3c_eng_events WHERE timestamp LIKE %s", (f"{today}%",))
total_after = cur.fetchone()[0]

conn.close()

print(f"\n{'='*50}")
print(f"  Events before : {total_before}")
print(f"  Deleted       : {deleted}")
print(f"  Events after  : {total_after}")
print(f"  Duplicates removed: {total_before - total_after}")
print(f"{'='*50}")

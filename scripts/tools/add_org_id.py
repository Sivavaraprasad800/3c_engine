"""
add_org_id.py — Adds org_id column to all 3c_eng_* tables.

What it does:
- Adds ONE new column: org_id VARCHAR(100) DEFAULT 'default'
- Adds indexes for query performance
- Does NOT change, delete or touch any existing columns or data
- Safe to run multiple times (skips if already done)

Run: python scripts/tools/add_org_id.py
"""
import os
from pathlib import Path

# Load .env
env_file = Path(__file__).parent.parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import pymysql

conn = pymysql.connect(
    host=os.environ["DB_HOST"],
    port=int(os.environ.get("DB_PORT", 3306)),
    user=os.environ["DB_USER"],
    password=os.environ.get("DB_PASSWORD") or os.environ.get("DB_PASS", ""),
    database=os.environ["DB_NAME"],
    charset="utf8mb4",
    ssl_disabled=True,
)
cur = conn.cursor()

# Step 1: Add org_id column to each 3c_eng_* table
tables = [
    "3c_eng_persons",
    "3c_eng_cameras",
    "3c_eng_events",
    "3c_eng_attendance",
    "3c_eng_unknown_persons",
    "3c_eng_settings",
    "3c_eng_face_embeddings",
    "3c_eng_ks_map",
    "3c_eng_entity_mapping",
    "3c_eng_kloudspot_events",
    "3c_eng_room_movements",
    "3c_eng_room_headcount",
    "3c_eng_room_occupancy",
]

print("Adding org_id column to 3c_eng_* tables...")
for t in tables:
    try:
        cur.execute(f"ALTER TABLE `{t}` ADD COLUMN org_id VARCHAR(100) NOT NULL DEFAULT 'default'")
        conn.commit()
        print(f"  ✓  {t}  — org_id added")
    except Exception as e:
        if "Duplicate column" in str(e) or "already exists" in str(e):
            print(f"  –  {t}  — already has org_id (skipped)")
        else:
            print(f"  ✗  {t}  — {e}")

# Step 2: Add indexes for fast filtering
print("\nAdding indexes...")
indexes = [
    ("3c_eng_persons",         "idx_persons_org"),
    ("3c_eng_cameras",         "idx_cameras_org"),
    ("3c_eng_events",          "idx_events_org"),
    ("3c_eng_attendance",      "idx_att_org"),
    ("3c_eng_unknown_persons", "idx_unk_org"),
    ("3c_eng_face_embeddings", "idx_embeddings_org"),
]
for table, idx_name in indexes:
    try:
        cur.execute(f"CREATE INDEX `{idx_name}` ON `{table}` (org_id)")
        conn.commit()
        print(f"  ✓  {idx_name}")
    except Exception as e:
        print(f"  –  {idx_name} (skipped: {str(e)[:50]})")

cur.close()
conn.close()

print("""
Done!

What was added:
  - org_id column (VARCHAR 100, default 'default') to 13 tables
  - Indexes on org_id for fast per-tenant queries

What was NOT changed:
  - No existing columns modified
  - No existing data changed
  - No tables dropped or renamed

Next step:
  - Set ORG_ID=your_org_name in .env for each client site
  - Restart the server
""")

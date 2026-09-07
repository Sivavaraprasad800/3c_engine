"""
add_org_id_prod.py — PRODUCTION DB: Add org_id column ONLY.

SAFE operations only:
  - ALTER TABLE ... ADD COLUMN org_id VARCHAR(100) NOT NULL DEFAULT 'default'
  - No data deleted
  - No data modified
  - No tables dropped
  - Skips silently if column already exists
"""
import pymysql

conn = pymysql.connect(
    host     = "zdotbox.c7mkuyk28a42.ap-south-1.rds.amazonaws.com",
    port     = 3306,
    user     = "zdotbox",
    password = "5fi7p1QDYRnX7TzKe6Py",
    database = "3C_Z_ATTEND_AI",
    charset  = "utf8mb4",
    connect_timeout = 10,
)
cur = conn.cursor()

tables = [
    "3c_eng_persons",
    "3c_eng_cameras",
    "3c_eng_events",
    "3c_eng_attendance",
    "3c_eng_unknown_persons",
    "3c_eng_settings",
    "3c_eng_face_embeddings",
]

print("Adding org_id column to production 3c_eng_* tables...")
print("(Safe: no data changed, no tables dropped)")
print()

for t in tables:
    try:
        cur.execute(f"ALTER TABLE `{t}` ADD COLUMN org_id VARCHAR(100) NOT NULL DEFAULT 'default'")
        conn.commit()
        print(f"  ✓  {t}  — org_id added")
    except Exception as e:
        msg = str(e)
        if "Duplicate column" in msg or "already exists" in msg:
            print(f"  –  {t}  — already has org_id (skipped)")
        else:
            print(f"  ✗  {t}  — ERROR: {msg}")

cur.close()
conn.close()
print()
print("Complete. No data was modified.")

"""
backfill_org_id.py — Update all existing rows from org_id='default' to 'zdotbox'.
Run ONCE after first deployment. Safe — only UPDATE WHERE org_id='default'.
"""
import pymysql

conn = pymysql.connect(
    host="zdotbox.c7mkuyk28a42.ap-south-1.rds.amazonaws.com",
    port=3306, user="zdotbox", password="5fi7p1QDYRnX7TzKe6Py",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10,
)
cur = conn.cursor()

ORG = "zdotbox"
tables = [
    "3c_eng_persons",
    "3c_eng_cameras",
    "3c_eng_events",
    "3c_eng_attendance",
    "3c_eng_unknown_persons",
    "3c_eng_settings",
    "3c_eng_face_embeddings",
]
print(f"Backfilling org_id='default' → '{ORG}' in production tables...")
total = 0
for t in tables:
    cur.execute(f"UPDATE `{t}` SET org_id=%s WHERE org_id='default'", (ORG,))
    conn.commit()
    print(f"  ✓  {t}: {cur.rowcount} rows updated")
    total += cur.rowcount

cur.close()
conn.close()
print(f"\nTotal: {total} rows updated. Done.")

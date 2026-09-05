"""Fix system settings: dedup_seconds too high, suspected_threshold wrong."""
import os, pymysql
from pathlib import Path
for line in open(str(Path(__file__).parent/".env"),encoding="utf-8-sig"):
    l=line.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip())

conn=pymysql.connect(host=os.environ.get("DB_HOST",""),
    port=int(os.environ.get("DB_PORT","3306")),
    user=os.environ.get("DB_USER",""),
    password=os.environ.get("DB_PASS",os.environ.get("DB_PASSWORD","")),
    database=os.environ.get("DB_NAME",""),
    charset="utf8mb4",connect_timeout=15)
cur=conn.cursor()

print("Current settings:")
cur.execute("SELECT key_name, value FROM 3c_eng_settings")
for k,v in cur.fetchall():
    print(f"  {k}: {v}")

# Fix suspected_threshold back to 0.37 (0.45 was too high, missing many matches)
# Fix dedup_seconds to 5 (120s was blocking re-entries)
fixes = [
    ("suspected_threshold", "0.37"),  # lower = catch more suspected matches (was 0.45)
    ("dedup_seconds", "5"),           # 5s = allow quick re-entry (was 120s)
    ("known_suppress_seconds", "5"),  # 5s = don't suppress known person for 2 min (was 120s)
    ("camera_unknown_cooldown", "5"), # 5s = allow unknowns quickly (was 15s)
]

for key, val in fixes:
    cur.execute("""
        INSERT INTO 3c_eng_settings (key_name, value) VALUES (%s,%s)
        ON DUPLICATE KEY UPDATE value=%s
    """, (key, val, val))
    print(f"  SET {key} = {val}")

conn.commit()
conn.close()
print("Done — restart server to apply")

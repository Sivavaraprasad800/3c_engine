"""Check camera config and what threshold causes rejection."""
import os, sys, io, pymysql
from pathlib import Path
if hasattr(sys.stdout,'buffer'):
    sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
os.chdir(str(Path(__file__).parent))
for line in open(".env",encoding="utf-8-sig"):
    l=line.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip())
DB_HOST=os.environ.get("DB_HOST",""); DB_PORT=int(os.environ.get("DB_PORT","3306"))
DB_USER=os.environ.get("DB_USER",""); DB_PASS=os.environ.get("DB_PASS",os.environ.get("DB_PASSWORD",""))
DB_NAME=os.environ.get("DB_NAME","")

conn=pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USER,
    password=DB_PASS,database=DB_NAME,charset="utf8mb4",connect_timeout=15)
cur=conn.cursor()

print("=== Camera configs (face_confidence, yaw, detection_zone) ===")
cur.execute("SELECT id, name, face_confidence, min_yaw, max_yaw, min_pitch, max_pitch, detection_zone FROM 3c_eng_cameras ORDER BY id")
for r in cur.fetchall():
    cid,nm,fc,miny,maxy,minp,maxp,zone = r
    zone_pts = len(eval(zone)) if zone and zone.strip() not in ('[]','null','') else 0
    print(f"  {str(cid):<22} face_conf={fc}  yaw=[{miny},{maxy}]  pitch=[{minp},{maxp}]  zone_pts={zone_pts}")

print("\n=== System settings ===")
cur.execute("SELECT key_name, value FROM 3c_eng_settings WHERE key_name IN ('face_threshold','suspected_threshold','dedup_seconds')")
for k,v in cur.fetchall():
    print(f"  {k}: {v}")

conn.close()

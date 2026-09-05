"""
download_all_images.py — Downloads ALL person face images from S3
"""

import os, sys, io, json, urllib.request
import pymysql
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_dir = Path(__file__).parent
os.chdir(str(_dir))
for line in open(str(_dir / ".env"), encoding="utf-8-sig"):
    l=line.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip())

DB_HOST=os.environ.get("DB_HOST",""); DB_PORT=int(os.environ.get("DB_PORT","3306"))
DB_USER=os.environ.get("DB_USER",""); DB_PASS=os.environ.get("DB_PASS",os.environ.get("DB_PASSWORD",""))
DB_NAME=os.environ.get("DB_NAME","")

SAVE_DIR = Path("C:/Users/siva/Downloads/all_person_images")
SAVE_DIR.mkdir(exist_ok=True)
S3_BASE  = "https://3c-bucket.s3.ap-south-1.amazonaws.com"

print("="*60)
print("  DOWNLOADING ALL PERSON IMAGES FROM S3")
print(f"  Saving to: {SAVE_DIR}")
print("="*60)

conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
    password=DB_PASS, database=DB_NAME,
    charset="utf8mb4", connect_timeout=15)
cur  = conn.cursor()

total_persons = 0
total_images  = 0
total_failed  = 0

for tbl in ["zdotapps_user_master", "factops_user_master"]:
    cur.execute(f"""
        SELECT org_issued_id, first_name, last_name, email_id,
               entity_id, employment_status, face_image_paths
        FROM `{tbl}`
        WHERE face_image_paths IS NOT NULL
          AND face_image_paths != '[]'
          AND face_image_paths != 'null'
        ORDER BY first_name, last_name
    """)
    rows = cur.fetchall()
    print(f"\n[{tbl}] Persons with images: {len(rows)}")

    for org_id, fn, ln, email, entity_id, status, face_paths in rows:
        full_name = f"{fn or ''} {ln or ''}".strip()
        if not full_name:
            continue

        # Parse image paths
        try:
            paths = json.loads(face_paths) if face_paths else []
        except Exception:
            paths = []
        if not paths:
            continue

        # Create folder
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in full_name)
        person_dir = SAVE_DIR / f"{org_id}_{safe}"
        person_dir.mkdir(exist_ok=True)

        # Save info file
        info_file = person_dir / "info.txt"
        info_file.write_text(
            f"Name       : {full_name}\n"
            f"OrgID      : {org_id}\n"
            f"Email      : {email or ''}\n"
            f"EntityID   : {entity_id or ''}\n"
            f"Status     : {status or ''}\n"
            f"Table      : {tbl}\n"
            f"Images     : {len(paths)}\n",
            encoding="utf-8"
        )

        # Download images
        downloaded = 0
        for i, url in enumerate(paths[:8]):
            if not url.startswith("http"):
                url = f"{S3_BASE}/{url}"
            fname = person_dir / f"face_{i+1}.jpg"
            if fname.exists():
                downloaded += 1
                continue
            try:
                urllib.request.urlretrieve(url, str(fname))
                size = fname.stat().st_size
                if size < 1000:  # too small = error page
                    fname.unlink()
                    print(f"  BAD:  {full_name} image {i+1} too small ({size} bytes) — deleted")
                else:
                    downloaded += 1
                    total_images += 1
            except Exception as e:
                total_failed += 1
                print(f"  FAIL: {full_name} image {i+1}: {url[:60]}  ({e})")

        if downloaded > 0:
            total_persons += 1
            print(f"  {full_name:<30} {downloaded} images  [{org_id}]  entity={entity_id or '—'}")
        else:
            print(f"  {full_name:<30} NO images downloaded")

conn.close()

print(f"\n{'='*60}")
print(f"  DOWNLOAD COMPLETE")
print(f"{'='*60}")
print(f"  Persons with images : {total_persons}")
print(f"  Total images saved  : {total_images}")
print(f"  Failed downloads    : {total_failed}")
print(f"  Saved to            : {SAVE_DIR}")
print("="*60)

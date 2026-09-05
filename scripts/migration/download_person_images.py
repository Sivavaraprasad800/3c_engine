"""
Check Gouthamram P and Ganesh Reddy in zdotapps + factops user_master
Download their face images from S3 if available
Enroll them into FAISS
"""
import pymysql, json, os, urllib.request
from pathlib import Path

DOWNLOAD_DIR = Path(r"C:\Users\siva\Downloads\enroll_images")
DOWNLOAD_DIR.mkdir(exist_ok=True)

conn = pymysql.connect(
    host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10
)
cur = conn.cursor()

search_names = [
    ("Gouthamram", "gouthamram"),
    ("Ganesh Reddy", "ganesh.reddy"),
]

results = []

for display_name, search_key in search_names:
    print(f"\n{'='*60}")
    print(f"Searching for: {display_name}")
    print(f"{'='*60}")

    found = False

    # Check zdotapps_user_master
    for tbl in ["zdotapps_user_master", "factops_user_master"]:
        cur.execute(f"""
            SELECT org_issued_id, first_name, last_name, email_id,
                   entity_id, employment_status, face_image_paths
            FROM `{tbl}`
            WHERE first_name LIKE %s OR last_name LIKE %s
               OR email_id LIKE %s OR CONCAT(first_name,' ',last_name) LIKE %s
        """, (f"%{display_name.split()[0]}%", f"%{display_name.split()[-1]}%",
              f"%{search_key}%", f"%{display_name}%"))
        rows = cur.fetchall()
        for row in rows:
            org_id, fn, ln, email, eid, status, face_paths = row
            full_name = f"{fn} {ln}".strip()
            print(f"\n  [{tbl}]")
            print(f"  Name       : {full_name}")
            print(f"  Email      : {email}")
            print(f"  org_id     : {org_id}")
            print(f"  entity_id  : {eid}")
            print(f"  status     : {status}")

            # Parse face image paths
            try:
                paths = json.loads(face_paths) if face_paths else []
            except Exception:
                paths = []

            print(f"  Images     : {len(paths)}")

            downloaded = []
            person_dir = DOWNLOAD_DIR / f"{org_id}_{full_name.replace(' ','_')}"
            person_dir.mkdir(exist_ok=True)

            for i, url in enumerate(paths):
                # Build full S3 URL if needed
                if url.startswith("http"):
                    full_url = url
                else:
                    full_url = f"https://3c-bucket.s3.ap-south-1.amazonaws.com/{url}"

                fname = person_dir / f"face_{i+1}.jpg"
                try:
                    urllib.request.urlretrieve(full_url, str(fname))
                    size = fname.stat().st_size
                    print(f"    Downloaded: {fname.name}  ({size} bytes)")
                    downloaded.append(str(fname))
                except Exception as e:
                    print(f"    FAILED: {full_url} — {e}")

            results.append({
                "name": full_name,
                "org_id": org_id,
                "entity_id": eid,
                "table": tbl,
                "images": downloaded,
            })
            found = True

    if not found:
        print(f"  NOT FOUND in any user master table")

conn.close()

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
for r in results:
    print(f"  {r['name']:<25} [{r['table']}]  images={len(r['images'])}  entity={r['entity_id']}")

print(f"\nImages saved to: {DOWNLOAD_DIR}")
print(f"\nTotal persons found: {len(results)}")

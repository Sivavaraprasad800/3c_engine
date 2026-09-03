"""
Enroll Gouthamram P and Ganesh Reddy from downloaded images.
Skips Ganesh Allada.
"""
import cv2
import json
from pathlib import Path
from datetime import datetime
import pymysql
from face_engine import FaceRecognitionEngine

engine = FaceRecognitionEngine()

DOWNLOAD_DIR = Path(r"C:\Users\siva\Downloads\enroll_images")

MYSQL = dict(
    host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10
)

# Persons to enroll — (folder_prefix, name, entity_id, our_person_id)
ENROLL = [
    {
        "folder":    "1932500_Gouthamram_P",
        "name":      "Gouthamram P",
        "entity_id": "6a83f9edc7597a3c16e6432b",
        "person_id": 122,   # already in 3c_eng_persons
    },
    {
        "folder":    "1780611_Ganesh_Reddy",
        "name":      "Ganesh Reddy",
        "entity_id": "6a05aa42ce374523606ecdac",
        "person_id": 25,    # already in 3c_eng_persons
    },
]

conn = pymysql.connect(**MYSQL)
mc = conn.cursor()

for p in ENROLL:
    folder = DOWNLOAD_DIR / p["folder"]
    imgs = sorted(folder.glob("face_*.jpg"))
    print(f"\n{'='*55}")
    print(f"Enrolling: {p['name']} (ID={p['person_id']})")
    print(f"Images found: {len(imgs)}")

    if not imgs:
        print("  No images found — skipping")
        continue

    # Remove existing embeddings first
    engine.employee_index.remove(p["person_id"])
    print(f"  Cleared old embeddings")

    enrolled = 0
    for img_path in imgs:
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  Cannot read {img_path.name}")
            continue
        result = engine.enroll(img, person_id=p["person_id"], name=p["name"], watchlist="employee")
        if result.get("success"):
            enrolled += 1
            print(f"  Enrolled {img_path.name} — total embeddings: {result.get('total_enrolled',0)}")
        elif result.get("note") == "duplicate_skipped":
            print(f"  {img_path.name} — duplicate skipped")
        else:
            print(f"  {img_path.name} — FAILED: {result.get('error','unknown')}")

    print(f"  Total enrolled: {enrolled} embeddings")

    # Update 3c_eng_persons — set photo from first image
    first_img = cv2.imread(str(imgs[0]))
    import base64
    _, buf = cv2.imencode(".jpg", first_img)
    b64 = base64.b64encode(buf.tobytes()).decode()

    mc.execute("""
        UPDATE 3c_eng_persons
        SET photo_b64=%s, entity_id=%s
        WHERE id=%s
    """, (b64, p["entity_id"], p["person_id"]))

    # Update entity mapping
    mc.execute("""
        INSERT INTO 3c_eng_entity_mapping
            (entity_id, full_name, person_id, our_name, match_method, mapped_at)
        VALUES (%s,%s,%s,%s,'manual',%s)
        ON DUPLICATE KEY UPDATE
            person_id=%s, our_name=%s, mapped_at=%s
    """, (p["entity_id"], p["name"], p["person_id"], p["name"],
          datetime.now().isoformat(),
          p["person_id"], p["name"], datetime.now().isoformat()))

    conn.commit()
    print(f"  DB updated: photo + entity_id set")

conn.close()

# Final FAISS stats
stats = engine.get_stats()
print(f"\n{'='*55}")
print(f"FAISS total embeddings : {stats['total_enrolled_embeddings']}")
print(f"Unique persons         : {stats['unique_persons']}")
print(f"\nDone — restart server to load new embeddings.")

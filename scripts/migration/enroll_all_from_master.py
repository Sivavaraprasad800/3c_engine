"""
enroll_all_from_master.py
─────────────────────────
For every person in zdotapps_user_master + factops_user_master:
  1. Download their face images from S3
  2. Check self-similarity — if avg >= 0.55 → enroll into FAISS
  3. If < 0.55 → skip (bad/inconsistent photos)

Only enrolls persons NOT already in FAISS (or updates if they have <5 embeddings).
"""

import cv2, numpy as np, pymysql, json, urllib.request, pickle, faiss
from pathlib import Path
from datetime import datetime
from face_engine import FaceRecognitionEngine

MIN_SELF_SIM = 0.55   # minimum average self-similarity to enroll
DOWNLOAD_DIR = Path(r"C:\Users\siva\Downloads\enroll_all_cache")
DOWNLOAD_DIR.mkdir(exist_ok=True)

engine = FaceRecognitionEngine()

# Load id_map to check who's already enrolled
id_map = engine.employee_index.id_map
already_enrolled_pids = set(v["person_id"] for v in id_map.values())
emb_count = {}
for v in id_map.values():
    emb_count[v["person_id"]] = emb_count.get(v["person_id"], 0) + 1

MYSQL = dict(
    host="zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com",
    port=3306, user="3c_dev_user", password="2H&5bQU2*)J)",
    database="3C_Z_ATTEND_AI", charset="utf8mb4", connect_timeout=10
)
conn = pymysql.connect(**MYSQL)
mc = conn.cursor()

# Load all our FRS persons
mc.execute("SELECT id, name FROM 3c_eng_persons WHERE watchlist='employee' OR watchlist IS NULL")
our_persons = {r[1].lower().strip(): r[0] for r in mc.fetchall()}
our_persons_by_id = {}
mc.execute("SELECT id, name FROM 3c_eng_persons")
for r in mc.fetchall():
    our_persons_by_id[r[0]] = r[1]

print(f"Our FRS persons: {len(our_persons)}")
print(f"Already in FAISS: {len(already_enrolled_pids)}")

stats = {"checked": 0, "enrolled": 0, "skipped_low_sim": 0,
         "skipped_no_face": 0, "skipped_no_images": 0, "already_good": 0}

def get_embedding(img):
    """Get normalized embedding from image, return None if no face."""
    faces = engine.app.get(img)
    if not faces:
        return None
    face = max(faces, key=lambda f: f.det_score)
    emb = face.embedding
    if emb is None:
        return None
    return emb / (np.linalg.norm(emb) + 1e-9)

def self_similarity(embeddings):
    """Average pairwise cosine similarity between embeddings."""
    if len(embeddings) < 2:
        return 1.0
    sims = []
    for i in range(len(embeddings)):
        for j in range(i+1, len(embeddings)):
            sims.append(float(np.dot(embeddings[i], embeddings[j])))
    return np.mean(sims)

def download_images(org_issued_id, name, face_image_paths, table):
    """Download face images from S3. Returns list of cv2 images."""
    try:
        paths = json.loads(face_image_paths) if face_image_paths else []
    except Exception:
        return []

    if not paths:
        return []

    safe_name = name.replace(" ", "_").replace("/", "_")
    person_dir = DOWNLOAD_DIR / f"{org_issued_id}_{safe_name}"
    person_dir.mkdir(exist_ok=True)

    images = []
    for i, url in enumerate(paths[:5]):
        if not url.startswith("http"):
            url = f"https://3c-bucket.s3.ap-south-1.amazonaws.com/{url}"
        fname = person_dir / f"face_{i+1}.jpg"
        try:
            if not fname.exists():
                urllib.request.urlretrieve(url, str(fname))
            img = cv2.imread(str(fname))
            if img is not None:
                images.append(img)
        except Exception:
            pass
    return images

# Process both tables
for tbl in ["zdotapps_user_master", "factops_user_master"]:
    mc.execute(f"""
        SELECT org_issued_id, first_name, last_name, email_id,
               entity_id, employment_status, face_image_paths
        FROM `{tbl}`
        WHERE employment_status='Active'
          AND face_image_paths IS NOT NULL
          AND face_image_paths != '[]'
          AND face_image_paths != 'null'
    """)
    rows = mc.fetchall()
    print(f"\n[{tbl}] Active persons with images: {len(rows)}")

    for row in rows:
        org_id, fn, ln, email, entity_id, status, face_paths = row
        full_name = f"{fn} {ln}".strip()
        stats["checked"] += 1

        # Find our person_id
        person_id = our_persons.get(full_name.lower().strip())
        if not person_id:
            # Try partial match
            for pname, pid in our_persons.items():
                if fn and fn.lower() in pname:
                    person_id = pid
                    break

        if not person_id:
            continue   # not in our system

        # Check if already well-enrolled (5 embeddings)
        current_count = emb_count.get(person_id, 0)
        if current_count >= 5:
            stats["already_good"] += 1
            continue   # already fully enrolled

        print(f"\n  Checking: {full_name} (ID={person_id}, current_embs={current_count})")

        # Download images
        imgs = download_images(org_id, full_name, face_paths, tbl)
        if not imgs:
            print(f"    No images downloadable — skip")
            stats["skipped_no_images"] += 1
            continue

        # Extract embeddings
        embeddings = []
        for img in imgs:
            emb = get_embedding(img)
            if emb is not None:
                embeddings.append(emb)

        if len(embeddings) < 2:
            print(f"    Only {len(embeddings)} detectable faces — skip")
            stats["skipped_no_face"] += 1
            continue

        # Self-similarity check
        avg_sim = self_similarity(embeddings)
        print(f"    Images: {len(imgs)}  Detectable: {len(embeddings)}  Self-sim: {avg_sim:.4f}", end="")

        if avg_sim < MIN_SELF_SIM:
            print(f"  ← SKIP (< {MIN_SELF_SIM})")
            stats["skipped_low_sim"] += 1
            continue

        print(f"  ← ENROLL ✓")

        # Remove old embeddings
        engine.employee_index.remove(person_id)

        # Enroll all good images
        enrolled = 0
        for img in imgs:
            result = engine.enroll(img, person_id=person_id,
                                   name=full_name, watchlist="employee")
            if result.get("success") or result.get("note") == "duplicate_skipped":
                enrolled += 1

        # Update photo in DB
        if imgs:
            import base64
            _, buf = cv2.imencode(".jpg", imgs[0])
            b64 = base64.b64encode(buf.tobytes()).decode()
            mc.execute("UPDATE 3c_eng_persons SET photo_b64=%s, entity_id=%s WHERE id=%s",
                       (b64, entity_id, person_id))

        conn.commit()
        stats["enrolled"] += 1
        print(f"    Enrolled {enrolled} embeddings for {full_name}")

conn.close()

final = engine.get_stats()
print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"  Persons checked       : {stats['checked']}")
print(f"  Already fully enrolled: {stats['already_good']}")
print(f"  Newly enrolled        : {stats['enrolled']}")
print(f"  Skipped (low sim<0.55): {stats['skipped_low_sim']}")
print(f"  Skipped (no face det) : {stats['skipped_no_face']}")
print(f"  Skipped (no images)   : {stats['skipped_no_images']}")
print(f"\n  FAISS total embeddings: {final['total_enrolled_embeddings']}")
print(f"  FAISS unique persons  : {final['unique_persons']}")
print(f"\nRestart server to load updated embeddings.")

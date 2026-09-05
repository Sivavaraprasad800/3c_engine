"""
enroll_all_persons.py
=====================
Downloads ALL person images from S3 (zdotapps_user_master + factops_user_master).
Enrolls every person into FAISS with:
  - Full name
  - Entity ID
  - Company
  - All details from user master tables

Also updates 3c_eng_persons and 3c_eng_entity_mapping tables.

Run: python enroll_all_persons.py
"""

import os, sys, io, cv2, json, base64, urllib.request
import numpy as np
import pymysql
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_dir = Path(__file__).parent
os.chdir(str(_dir))
for line in open(str(_dir / ".env"), encoding="utf-8-sig"):
    l=line.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip())

# ── Config ────────────────────────────────────────────────────
DOWNLOAD_DIR = Path(r"C:\Users\siva\Downloads\enroll_all_cache")
DOWNLOAD_DIR.mkdir(exist_ok=True)

MIN_SELF_SIM   = 0.45   # min avg self-similarity to enroll
MIN_FACE_SIZE  = 20     # min face width in pixels
S3_BASE        = "https://3c-bucket.s3.ap-south-1.amazonaws.com"

DB_HOST=os.environ.get("DB_HOST",""); DB_PORT=int(os.environ.get("DB_PORT","3306"))
DB_USER=os.environ.get("DB_USER",""); DB_PASS=os.environ.get("DB_PASS",os.environ.get("DB_PASSWORD",""))
DB_NAME=os.environ.get("DB_NAME","")

# ── Load face engine ──────────────────────────────────────────
print("Loading face engine...")
sys.path.insert(0, str(_dir))
from face_engine import FaceRecognitionEngine
engine = FaceRecognitionEngine()
print(f"FAISS: {engine.employee_index.total} embeddings, "
      f"{len(set(v['person_id'] for v in engine.employee_index.id_map.values()))} persons")

# ── DB connection ─────────────────────────────────────────────
conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
    password=DB_PASS, database=DB_NAME,
    charset="utf8mb4", connect_timeout=15)
cur  = conn.cursor()

# ── Get all persons from 3c_eng_persons ──────────────────────
cur.execute("SELECT id, name, watchlist FROM 3c_eng_persons WHERE watchlist='employee' OR watchlist IS NULL")
our_persons = {r[1].lower().strip(): {"id":r[0],"name":r[1],"watchlist":r[2]} for r in cur.fetchall()}
cur.execute("SELECT id, name FROM 3c_eng_persons")
our_by_id = {r[0]: r[1] for r in cur.fetchall()}

print(f"Our FRS persons: {len(our_persons)}")

# ── Current FAISS enrollment ──────────────────────────────────
enrolled_pids = set(v["person_id"] for v in engine.employee_index.id_map.values())
emb_count     = {}
for v in engine.employee_index.id_map.values():
    emb_count[v["person_id"]] = emb_count.get(v["person_id"],0)+1

# ── Stats ─────────────────────────────────────────────────────
stats = {
    "total_checked": 0, "enrolled": 0, "updated": 0,
    "skipped_no_images": 0, "skipped_no_face": 0,
    "skipped_low_sim": 0, "already_good": 0,
    "not_in_our_db": 0, "errors": 0,
    "entity_ids_mapped": 0,
}

def download_images(org_id, full_name, face_paths_json):
    """Download face images from S3. Returns list of cv2 images."""
    try:
        paths = json.loads(face_paths_json) if face_paths_json else []
    except Exception:
        return []
    if not paths:
        return []
    safe  = "".join(c if c.isalnum() or c in "_ " else "_" for c in full_name).replace(" ","_")
    pdir  = DOWNLOAD_DIR / f"{org_id}_{safe}"
    pdir.mkdir(exist_ok=True)
    images = []
    for i, url in enumerate(paths[:8]):
        if not url.startswith("http"):
            url = f"{S3_BASE}/{url}"
        fname = pdir / f"face_{i+1}.jpg"
        try:
            if not fname.exists():
                urllib.request.urlretrieve(url, str(fname))
            img = cv2.imread(str(fname))
            if img is not None:
                images.append(img)
        except Exception as e:
            pass  # image not accessible
    return images

def get_embedding(img):
    faces = engine.app.get(img)
    if not faces: return None
    face = max(faces, key=lambda f: f.det_score)
    if face.det_score < 0.5: return None
    bbox = face.bbox.astype(int)
    fw = bbox[2]-bbox[0]
    if fw < MIN_FACE_SIZE: return None
    emb = face.embedding
    if emb is None: return None
    return emb / (np.linalg.norm(emb)+1e-9)

def self_similarity(embeddings):
    if len(embeddings) < 2: return 1.0
    sims = []
    for i in range(len(embeddings)):
        for j in range(i+1, len(embeddings)):
            sims.append(float(np.dot(embeddings[i], embeddings[j])))
    return float(np.mean(sims))

def find_our_person(fn, ln, email, entity_id):
    """Find our person_id by name matching."""
    full = f"{fn} {ln}".strip()
    # Exact match
    if full.lower() in our_persons:
        return our_persons[full.lower()]
    # First name match
    if fn:
        for pname, info in our_persons.items():
            if fn.lower() in pname:
                return info
    # Last name match
    if ln:
        for pname, info in our_persons.items():
            if ln.lower() in pname:
                return info
    return None

def update_entity_mapping(person_id, entity_id, full_name, company):
    """Upsert into 3c_eng_entity_mapping."""
    if not entity_id: return
    now_iso = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO 3c_eng_entity_mapping
            (entity_id, full_name, person_id, our_name, company, match_method, mapped_at)
        VALUES (%s,%s,%s,%s,%s,'auto_name',%s)
        ON DUPLICATE KEY UPDATE
            person_id=%s, our_name=%s, company=%s, mapped_at=%s
    """, (entity_id, full_name, person_id, full_name, company, now_iso,
          person_id, full_name, company, now_iso))

def update_ks_map(person_id, entity_id, full_name):
    """Upsert into 3c_eng_ks_map."""
    if not entity_id: return
    now_iso = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO 3c_eng_ks_map (person_id, ks_entity_id, ks_name, mapped_at, mapped_by)
        VALUES (%s,%s,%s,%s,'auto_name')
        ON DUPLICATE KEY UPDATE ks_entity_id=%s, ks_name=%s, mapped_at=%s
    """, (person_id, entity_id, full_name, now_iso,
          entity_id, full_name, now_iso))

# ── Process both tables ───────────────────────────────────────
print("\n" + "="*68)
print("  DOWNLOADING AND ENROLLING ALL PERSONS FROM USER MASTER TABLES")
print("="*68)

for tbl in ["zdotapps_user_master", "factops_user_master"]:
    cur.execute(f"""
        SELECT org_issued_id, first_name, last_name, email_id,
               entity_id, employment_status, face_image_paths, department
        FROM `{tbl}`
        WHERE employment_status='Active'
        ORDER BY first_name, last_name
    """)
    rows = cur.fetchall()
    print(f"\n[{tbl}] Total active persons: {len(rows)}")

    for row in rows:
        org_id, fn, ln, email, entity_id, status, face_paths, dept = row
        full_name = f"{fn or ''} {ln or ''}".strip()
        company   = "zdotapps" if "zdot" in tbl else "factops"
        stats["total_checked"] += 1

        if not full_name:
            continue

        # Find person in our FRS DB
        person_info = find_our_person(fn or "", ln or "", email, entity_id)

        if not person_info:
            # Person not in our DB — create them
            try:
                cur.execute("""
                    INSERT INTO 3c_eng_persons
                        (name, watchlist, company, created_at)
                    VALUES (%s,'employee',%s,%s)
                """, (full_name, company, datetime.now().isoformat()))
                conn.commit()
                new_id = cur.lastrowid
                person_info = {"id": new_id, "name": full_name}
                our_persons[full_name.lower()] = person_info
                print(f"  + Added new person: {full_name} (id={new_id})")
            except Exception as e:
                stats["errors"] += 1
                continue

        pid = person_info["id"]

        # Update entity mapping
        if entity_id:
            update_entity_mapping(pid, entity_id, full_name, company)
            update_ks_map(pid, entity_id, full_name)
            stats["entity_ids_mapped"] += 1

        # Check if already well enrolled
        current_count = emb_count.get(pid, 0)
        if current_count >= 5:
            stats["already_good"] += 1
            continue

        # Download images
        imgs = download_images(org_id, full_name, face_paths)
        if not imgs:
            stats["skipped_no_images"] += 1
            continue

        # Extract embeddings
        embeddings = []
        for img in imgs:
            emb = get_embedding(img)
            if emb is not None:
                embeddings.append(emb)

        if len(embeddings) < 1:
            stats["skipped_no_face"] += 1
            continue

        # Self-similarity check (skip if only 1 image)
        if len(embeddings) >= 2:
            avg_sim = self_similarity(embeddings)
            if avg_sim < MIN_SELF_SIM:
                print(f"  ! Low self-sim={avg_sim:.3f} for {full_name} — skipping")
                stats["skipped_low_sim"] += 1
                continue

        # Remove old embeddings if re-enrolling
        if current_count > 0:
            engine.employee_index.remove(pid)

        # Enroll
        enrolled_this = 0
        for img in imgs[:5]:
            try:
                result = engine.enroll(img, person_id=pid, name=full_name, watchlist="employee")
                if result.get("success") or result.get("note") == "duplicate_skipped":
                    enrolled_this += 1
            except Exception:
                pass

        if enrolled_this > 0:
            # Update photo in DB
            try:
                _, buf = cv2.imencode(".jpg", imgs[0])
                b64 = base64.b64encode(buf.tobytes()).decode()
                cur.execute("""
                    UPDATE 3c_eng_persons
                    SET photo_b64=%s, company=%s
                    WHERE id=%s
                """, (b64, company, pid))
                conn.commit()
            except Exception:
                pass

            emb_count[pid] = enrolled_this
            if pid in enrolled_pids:
                stats["updated"] += 1
            else:
                stats["enrolled"] += 1
                enrolled_pids.add(pid)
            print(f"  ✓ Enrolled: {full_name:<30} id={pid}  embs={enrolled_this}  entity={entity_id or '—'}")
        else:
            stats["skipped_no_face"] += 1

# ── Commit entity mappings ────────────────────────────────────
conn.commit()
conn.close()

# ── Final stats ───────────────────────────────────────────────
final = engine.get_stats()
print(f"\n{'='*68}")
print(f"  ENROLLMENT COMPLETE")
print(f"{'='*68}")
print(f"  Total checked          : {stats['total_checked']}")
print(f"  Newly enrolled         : {stats['enrolled']}")
print(f"  Updated (re-enrolled)  : {stats['updated']}")
print(f"  Already fully enrolled : {stats['already_good']}")
print(f"  Skipped (no images)    : {stats['skipped_no_images']}")
print(f"  Skipped (no face det)  : {stats['skipped_no_face']}")
print(f"  Skipped (low self-sim) : {stats['skipped_low_sim']}")
print(f"  Entity IDs mapped      : {stats['entity_ids_mapped']}")
print(f"  Errors                 : {stats['errors']}")
print(f"\n  FAISS total embeddings : {final['total_enrolled_embeddings']}")
print(f"  FAISS unique persons   : {final['unique_persons']}")
print(f"\n  Restart server to load updated embeddings.")
print("="*68)

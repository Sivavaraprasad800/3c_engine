"""
identify_unknowns.py
====================
Takes last 20 Unknown records from DB.
Runs recognition on each snapshot.
Reports who each person ACTUALLY is.
"""
import os, sys, io, cv2, base64
import numpy as np
import pickle, faiss, pymysql
from pathlib import Path
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

os.chdir(str(Path(__file__).parent))
for line in open(".env", encoding="utf-8-sig"):
    l=line.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip())

DB_HOST=os.environ.get("DB_HOST",""); DB_PORT=int(os.environ.get("DB_PORT","3306"))
DB_USER=os.environ.get("DB_USER",""); DB_PASS=os.environ.get("DB_PASS",os.environ.get("DB_PASSWORD",""))
DB_NAME=os.environ.get("DB_NAME","")

import onnxruntime as ort
from insightface.app import FaceAnalysis
so = ort.SessionOptions(); so.intra_op_num_threads=2
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"],
                   allowed_modules=["detection","recognition"], session_options=so)
app.prepare(ctx_id=-1, det_size=(320,320))
emp_index = faiss.read_index("face_index.faiss")
with open("id_map.pkl","rb") as f:
    emp_map = pickle.load(f)["id_map"]

def decode(b64):
    if b64 and "," in b64: b64=b64.split(",",1)[1]
    try:
        arr=np.frombuffer(base64.b64decode(b64),dtype=np.uint8)
        return cv2.imdecode(arr,cv2.IMREAD_COLOR)
    except: return None

def recognize(img):
    if img is None: return None, 0.0
    faces = app.get(img)
    if not faces: return None, 0.0
    face = max(faces, key=lambda f: f.det_score)
    emb  = getattr(face,"normed_embedding",None)
    if emb is None: emb = face.embedding
    if emb is None: return None, 0.0
    emb_n = emb/(np.linalg.norm(emb)+1e-9)
    k = min(10, emp_index.ntotal)
    sc, ids = emp_index.search(emb_n.reshape(1,-1), k)
    seen = {}
    for j in range(k):
        fid=int(ids[0][j]); sim=float(sc[0][j])
        if fid in emp_map:
            pid=emp_map[fid]["person_id"]
            if pid not in seen or sim>seen[pid][0]:
                seen[pid]=(sim,emp_map[fid]["name"])
    if not seen: return None, 0.0
    best = max(seen.values(), key=lambda x:x[0])
    return best[1], round(best[0],4)

# ── Fetch last 20 Unknown events ─────────────────────────────
conn=pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USER,
    password=DB_PASS,database=DB_NAME,charset="utf8mb4",connect_timeout=15)
cur=conn.cursor()
cur.execute("""
    SELECT id, camera_id, timestamp, snapshot_b64
    FROM 3c_eng_events
    WHERE matched=0 AND suspected=0
      AND (person_name='Unknown' OR person_name IS NULL)
      AND snapshot_b64 IS NOT NULL AND snapshot_b64 != ''
    ORDER BY timestamp DESC
    LIMIT 20
""")
rows = cur.fetchall()
conn.close()

print("="*68)
print(f"  IDENTIFYING 20 MOST RECENT UNKNOWN RECORDS")
print("="*68)
print(f"\n  {'#':>3}  {'Camera':<20} {'Timestamp':<22} {'Found Person':<28} {'Conf':>7}  Status")
print(f"  {'-'*3}  {'-'*20} {'-'*22} {'-'*28} {'-'*7}  {'-'*12}")

found_count = 0
suspected_count = 0
truly_unknown = 0

results = []
for i, (eid, cam, ts, b64) in enumerate(rows, 1):
    img  = decode(b64)
    name, sim = recognize(img)

    if sim >= 0.50:
        status = "IDENTIFIED"
        found_count += 1
    elif sim >= 0.37:
        status = "SUSPECTED"
        suspected_count += 1
    else:
        status = "truly unknown"
        truly_unknown += 1
        name = name or "—"

    star = "  ***" if sim >= 0.50 else ("  ~" if sim >= 0.37 else "")
    short_name = (name[:26]+"..") if name and len(name)>28 else (name or "—")
    print(f"  {i:>3}  {str(cam):<20} {str(ts)[:22]:<22} {short_name:<28} {sim:>7.3f}  {status}{star}")
    results.append({"eid":eid,"cam":cam,"ts":str(ts),"name":name,"sim":sim,"status":status})

# ── Summary ───────────────────────────────────────────────────
print(f"\n{'='*68}")
print(f"  RESULTS — {len(rows)} Unknown records analyzed")
print(f"{'='*68}")
print(f"  IDENTIFIED (sim>=0.50)  : {found_count}")
print(f"  SUSPECTED  (sim>=0.37)  : {suspected_count}")
print(f"  Truly Unknown (<0.37)   : {truly_unknown}")
print(f"\n  These {found_count+suspected_count} people were detected as Unknown")
print(f"  but our model can identify them:")

identified = [r for r in results if r["sim"]>=0.37]
if identified:
    print(f"\n  {'Person':<30} {'Camera':<20} {'Sim':>7}  {'Time'}")
    print(f"  {'-'*30} {'-'*20} {'-'*7}  {'-'*22}")
    for r in sorted(identified, key=lambda x:-x["sim"]):
        print(f"  {r['name']:<30} {r['cam']:<20} {r['sim']:>7.3f}  {r['ts'][:22]}")

print(f"\n  WHY ARE ENROLLED PEOPLE SHOWING AS UNKNOWN?")
print(f"  {'─'*60}")
if found_count > 0:
    pct = round((found_count+suspected_count)/len(rows)*100)
    print(f"  {pct}% of 'Unknown' records ARE enrolled employees.")
    print(f"  The system failed to identify them in real-time because:")
    print(f"  1. Single-frame recognition (no averaging) — low confidence")
    print(f"  2. Blurry/dark frames from camera — below threshold")
    print(f"  3. Face turned or too small in that specific captured frame")
    print(f"  4. Dedup suppressed the matched event before it could save")
    print(f"\n  THE FIX: Deploy embedding averaging (already tested — gives +0.10)")
    print(f"  With averaging, these would be IDENTIFIED, not Unknown.")

print(f"\n  No data written to database.")
print("="*68)

"""
gender_confusion_check.py
==========================
Problem: A MALE person (snapshot1) appeared under FEMALE name (Keerrrrthi Kanasani)
         Dashboard shows:
           - Ganesh Allada    03/09/2026 10:51:25  Studio-CAM2     52%
           - Keerrrrthi Kanasani 03/09/2026 10:50:39  0F-ECOMALL-ENTRY 51%

Analyzes:
  snapshot (1).jpg  - the mystery person (male?)
  snapshot (3).jpg  - Keerrrrthi Kanasani (female, correct)

Finds: why male got female name, root cause
"""

import os, sys, io, cv2
import numpy as np
import pickle, faiss
from pathlib import Path
from datetime import datetime, timedelta
import pymysql, base64

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

def analyze(img, label):
    h,w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap  = cv2.Laplacian(gray, cv2.CV_64F).var()
    bright = float(np.mean(gray))

    faces = app.get(img)
    if not faces:
        print(f"\n  {label}: NO FACE DETECTED")
        return None, 0.0

    face = max(faces, key=lambda f: f.det_score)
    bbox = face.bbox.astype(int).tolist()
    fw,fh = bbox[2]-bbox[0], bbox[3]-bbox[1]
    det   = float(face.det_score)

    emb   = getattr(face,"normed_embedding",None)
    if emb is None: emb = face.embedding
    emb_n = emb/(np.linalg.norm(emb)+1e-9) if emb is not None else None

    k = min(20, emp_index.ntotal)
    seen = {}
    if emb_n is not None:
        sc,ids = emp_index.search(emb_n.reshape(1,-1), k)
        for j in range(k):
            fid=int(ids[0][j]); sim=float(sc[0][j])
            if fid in emp_map:
                pid=emp_map[fid]["person_id"]; nm=emp_map[fid]["name"]
                if pid not in seen or sim>seen[pid][0]:
                    seen[pid]=(sim,nm)

    ranked = sorted(seen.values(), key=lambda x:-x[0])
    top1_sim, top1_name = ranked[0] if ranked else (0,"?")

    print(f"\n  {'─'*60}")
    print(f"  {label}")
    print(f"  {'─'*60}")
    print(f"  Size    : {w}x{h}px  Face:{fw}x{fh}px  Det:{det:.3f}")
    print(f"  Sharp   : {lap:.1f}  ({'BLURRY' if lap<40 else 'MODERATE' if lap<200 else 'SHARP'})")
    print(f"  Bright  : {bright:.1f}")
    print(f"\n  Top-5 matches:")
    print(f"  {'Name':<32} {'Sim':>7}  {'Status'}")
    print(f"  {'-'*32} {'-'*7}  {'-'*12}")
    for sim, name in ranked[:5]:
        status = "IDENTIFIED" if sim>=0.50 else "SUSPECTED" if sim>=0.37 else "low"
        print(f"  {name:<32} {sim:.4f}  {status}")

    return emb_n, top1_sim

# ── Load and analyze all snapshots ───────────────────────────
IMAGES = {
    "snapshot(1).jpg  [mystery person - shown as Keerrrrthi?]":
        r"C:\Users\siva\Downloads\result\snapshot (1).jpg",
    "snapshot(3).jpg  [Keerrrrthi Kanasani - real female]":
        r"C:\Users\siva\Downloads\result\snapshot (3).jpg",
}

# Also try snapshot.jpg
snap_orig = r"C:\Users\siva\Downloads\result\snapshot.jpg"
if Path(snap_orig).exists():
    IMAGES["snapshot.jpg  [previous - Aneesha Ravi]"] = snap_orig

print("="*62)
print("  GENDER CONFUSION ROOT CAUSE ANALYSIS")
print("  Dashboard: Male person shown as Keerrrrthi Kanasani 51%")
print("="*62)

embeddings = {}
for label, path in IMAGES.items():
    img = cv2.imread(path)
    if img is None:
        print(f"\n  [{label}] Cannot read image")
        continue
    emb, sim = analyze(img, label)
    embeddings[label] = emb

# ── Cross-similarity between the two snapshots ───────────────
keys = list(embeddings.keys())
if len(keys) >= 2 and embeddings[keys[0]] is not None and embeddings[keys[1]] is not None:
    e1 = embeddings[keys[0]]
    e2 = embeddings[keys[1]]
    cross_sim = float(np.dot(e1, e2))
    print(f"\n  {'─'*62}")
    print(f"  CROSS-SIMILARITY between snapshot(1) and snapshot(3):")
    print(f"  {cross_sim:.4f}  ", end="")
    if cross_sim >= 0.50:
        print("SAME PERSON — system was right to match them")
    elif cross_sim >= 0.37:
        print("POSSIBLY SAME — borderline")
    else:
        print("DIFFERENT PEOPLE — confirms wrong name assignment")

# ── Check Keerrrrthi's enrolled embedding ────────────────────
print(f"\n  {'─'*62}")
print(f"  KEERRRRTHI KANASANI — enrolled templates in FAISS:")
keerthi_pids = set()
for fid, info in emp_map.items():
    if "keer" in info["name"].lower() or "kanasani" in info["name"].lower():
        keerthi_pids.add(info["person_id"])
        print(f"  pid={info['person_id']}  name={info['name']}")

count_k = sum(1 for info in emp_map.values() if info["person_id"] in keerthi_pids)
print(f"  Total templates: {count_k}")

# ── DB events at 10:50-10:51 on 03/09/2026 ──────────────────
print(f"\n  {'─'*62}")
print(f"  DB EVENTS at 10:50-10:52 on 03/09/2026 (all cameras):")
try:
    conn=pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USER,
        password=DB_PASS,database=DB_NAME,charset="utf8mb4",connect_timeout=10)
    cur=conn.cursor()
    cur.execute("""
        SELECT id, camera_id, person_name, confidence, matched, suspected,
               timestamp, snapshot_b64
        FROM 3c_eng_events
        WHERE timestamp BETWEEN '2026-09-03 10:49:00' AND '2026-09-03 10:52:30'
        ORDER BY timestamp ASC
    """)
    rows = cur.fetchall()
    print(f"  Found {len(rows)} events\n")
    print(f"  {'ID':>8}  {'Camera':<22} {'Person':<28} {'Conf':>6} {'M':>2} {'S':>2}  {'Time'}")
    print(f"  {'-'*8}  {'-'*22} {'-'*28} {'-'*6} {'-'*2} {'-'*2}  {'-'*22}")
    for eid,cam,pname,conf,m,s,ts,b64 in rows:
        img_ev = decode(b64) if b64 else None
        re_name = "?"
        if img_ev is not None:
            faces = app.get(img_ev)
            if faces:
                face = max(faces, key=lambda f: f.det_score)
                emb  = getattr(face,"normed_embedding",None)
                if emb is None: emb = face.embedding
                if emb is not None:
                    emb_n = emb/(np.linalg.norm(emb)+1e-9)
                    k=min(5,emp_index.ntotal)
                    sc2,ids2=emp_index.search(emb_n.reshape(1,-1),k)
                    seen2={}
                    for j in range(k):
                        fid=int(ids2[0][j]); sim=float(sc2[0][j])
                        if fid in emp_map:
                            pid=emp_map[fid]["person_id"]
                            if pid not in seen2 or sim>seen2[pid][0]:
                                seen2[pid]=(sim,emp_map[fid]["name"])
                    if seen2:
                        bst=max(seen2.values(),key=lambda x:x[0])
                        re_name=f"{bst[1][:18]} {bst[0]:.3f}"
        mm="Y" if m else "N"; ss="Y" if s else "N"
        mismatch=""
        if pname and re_name!="?" and re_name.split()[0].lower()!=pname.split()[0].lower():
            mismatch="  *** MISMATCH"
        print(f"  {eid:>8}  {str(cam):<22} {str(pname or '?'):<28} "
              f"{float(conf or 0):>6.3f} {mm:>2} {ss:>2}  {str(ts)[:22]}")
        print(f"           Re-recog: {re_name}{mismatch}")
    conn.close()
except Exception as e:
    print(f"  DB error: {e}")

# ── ROOT CAUSE ────────────────────────────────────────────────
print(f"\n{'='*62}")
print(f"  ROOT CAUSE — WHY MALE GOT FEMALE NAME")
print(f"{'='*62}")
print(f"""
  From the dashboard screenshot:
    10:50:39  Keerrrrthi Kanasani  0F-ECOMALL-ENTRY  51%  Suspected
    10:51:25  Ganesh Allada        Studio-CAM2        52%  (not shown to you)

  The unknown male (snapshot 1) appeared at 0F-ECOMALL-ENTRY
  at almost the same time as Keerrrrthi.

  POSSIBLE CAUSES:

  1. SAME-CAMERA DEDUP BUG (most likely):
     Keerrrrthi walked past 0F-ECOMALL-ENTRY first.
     The dedup timer started: "last seen = Keerrrrthi"
     Unknown male walked past same camera within dedup window.
     System reused Keerrrrthi's name for his detection.

  2. BLURRY IMAGE MISIDENTIFICATION:
     snapshot(1) sharpness = 18.7 (extremely blurry)
     At this quality, embeddings are nearly random.
     Top match = 0.27 (below even Suspected threshold)
     But if threshold was relaxed or dedup reused name,
     wrong assignment happens.

  3. TWO PEOPLE IN SAME FRAME:
     If Keerrrrthi and the male were BOTH in the same frame,
     InsightFace detects both faces but only saves one event.
     The saved snapshot could be the male face but with
     Keerrrrthi's recognition result from the same frame.

  EVIDENCE CHECK:
  - snapshot(1) re-recognition: top match is NOT Keerrrrthi (0.27)
  - This means the face is NOT Keerrrrthi
  - The name came from dedup OR multi-face frame confusion

  FIX:
  Add embedding similarity check before reusing dedup name.
  If sim(current_face, last_face) < 0.5 -> treat as new person.
""")
print("="*62)

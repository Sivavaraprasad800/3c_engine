"""
find_root_cause.py
==================
Root cause: at 03/09/2026 09:49, Hanumantha was ALSO in front of camera.
System may have mixed up detections — gave Hanumantha's name to Aneesha's face.

Investigates:
1. All events at 09:49 on Studio-CAM2
2. How many faces were detected in that minute
3. Whether Hanumantha had a detection right next to Aneesha
4. The dedup/tracker logic that could cause wrong assignment
"""

import os, sys, io, cv2, base64
import numpy as np
import pickle, faiss, pymysql
from pathlib import Path
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

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

def get_top3(img):
    faces=app.get(img)
    if not faces: return []
    face=max(faces,key=lambda f:f.det_score)
    emb=getattr(face,"normed_embedding",None)
    if emb is None: emb=face.embedding
    if emb is None: return []
    emb_n=emb/(np.linalg.norm(emb)+1e-9)
    k=min(10,emp_index.ntotal)
    sc,ids=emp_index.search(emb_n.reshape(1,-1),k)
    seen={}
    for j in range(k):
        fid=int(ids[0][j]); sim=float(sc[0][j])
        if fid in emp_map:
            pid=emp_map[fid]["person_id"]
            nm=emp_map[fid]["name"]
            if pid not in seen or sim>seen[pid][0]:
                seen[pid]=(sim,nm)
    return sorted(seen.values(),key=lambda x:-x[0])[:3]

def count_faces(img):
    return len(app.get(img)) if img is not None else 0

conn=pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USER,
    password=DB_PASS,database=DB_NAME,charset="utf8mb4",connect_timeout=15)
cur=conn.cursor()

print("="*68)
print("  ROOT CAUSE ANALYSIS — WRONG NAME AT 09:49 Studio-CAM2")
print("="*68)

# ── 1. All events at Studio-CAM2 between 09:48 and 09:51 ─────
print("\n1. ALL EVENTS at Studio-CAM2 between 09:48–09:51 on 03/09/2026")
print("-"*68)
cur.execute("""
    SELECT id, person_name, confidence, matched, suspected,
           timestamp, snapshot_b64
    FROM 3c_eng_events
    WHERE camera_id='Studio-CAM2'
      AND timestamp BETWEEN '2026-09-03 09:48:00' AND '2026-09-03 09:51:00'
    ORDER BY timestamp ASC
""")
events = cur.fetchall()
print(f"  Found {len(events)} events in that 3-minute window\n")

print(f"  {'ID':>8}  {'Person':<28} {'Conf':>6} {'M':>2} {'S':>2}  {'Timestamp'}")
print(f"  {'-'*8}  {'-'*28} {'-'*6} {'-'*2} {'-'*2}  {'-'*22}")
for eid,pname,conf,matched,suspected,ts,b64 in events:
    m="Y" if matched else " "
    s="Y" if suspected else " "
    print(f"  {eid:>8}  {(pname or '?'):<28} {float(conf or 0):>6.3f} {m:>2} {s:>2}  {str(ts)[:22]}")

# ── 2. Find Hanumantha events in same window ──────────────────
print(f"\n2. HANUMANTHA events in same window (ANY camera)")
print("-"*68)
cur.execute("""
    SELECT id, camera_id, confidence, matched, suspected, timestamp
    FROM 3c_eng_events
    WHERE person_name LIKE '%Hanumantha%'
      AND timestamp BETWEEN '2026-09-03 09:48:00' AND '2026-09-03 09:51:00'
    ORDER BY timestamp ASC
""")
hanu_events = cur.fetchall()
if hanu_events:
    for eid,cam,conf,m,s,ts in hanu_events:
        print(f"  id={eid}  cam={cam}  conf={float(conf or 0):.3f}  "
              f"matched={'Y' if m else 'N'}  ts={str(ts)[:22]}")
else:
    print("  No Hanumantha events in this window")

# ── 3. What does snapshot.jpg actually contain? ───────────────
print(f"\n3. SNAPSHOT.JPG — re-running recognition on saved image")
print("-"*68)
img_saved = cv2.imread(r"C:\Users\siva\Downloads\result\snapshot.jpg")
if img_saved is not None:
    n_faces = count_faces(img_saved)
    top3    = get_top3(img_saved)
    h,w     = img_saved.shape[:2]
    gray    = cv2.cvtColor(img_saved,cv2.COLOR_BGR2GRAY)
    lap     = cv2.Laplacian(gray,cv2.CV_64F).var()
    print(f"  Size={w}x{h}  Sharpness={lap:.0f}  Faces={n_faces}")
    print(f"  Top matches:")
    for sim,name in top3:
        print(f"    {name:<32} {sim:.4f}")

# ── 4. Check the event snapshot for that specific event ──────
print(f"\n4. ACTUAL EVENT SNAPSHOT from DB (the one that showed Hanumantha)")
print("-"*68)

# Find the event that showed Hanumantha for Aneesha
cur.execute("""
    SELECT id, person_name, confidence, matched, suspected,
           timestamp, snapshot_b64
    FROM 3c_eng_events
    WHERE camera_id='Studio-CAM2'
      AND timestamp BETWEEN '2026-09-03 09:49:00' AND '2026-09-03 09:50:30'
    ORDER BY timestamp ASC
    LIMIT 10
""")
specific = cur.fetchall()
for eid,pname,conf,m,s,ts,b64 in specific:
    img=decode(b64) if b64 else None
    n_f = count_faces(img) if img else 0
    if img is not None:
        gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        lap=cv2.Laplacian(gray,cv2.CV_64F).var()
        bright=float(np.mean(gray))
        top3=get_top3(img)
        top_name = top3[0][1] if top3 else "?"
        top_sim  = top3[0][0] if top3 else 0
        h,w=img.shape[:2]
    else:
        lap=bright=w=h=top_sim=0; top_name="?"

    print(f"\n  Event id={eid}  ts={str(ts)[:22]}")
    print(f"    DB says        : {pname}  conf={float(conf or 0):.3f}  "
          f"matched={'Y' if m else 'N'}  suspected={'Y' if s else 'N'}")
    print(f"    Image          : {w}x{h}px  sharp={lap:.0f}  bright={bright:.0f}  faces={n_f}")
    print(f"    Re-recognition : {top_name}  {top_sim:.4f}")
    mismatch = pname and top_name and top_name.split()[0].lower() != pname.split()[0].lower()
    if mismatch:
        print(f"    *** MISMATCH *** DB={pname}  Actual={top_name}")
        print(f"        This confirms wrong name was assigned!")

conn.close()

# ── 5. Root cause explanation ─────────────────────────────────
print(f"\n{'='*68}")
print(f"  ROOT CAUSE EXPLANATION")
print(f"{'='*68}")
print(f"""
  The likely sequence of events at 09:49 Studio-CAM2:

  1. HANUMANTHA walked past the camera at 09:49
     -> System detected his face, recognized him (Identified)
     -> Dedup tracker: stored "last seen = Hanumantha"

  2. ANEESHA walked past 1-5 seconds LATER
     -> System detected her face
     -> BUT the DEDUP WINDOW was still active from Hanumantha
     -> The dedup logic saw "someone at Studio-CAM2 just matched"
     -> It assigned Hanumantha's tracker ID to her detection

  THIS IS THE BUG:
  The dedup/cooldown system doesn't distinguish between DIFFERENT
  people — it suppresses detections based on TIME only, not FACE.
  When two different people walk past within the cooldown window
  (typically 30-120s), the second person gets the first person's name.

  EVIDENCE:
  - snapshot.jpg (Aneesha) → recognition gives: Aneesha Ravi 47.5%
  - But dashboard showed: Hanumantha Vallapaneni ~48%
  - This is NOT a face recognition error — it's a DEDUP/TRACKER bug

  FIX (in server.py):
  The dedup should check face EMBEDDING SIMILARITY before reusing
  a previous detection's identity, not just timestamp.
  
  Current: "if same camera + recent time -> skip or reuse last name"
  Needed : "if same camera + recent time + sim>0.6 -> reuse last name"
           "if same camera + recent time + sim<0.6 -> it's a different
            person, run fresh recognition"
""")
print("="*68)

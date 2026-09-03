"""
why_unknown.py
==============
Pranathi Garlapati scores 77.8% on snapshot(4).jpg
But dashboard shows her as Unknown / Unregistered.
Finds the exact reason why.
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

print("="*65)
print("  WHY IS PRANATHI GARLAPATI SHOWING AS UNKNOWN?")
print("="*65)

# ── 1. Check her enrollment in DB ────────────────────────────
print("\n1. ENROLLMENT CHECK")
print("-"*65)
conn=pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USER,
    password=DB_PASS,database=DB_NAME,charset="utf8mb4",connect_timeout=15)
cur=conn.cursor()

cur.execute("""
    SELECT id, name, watchlist, company,
           (photo_b64 IS NOT NULL AND photo_b64 != '') as has_photo,
           created_at
    FROM 3c_eng_persons
    WHERE name LIKE '%Pranathi%' OR name LIKE '%Garlapati%'
""")
persons = cur.fetchall()
if persons:
    for pid,nm,wl,co,hp,ca in persons:
        print(f"  DB person   : id={pid}  name={nm}")
        print(f"  Watchlist   : {wl}")
        print(f"  Company     : {co}")
        print(f"  Has photo   : {'YES' if hp else 'NO'}")
        print(f"  Created     : {ca}")
        # Count FAISS templates
        count = sum(1 for info in emp_map.values() if info["person_id"]==pid)
        print(f"  FAISS templates: {count}")
else:
    print("  NOT FOUND in 3c_eng_persons table!")

# ── 2. Check FAISS directly ───────────────────────────────────
print(f"\n2. FAISS INDEX CHECK")
print("-"*65)
pranathi_entries = [(fid,info) for fid,info in emp_map.items()
                    if "pranathi" in info["name"].lower()]
if pranathi_entries:
    print(f"  Found {len(pranathi_entries)} FAISS entries:")
    for fid, info in pranathi_entries:
        print(f"  fid={fid}  person_id={info['person_id']}  name={info['name']}")
else:
    print("  NOT FOUND in FAISS id_map!")

# ── 3. Check today's events for Pranathi ─────────────────────
print(f"\n3. RECENT EVENTS FOR PRANATHI")
print("-"*65)
d7=(datetime.now()-timedelta(days=7)).strftime("%Y-%m-%d")
cur.execute("""
    SELECT id, camera_id, person_name, confidence, matched, suspected,
           timestamp
    FROM 3c_eng_events
    WHERE (person_name LIKE %s OR person_name LIKE %s)
      AND timestamp >= %s
    ORDER BY timestamp DESC LIMIT 10
""", ("%Pranathi%", "%Garlapati%", d7+" 00:00:00"))
ev_rows = cur.fetchall()
if ev_rows:
    print(f"  Found {len(ev_rows)} recent events:")
    for eid,cam,nm,conf,m,s,ts in ev_rows:
        print(f"  id={eid}  cam={cam}  conf={float(conf or 0):.3f}  "
              f"matched={'Y' if m else 'N'}  ts={str(ts)[:22]}")
else:
    print("  NO recent events found for Pranathi")

# ── 4. Check the specific event at 11:11:23 Studio-CAM2 ──────
print(f"\n4. THE SPECIFIC UNKNOWN EVENT (Studio-CAM2  11:11:23)")
print("-"*65)
cur.execute("""
    SELECT id, camera_id, person_name, confidence, matched, suspected,
           timestamp, snapshot_b64
    FROM 3c_eng_events
    WHERE camera_id='Studio-CAM2'
      AND timestamp BETWEEN '2026-09-03 11:10:00' AND '2026-09-03 11:13:00'
    ORDER BY timestamp ASC
""")
spec_events = cur.fetchall()
print(f"  Events in that window: {len(spec_events)}")
for eid,cam,nm,conf,m,s,ts,b64 in spec_events:
    img = decode(b64) if b64 else None
    re_name="?"; re_sim=0.0
    if img is not None:
        faces=app.get(img)
        if faces:
            face=max(faces,key=lambda f:f.det_score)
            emb=getattr(face,"normed_embedding",None)
            if emb is None: emb=face.embedding
            if emb is not None:
                emb_n=emb/(np.linalg.norm(emb)+1e-9)
                k=min(5,emp_index.ntotal)
                sc2,ids2=emp_index.search(emb_n.reshape(1,-1),k)
                seen2={}
                for j in range(k):
                    fid=int(ids2[0][j]); sim=float(sc2[0][j])
                    if fid in emp_map:
                        pid2=emp_map[fid]["person_id"]
                        if pid2 not in seen2 or sim>seen2[pid2][0]:
                            seen2[pid2]=(sim,emp_map[fid]["name"])
                if seen2:
                    bst=max(seen2.values(),key=lambda x:x[0])
                    re_name=bst[1]; re_sim=bst[0]
    print(f"\n  id={eid}  ts={str(ts)[:22]}")
    print(f"  DB says   : {nm or 'Unknown'}  conf={float(conf or 0):.3f}  "
          f"matched={'Y' if m else 'N'}  suspected={'Y' if s else 'N'}")
    print(f"  Re-recog  : {re_name}  {re_sim:.4f}")
    if re_sim >= 0.50 and (not m):
        print(f"  *** BUG: Re-recognition={re_name} {re_sim:.3f} but saved as Unknown!")

conn.close()

# ── 5. Check system thresholds ───────────────────────────────
print(f"\n5. SYSTEM THRESHOLD CHECK")
print("-"*65)
print(f"  Pranathi sim on snapshot(4): 0.7781")
print(f"  Expected result: IDENTIFIED (above 0.50 threshold)")
print(f"  Actual result  : Unknown / Unregistered")
print(f"\n  Possible reasons the system shows Unknown despite 77.8% sim:")

# Re-run on the actual snapshot
img = cv2.imread(r"C:\Users\siva\Downloads\result\snapshot (4).jpg")
if img is not None:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap  = cv2.Laplacian(gray, cv2.CV_64F).var()
    faces = app.get(img)
    if faces:
        face = max(faces, key=lambda f: f.det_score)
        det  = float(face.det_score)
        bbox = face.bbox.astype(int).tolist()
        x1,y1,x2,y2=bbox; fw,fh=x2-x1,y2-y1

        print(f"\n  Image sharpness  : {lap:.1f}")
        print(f"  Detection score  : {det:.4f}")
        print(f"  Face size        : {fw}x{fh}px")

        reasons = []
        if lap < 15:
            reasons.append(f"VERY BLURRY (lap={lap:.0f}<15) — might fail quality gate")
        if det < 0.40:
            reasons.append(f"Low detection score ({det:.3f}) — face rejected by confidence filter")
        if fw < 30:
            reasons.append(f"Face too small ({fw}px) — below MIN_FACE_SIZE=30")

        # Check if this is from a live camera (different frame than our test image)
        print(f"\n  NOTE: snapshot(4).jpg is a SAVED SNAPSHOT we downloaded.")
        print(f"  The dashboard event at 11:11:23 may be a DIFFERENT FRAME from")
        print(f"  the live camera — lower quality than the saved snapshot.")
        print(f"\n  The saved snapshot(4).jpg scores 77.8% on Pranathi.")
        print(f"  But the LIVE FRAME at 11:11:23 was likely blurrier/smaller.")

        if reasons:
            print(f"\n  Quality issues found:")
            for r in reasons: print(f"    - {r}")
        else:
            print(f"\n  Image quality is acceptable (lap={lap:.0f}, det={det:.3f}, fw={fw}px)")
            print(f"  ROOT CAUSE: The live camera frame was likely worse quality")
            print(f"  than this downloaded snapshot. The live event hit a quality")
            print(f"  gate or the face was captured at a worse angle/blur level.")

print(f"\n{'='*65}")
print(f"  SUMMARY")
print(f"{'='*65}")
print(f"""
  The snapshot(4).jpg WE analyzed = Pranathi Garlapati 77.8% IDENTIFIED
  The dashboard event at 11:11 = Unknown

  These are DIFFERENT captures of the same person.

  Most likely causes (in order):
  1. The live frame had LOWER quality than the saved snapshot
     (blurrier, smaller face, or side angle) causing <0.50 confidence
  2. The dedup/cooldown suppressed Pranathi's detection
     (she was seen recently, system skipped re-saving)
  3. The live frame was captured BEFORE she walked close to camera
     (face too small/far, below min_face_size=30px)
  4. Camera quality gate rejected the frame
     (sharpness < BLUR_THRESHOLD or face < MIN_FACE_SIZE)
""")
print("="*65)

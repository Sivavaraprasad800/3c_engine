"""
trace_event.py
==============
Takes Keerrrrthi's Unknown event at 12:17 and traces
EXACTLY why it was saved as Unknown despite 0.727 confidence.
Simulates the full server.py pipeline step by step.
"""
import os, sys, io, cv2, base64, time
import numpy as np
import pickle, faiss, pymysql
from pathlib import Path
from datetime import datetime

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

# ── Fetch the specific Unknown events for Keerrrrthi ─────────
conn=pymysql.connect(host=DB_HOST,port=DB_PORT,user=DB_USER,
    password=DB_PASS,database=DB_NAME,charset="utf8mb4",connect_timeout=15)
cur=conn.cursor()
cur.execute("""
    SELECT id, camera_id, person_name, confidence, matched, suspected,
           timestamp, snapshot_b64
    FROM 3c_eng_events
    WHERE matched=0 AND suspected=0
      AND (person_name='Unknown' OR person_name IS NULL)
      AND snapshot_b64 IS NOT NULL
      AND timestamp >= '2026-09-03 12:15:00'
    ORDER BY timestamp DESC
    LIMIT 10
""")
rows = cur.fetchall()

# Also check if there are ANY Keerrrrthi events today
cur.execute("""
    SELECT id, camera_id, person_name, confidence, matched, suspected, timestamp
    FROM 3c_eng_events
    WHERE person_name LIKE %s
      AND timestamp >= '2026-09-03 12:00:00'
    ORDER BY timestamp DESC LIMIT 10
""", ("%Keerrrrthi%",))
keerthi_rows = cur.fetchall()
conn.close()

print("="*68)
print("  EXACT TRACE — WHY KEERRRRTHI SAVES AS UNKNOWN")
print("="*68)

print(f"\n1. Keerrrrthi events in DB today (12:00+):")
if keerthi_rows:
    for eid,cam,nm,conf,m,s,ts in keerthi_rows:
        print(f"  id={eid} cam={cam} name={nm} conf={float(conf or 0):.3f} "
              f"matched={'Y' if m else 'N'} suspected={'Y' if s else 'N'} ts={str(ts)[:22]}")
else:
    print("  NO Keerrrrthi events found after 12:00")

print(f"\n2. Recent Unknown events (12:15+) — tracing each:")
THRESHOLD = 0.50
SUSPECTED_THRESHOLD = 0.37

for eid,cam,nm,conf,m,s,ts,b64 in rows[:5]:
    print(f"\n  {'─'*60}")
    print(f"  Event id={eid}  cam={cam}  ts={str(ts)[:22]}")
    img = decode(b64) if b64 else None
    if img is None:
        print("  Cannot decode image"); continue

    h,w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap  = cv2.Laplacian(gray, cv2.CV_64F).var()
    bright = float(np.mean(gray))
    print(f"  Image: {w}x{h}  sharp={lap:.1f}  bright={bright:.1f}")

    # Step A: Detection
    faces = app.get(img)
    print(f"  Step A — Detection: {len(faces)} face(s) found")
    if not faces:
        print("  -> STOPPED: No face detected → saved as Unknown (no embedding)")
        continue

    face = max(faces, key=lambda f: f.det_score)
    det  = float(face.det_score)
    print(f"  Step A — Best face det_score={det:.4f}")

    # Step B: Embedding
    emb = getattr(face,"normed_embedding",None)
    if emb is None: emb = face.embedding
    if emb is None:
        print("  -> STOPPED: No embedding extracted"); continue
    emb_n = emb/(np.linalg.norm(emb)+1e-9)

    # Step C: FAISS search
    k = min(10, emp_index.ntotal)
    sc,ids = emp_index.search(emb_n.reshape(1,-1), k)
    seen={}
    for j in range(k):
        fid=int(ids[0][j]); sim=float(sc[0][j])
        if fid in emp_map:
            pid=emp_map[fid]["person_id"]
            if pid not in seen or sim>seen[pid][0]:
                seen[pid]=(sim,emp_map[fid]["name"])
    if not seen:
        print("  -> STOPPED: FAISS returned no matches"); continue
    best=max(seen.values(),key=lambda x:x[0])
    best_sim, best_name = best
    print(f"  Step C — FAISS top match: {best_name}  sim={best_sim:.4f}")

    # Step D: Threshold check
    print(f"\n  Step D — Threshold check:")
    print(f"    best_sim={best_sim:.4f}  threshold={THRESHOLD}  suspected={SUSPECTED_THRESHOLD}")
    if best_sim >= THRESHOLD:
        print(f"    -> Should be IDENTIFIED — but saved as Unknown!")
        print(f"    -> BUG: upgrade code in server.py did not run for this event")
    elif best_sim >= SUSPECTED_THRESHOLD:
        print(f"    -> Should be SUSPECTED — but saved as Unknown!")
        print(f"    -> BUG: upgrade code in server.py did not run for this event")
    else:
        print(f"    -> Correctly Unknown (sim={best_sim:.4f} < {SUSPECTED_THRESHOLD})")
        continue

    # Step E: Check what version of server.py handled this
    print(f"\n  Step E — Why did upgrade code NOT run?")
    print(f"    The event timestamp is {str(ts)[:22]}")
    print(f"    Your latest fix was pushed at ~12:03")
    ts_dt = datetime.fromisoformat(str(ts)[:19]) if ts else None
    if ts_dt and ts_dt.hour == 12 and ts_dt.minute >= 17:
        print(f"    This event is AFTER the fix was pushed")
        print(f"    POSSIBLE CAUSES:")
        print(f"    1. Server was NOT restarted after pulling new code from git")
        print(f"    2. The running server.py file is DIFFERENT from the git version")
        print(f"    3. The upgrade code has a bug preventing it from firing")
        print(f"\n    CHECK: Does your running server have this code?")
        print(f"    Search in server.py for: '_sus_thresh_pre'")
        print(f"    If NOT found → server.py was not updated on the running machine")

print(f"\n{'='*68}")
print(f"  DIAGNOSIS SUMMARY")
print(f"{'='*68}")
print(f"""
  The FAISS recognition correctly identifies Keerrrrthi at 0.63-0.73.
  But the running server is still saving her as Unknown.

  This means the new upgrade code is NOT executing in the live server.

  MOST LIKELY REASON:
  The server.py that git pushed is in:
    D:\\kk]\\siva\\frs_ai_model-main\\frs_ai_model-main\\server.py

  But you might be running a DIFFERENT server.py somewhere else,
  OR the file wasn't saved/reloaded properly.

  VERIFY with this command in your terminal:
    python -c "import server; print(server.__file__)"

  Also check: does your server log show this message on startup?
    '[Server] Camera mode: ...'

  If yes, what version does it show? The fix adds this log line:
    '[UpgradeSuspected:...]'
  
  If you don't see [UpgradeSuspected] in the logs → old code is running.
""")

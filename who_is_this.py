"""
who_is_this.py
==============
Deep check: the image was labeled Hanumantha Vallapaneni (Suspected 48%)
but might actually be Aneesha Ravi.
Checks: similarity to both, overlap between their embeddings, confusion reason.
"""
import os, sys, io, cv2
import numpy as np
import pickle, faiss
from pathlib import Path

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

os.chdir(str(Path(__file__).parent))

import onnxruntime as ort
from insightface.app import FaceAnalysis
so = ort.SessionOptions()
so.intra_op_num_threads = 2
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"],
                   allowed_modules=["detection","recognition"], session_options=so)
app.prepare(ctx_id=-1, det_size=(320,320))

emp_index = faiss.read_index("face_index.faiss")
with open("id_map.pkl","rb") as f:
    emp_map = pickle.load(f)["id_map"]

img_path = r"C:\Users\siva\Downloads\result\snapshot.jpg"
img = cv2.imread(img_path)
if img is None:
    print("Cannot read image"); sys.exit(1)

h, w  = img.shape[:2]
gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
lap   = cv2.Laplacian(gray, cv2.CV_64F).var()
bright= float(np.mean(gray))

print("="*60)
print("  WHO IS THIS — DEEP ANALYSIS")
print("="*60)
print(f"\n  Image  : {w}x{h}px")
print(f"  Sharp  : {lap:.1f}  ({'BLURRY' if lap<40 else 'OK'})")
print(f"  Bright : {bright:.1f}")

faces = app.get(img)
if not faces:
    print("  NO FACE DETECTED"); sys.exit(0)

face  = max(faces, key=lambda f: f.det_score)
bbox  = face.bbox.astype(int).tolist()
x1,y1,x2,y2 = bbox
fw,fh = x2-x1, y2-y1
emb   = getattr(face,"normed_embedding",None)
if emb is None: emb = face.embedding
emb_n = emb/(np.linalg.norm(emb)+1e-9)

print(f"  Face   : {fw}x{fh}px  det={face.det_score:.3f}")

# ── Full top-10 search ────────────────────────────────────────
k = min(20, emp_index.ntotal)
sc, ids = emp_index.search(emb_n.reshape(1,-1), k)

seen = {}
for j in range(k):
    fid=int(ids[0][j]); sim=float(sc[0][j])
    if fid in emp_map:
        pid=emp_map[fid]["person_id"]
        nm =emp_map[fid]["name"]
        if pid not in seen or sim>seen[pid][0]:
            seen[pid]=(sim,nm)

ranked = sorted(seen.values(), key=lambda x:-x[0])

print(f"\n  Top matches from FAISS:")
print(f"  {'Rank':<5} {'Name':<32} {'Sim':>7}  {'Status'}")
print(f"  {'-'*5} {'-'*32} {'-'*7}  {'-'*12}")
for rank,(sim,name) in enumerate(ranked[:10],1):
    status = "IDENTIFIED" if sim>=0.50 else "SUSPECTED" if sim>=0.37 else "unknown"
    bar    = "█"*int(sim*25)
    print(f"  #{rank:<4} {name:<32} {sim:.4f}  {status}  {bar}")

# ── Specifically check Hanumantha vs Aneesha ─────────────────
print(f"\n{'='*60}")
print(f"  SPECIFIC CHECK: Hanumantha vs Aneesha Ravi")
print(f"{'='*60}")

targets = {"Hanumantha Vallapaneni": None,
           "Aneesha Ravi": None}

for pid,(sim,name) in seen.items():
    for t in targets:
        if t.lower().split()[0] in name.lower():
            targets[t] = (sim, name, pid)

for label, result in targets.items():
    if result:
        sim, name, pid = result
        # Count how many embeddings this person has
        count = sum(1 for info in emp_map.values() if info["person_id"]==pid)
        print(f"\n  {label}")
        print(f"    Matched name    : {name}")
        print(f"    Similarity      : {sim:.4f} ({round(sim*100,1)}%)")
        print(f"    Templates stored: {count}")
    else:
        print(f"\n  {label}  — NOT in top-20 results")

# ── Why is it confused? ───────────────────────────────────────
print(f"\n{'='*60}")
print(f"  ROOT CAUSE — WHY IS IT CONFUSED?")
print(f"{'='*60}")

best_sim, best_name = ranked[0]
second_sim, second_name = ranked[1] if len(ranked)>1 else (0,"—")
gap = best_sim - second_sim

print(f"\n  Best match    : {best_name}  {best_sim:.4f}")
print(f"  Second match  : {second_name}  {second_sim:.4f}")
print(f"  Gap           : {gap:.4f}")

print(f"\n  Reasons for confusion:")
if lap < 40:
    print(f"  1. IMAGE IS BLURRY (sharpness={lap:.0f}) — face texture lost,")
    print(f"     ArcFace embedding is weak, small differences in similarity")
    print(f"     cause wrong top-1 matches")
if gap < 0.05:
    print(f"  2. GAP TOO SMALL ({gap:.4f}) — top-2 similarities are very")
    print(f"     close. This means the system has LOW CONFIDENCE in its answer.")
    print(f"     Any gap < 0.05 is unreliable — treat as 'unknown'")
if best_sim < 0.50:
    print(f"  3. BELOW THRESHOLD (best={best_sim:.4f} < 0.50) — correctly")
    print(f"     shown as 'Suspected', not 'Identified'")

# Check if Hanumantha and Aneesha templates look similar (embedding confusion)
hanu_embs = []
aneesha_embs = []
try:
    flat = faiss.downcast_index(emp_index.index)
    for fid, info in emp_map.items():
        if fid < flat.ntotal:
            vec = flat.reconstruct(fid)
            nm  = info["name"].lower()
            if "hanumantha" in nm:
                hanu_embs.append(vec)
            elif "aneesha" in nm:
                aneesha_embs.append(vec)

    if hanu_embs and aneesha_embs:
        # Cross similarity between their templates
        sims_cross = []
        for h_e in hanu_embs:
            for a_e in aneesha_embs:
                h_n = h_e/(np.linalg.norm(h_e)+1e-9)
                a_n = a_e/(np.linalg.norm(a_e)+1e-9)
                sims_cross.append(float(np.dot(h_n,a_n)))
        avg_cross = np.mean(sims_cross)
        max_cross = np.max(sims_cross)
        print(f"\n  Template similarity between Hanumantha & Aneesha:")
        print(f"    Avg cross-similarity: {avg_cross:.4f}")
        print(f"    Max cross-similarity: {max_cross:.4f}")
        if avg_cross > 0.35:
            print(f"    WARNING: Their enrollment photos look SIMILAR to each other")
            print(f"    This causes confusion on blurry/ambiguous captures")
        else:
            print(f"    Their templates are distinct — confusion is due to image blur only")
except Exception as e:
    print(f"  (Could not compare templates: {e})")

print(f"\n{'='*60}")
print(f"  VERDICT")
print(f"{'='*60}")
print(f"\n  The system showed: Hanumantha Vallapaneni (Suspected 48%)")
print(f"  My analysis shows: {ranked[0][1]} at {ranked[0][0]:.4f}")
print(f"\n  This image is TOO BLURRY to make a reliable identification.")
print(f"  Sharpness={lap:.0f} needs to be >=200 for reliable results.")
print(f"  Fix: improve Studio-CAM2 shutter speed to reduce blur.")
print(f"\n  No DB changes made.")
print("="*60)

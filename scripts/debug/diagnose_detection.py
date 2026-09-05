"""Diagnose why detection is low — check every layer."""
import os, sys, time, json
from pathlib import Path
from datetime import datetime, timedelta

for line in Path(".env").read_text(encoding="utf-8-sig").splitlines():
    l=line.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip())
sys.path.insert(0,".")

import urllib.request

BASE = "http://localhost:8001"

def get(path):
    try:
        r = urllib.request.urlopen(f"{BASE}{path}", timeout=5)
        return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

print("="*60)
print("  DETECTION PIPELINE DIAGNOSIS")
print("="*60)

# 1. Server health
h = get("/api/v1/health")
print(f"\n1. SERVER")
print(f"   Status          : {h.get('status','?')}")
print(f"   AI ready        : {h.get('ai_ready','?')}")
print(f"   Embeddings      : {h.get('total_enrolled_embeddings','?')}")
print(f"   Unique persons  : {h.get('unique_persons','?')}")
print(f"   Detector        : {h.get('detector','?')}")
running = h.get('running_cameras', [])
fps = h.get('camera_fps', {})
print(f"   Running cameras : {len(running)}")

# 2. Camera status
print(f"\n2. CAMERAS")
cams = get("/api/v1/cameras")
for c in cams.get("cameras", []):
    cfps = fps.get(c["id"], 0)
    zone_pts = len(c.get("detection_zone") or [])
    print(f"   {c['id']:<16} running={c.get('running',False)}  fps={cfps}  zone_pts={zone_pts}  face_conf={c.get('face_confidence',0.6)}")

# 3. Settings
print(f"\n3. SETTINGS")
s = get("/api/v1/settings/system")
print(f"   face_threshold      : {s.get('face_threshold','?')}")
print(f"   suspected_threshold : {s.get('suspected_threshold','?')}")
print(f"   dedup_seconds       : {s.get('dedup_seconds','?')}")
print(f"   camera_unknown_cool : {s.get('camera_unknown_cooldown','?')}")

# 4. Recent events
print(f"\n4. RECENT EVENTS (last 1 hour)")
evts = get("/api/v1/events?limit=100&hours=1")
evlist = evts.get("events", [])
matched = [e for e in evlist if e.get("matched")]
unknown = [e for e in evlist if not e.get("matched")]
print(f"   Total events    : {len(evlist)}")
print(f"   Matched (known) : {len(matched)}")
print(f"   Unknown         : {len(unknown)}")
if evlist:
    last_ts = evlist[0].get("timestamp","")
    print(f"   Last event      : {last_ts[:19] if last_ts else '?'}")
    print(f"   Minutes since last event: {int((datetime.now()-datetime.fromisoformat(last_ts[:19])).total_seconds()/60) if last_ts else '?'} min")

# 5. Per-camera event counts
print(f"\n5. EVENTS PER CAMERA (last 1h)")
from collections import Counter
cam_counts = Counter(e.get("camera_id") for e in evlist)
for cam, cnt in cam_counts.most_common():
    print(f"   {cam:<16} {cnt} events")

# 6. Pulse check on DEMO camera
print(f"\n6. DEMO CAMERA PULSE")
p = get("/api/v1/cameras/DEMO/pulse")
print(f"   capture_fps     : {p.get('fps','?')}")
print(f"   recognition_fps : {p.get('rec_fps','?')}")
print(f"   total_detections: {p.get('total_detections','?')}")
print(f"   running         : {p.get('running','?')}")
print(f"   has_zone        : {p.get('has_zone','?')}")

# 7. Check _last_seen dedup state
print(f"\n7. DIAGNOSIS SUMMARY")
issues = []
if not h.get("ai_ready"):
    issues.append("❌ AI engine not loaded")
if h.get("total_enrolled_embeddings", 0) < 100:
    issues.append(f"❌ Only {h.get('total_enrolled_embeddings')} embeddings — too few")
if s.get("face_threshold", 0.5) > 0.5:
    issues.append(f"❌ face_threshold {s.get('face_threshold')} too high")
if s.get("dedup_seconds", 120) > 60:
    issues.append(f"⚠  dedup_seconds={s.get('dedup_seconds')} — same person blocked for {s.get('dedup_seconds')}s")
for c in cams.get("cameras", []):
    if not c.get("running"):
        issues.append(f"❌ Camera {c['id']} NOT running")
    cfps = fps.get(c["id"], 0)
    if cfps < 3:
        issues.append(f"⚠  Camera {c['id']} low FPS: {cfps}")
if len(evlist) < 5:
    issues.append(f"❌ Very few events in last hour: {len(evlist)}")

if issues:
    for i in issues:
        print(f"  {i}")
else:
    print("  ✅ No obvious issues found — detection pipeline looks healthy")

print(f"\n{'='*60}")

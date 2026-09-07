"""Full application test — run against running server on localhost:8001"""
import urllib.request, json, time, sys

BASE = "http://localhost:8001"

def get(path):
    try: return json.loads(urllib.request.urlopen(f"{BASE}{path}", timeout=5).read())
    except Exception as e: return {"error": str(e)}

results = []
def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((name, status, detail))
    print(f"  [{status}] {name:<30} {detail}")

print("=" * 60)
print("FRS 3C ENGINE — FULL TEST REPORT")
print("=" * 60)

h = get("/api/v1/health")
check("Health endpoint",         h.get("status") == "ok",              f"status={h.get('status')}")
check("AI engine ready",         h.get("ai_ready") == True,            f"ai_ready={h.get('ai_ready')}")
check("Org ID set",              h.get("org_id") not in ("default",""), f"org_id={h.get('org_id')}")
check("Embeddings loaded",       h.get("total_enrolled_embeddings",0) > 0, f"{h.get('total_enrolled_embeddings')} embeddings")

d = get("/api/v1/dashboard")
check("Dashboard endpoint",      "total_detections" in d,              f"detections={d.get('total_detections')}")
check("Enrolled persons",        d.get("enrolled", 0) > 0,             f"enrolled={d.get('enrolled')}")

s = get("/api/v1/system/status")
inst = s.get("installations", [{}])[0] if s.get("installations") else {}
check("System status table",     bool(inst),                            f"host={inst.get('hostname')} online={inst.get('online')}")
check("Heartbeat recorded",      inst.get("online") == True,           f"minutes_ago={inst.get('minutes_ago',999)}")

cams = get("/api/v1/cameras")
cam_list = cams.get("cameras", [])
check("Cameras endpoint",        len(cam_list) > 0,                    f"{len(cam_list)} cameras in DB")

ev = get("/api/v1/events?limit=1&hours=24")
check("Events endpoint",         "events" in ev,                       f"total={ev.get('total_count')}")

att = get("/api/v1/attendance?limit=1")
check("Attendance endpoint",     "error" not in att,                   "OK")

unk = get("/api/v1/unknown-persons?limit=1")
check("Unknowns endpoint",       "unknown_persons" in unk,             f"total={unk.get('total_count', unk.get('count', 'ok'))}")

oc = get("/api/v1/org/config")
check("Org config endpoint",     oc.get("is_configured") == True,      f"org={oc.get('org_id')}")

diag = get("/api/v1/diagnostics")
check("Diagnostics endpoint",    "lines" in diag,                      f"{diag.get('count',0)} log lines")

passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
print("=" * 60)
print(f"RESULT: {passed}/{len(results)} passed — {'ALL PASS' if failed == 0 else f'{failed} FAILED'}")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)

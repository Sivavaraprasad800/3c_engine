"""Restore settings to what was working at 11AM."""
import os, sys, urllib.request, json
for line in open(".env","r",encoding="utf-8-sig"):
    l=line.strip()
    if l and not l.startswith("#") and "=" in l:
        k,v=l.split("=",1); os.environ.setdefault(k.strip(),v.strip())

settings = {
    "face_threshold": 0.45,
    "suspected_threshold": 0.37,
    "blacklist_threshold": 0.35,
    "visitor_threshold": 0.50,
    "dedup_threshold": 0.65,
    "camera_cooldown": 120,
    "global_cooldown": 300,
    "dedup_seconds": 60,
    "known_suppress_seconds": 60,
    "camera_unknown_cooldown": 15,
}
data = json.dumps(settings).encode()
req = urllib.request.Request("http://localhost:8001/api/v1/settings/system",
    data=data, headers={"Content-Type":"application/json"}, method="PATCH")
r = urllib.request.urlopen(req, timeout=5)
result = json.loads(r.read())
print("Settings restored:")
for k,v in settings.items():
    print(f"  {k:<30} = {v}")

"""
Fix 3MP camera RTSP URLs: change /live (sub-stream) to main stream.
Only changes cameras that use /live path - leaves 6MP/8MP cameras untouched.
Also updates face detection settings for ALL cameras.
"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pymysql

DB_HOST = os.environ.get("DB_HOST", "zdotapps-devenviron.cvuouqwaej9d.ap-south-1.rds.amazonaws.com")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "3c_dev_user")
DB_PASS = os.environ.get("DB_PASSWORD", "2H&5bQU2*)J)")
DB_NAME = os.environ.get("DB_NAME", "3C_Z_ATTEND_AI")

conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME)
cur = conn.cursor(pymysql.cursors.DictCursor)

# 1. Show ALL cameras and their RTSP URLs
print("=" * 80)
print("ALL CAMERAS AND RTSP URLS:")
print("=" * 80)
cur.execute("SELECT id, name, rtsp_url FROM 3c_eng_cameras ORDER BY id")
cameras = cur.fetchall()
for cam in cameras:
    url = cam["rtsp_url"] or ""
    is_live = "/live" in url.lower()
    flag = " <<<-- SUB-STREAM (needs fix)" if is_live else ""
    print(f"  {cam['id']:30s} | {cam['name']:25s} | {url[:70]}{flag}")

# 2. Find3MP cameras with /live sub-stream and fix them
print("\n" + "=" * 80)
print("FIXING 3MP CAMERAS (changing /live to main stream):")
print("=" * 80)

fixed = 0
for cam in cameras:
    url = cam["rtsp_url"] or ""
    if "/live" not in url.lower():
        continue

    new_url = url.replace("/live", "/cam/realmonitor?channel=1&subtype=0")

    print(f"\n  Camera: {cam['id']} ({cam['name']})")
    print(f"  OLD: {url}")
    print(f"  NEW: {new_url}")

    cur.execute(
        "UPDATE 3c_eng_cameras SET rtsp_url = %s WHERE id = %s",
        (new_url, cam["id"])
    )
    fixed += 1

conn.commit()
print(f"\n  Fixed {fixed} camera(s) from /live to main stream")

# 3. Update face settings for ALL cameras
print("\n" + "=" * 80)
print("UPDATING FACE SETTINGS (wider angles + lower threshold):")
print("=" * 80)

cur.execute("""
    UPDATE 3c_eng_cameras SET
        face_confidence = LEAST(face_confidence, 0.4),
        min_yaw = LEAST(min_yaw, -45),
        max_yaw = GREATEST(max_yaw, 45),
        min_pitch = LEAST(min_pitch, -25),
        max_pitch = GREATEST(max_pitch, 25)
""")
updated = cur.rowcount
conn.commit()
print(f"  Updated {updated} camera(s)")

# 4. Show final state
print("\n" + "=" * 80)
print("FINAL STATE:")
print("=" * 80)
cur.execute("SELECT id, name, rtsp_url, face_confidence, min_yaw, max_yaw, min_pitch, max_pitch FROM 3c_eng_cameras ORDER BY id")
for cam in cur.fetchall():
    url = cam["rtsp_url"] or ""
    print(f"  {cam['id']:30s} | conf={cam['face_confidence']} yaw=[{cam['min_yaw']},{cam['max_yaw']}] pitch=[{cam['min_pitch']},{cam['max_pitch']}] | {url[:65]}")

cur.close()
conn.close()
print("\nDONE! Restart server to apply changes.")

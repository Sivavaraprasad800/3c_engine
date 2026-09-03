"""
Test RTSP stream URLs for UTPL cameras.
Tries multiple main-stream paths to find the one that gives full resolution.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import cv2

# Test with Studio-CAM2 as sample
BASE = "rtsp://admin:utpl%40123@172.16.3.119:554"

STREAM_PATHS = [
    ("/cam/realmonitor?channel=1&subtype=0", "Dahua main stream"),
    ("/cam/realmonitor?channel=1&subtype=1", "Dahua sub stream"),
    ("/h264", "H.264 main"),
    ("/h264/ch1/main/av_stream", "H264 ch1 main"),
    ("/live", "Live sub-stream (original)"),
    ("/1", "Channel 1 simple"),
    ("/Streaming/Channels/1", "Hikvision-style"),
    ("/video1", "Video1"),
]

print("=" * 70)
print("Testing RTSP URLs for Studio-CAM2 (172.16.3.119)")
print("=" * 70)

for path, desc in STREAM_PATHS:
    url = BASE + path
    print(f"\n  Testing: {desc}")
    print(f"  URL: {url}")

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"  Result: CANNOT CONNECT")
        continue

    # Try to grab a frame
    cap.grab()
    ret, frame = cap.retrieve()
    cap.release()

    if ret and frame is not None:
        h, w = frame.shape[:2]
        mp = w * h / 1_000_000
        quality = "EXCELLENT" if mp > 2 else "GOOD" if mp > 0.5 else "LOW"
        print(f"  Result: OK - {w}x{h} ({mp:.1f}MP) [{quality}]")
    else:
        print(f"  Result: CONNECTED but NO FRAME")

print("\n" + "=" * 70)
print("DONE - use the URL path that gives the highest resolution")
print("=" * 70)

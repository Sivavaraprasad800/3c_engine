"""
camera_processor.py — Multi-Camera FRS Processor
Each camera runs in its own thread.
Auto-fetches camera list from server (Colab GPU or local).
Pushes live frames for dashboard streaming.
Sends frames for GPU AI recognition.

Run:
  python camera_processor.py --server "https://xxxx.trycloudflare.com"
"""

import os
import cv2
import numpy as np
import requests
import time
import argparse
import threading
import queue
from datetime import datetime

# Stable RTSP: force TCP + fast timeout (fixes RTP packet loss / 30s hangs)
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;5000000|max_delay;500000"
)

# ── CONFIG ────────────────────────────────────────────────────────
SERVER_URL             = "http://localhost:8001"   # Local FRS server (AI_MODE=1) — port 8001 (8000 = Django)
# Change to your Render URL ONLY if running cameras separate from the AI server:
# SERVER_URL = "https://frs-ai-model.onrender.com"
PROCESS_EVERY_N_FRAMES = 5      # GPU recognition every 5th frame (less load)
LIVE_EVERY_N_FRAMES    = 2      # Live push every 2nd frame
FRAME_WIDTH            = 640
FRAME_HEIGHT           = 360
RECOGNITION_THRESHOLD  = None  # None = use server's system settings


class SingleCameraProcessor:
    """Handles one RTSP camera — runs in its own thread."""

    def __init__(self, cam: dict):
        self.cam_id    = cam["id"]
        self.rtsp_url  = cam["rtsp_url"]
        self.cam_type  = cam.get("camera_type", "checkin")
        self.det_zone  = cam.get("detection_zone", [])
        self.face_conf = cam.get("face_confidence", 0.5)
        self.fps_target = cam.get("fps", 30)

        self.frame_count  = 0
        self.fps          = 0.0
        self.last_results = []
        self.result_lock  = threading.Lock()
        self.rec_queue    = queue.Queue(maxsize=1)
        self.live_queue   = queue.Queue(maxsize=1)
        self.stop_event   = threading.Event()

        print(f"[{self.cam_id}] Initialized — {self.rtsp_url}")

    def send_for_recognition(self, frame):
        try:
            _, enc = cv2.imencode(
                '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            params = {
                    "camera_id":     self.cam_id,
                    "save_snapshot": "true"
                }
            if RECOGNITION_THRESHOLD is not None:
                params["threshold"] = RECOGNITION_THRESHOLD
            r = requests.post(
                f"{SERVER_URL}/api/v1/frd/recognize",
                files={"file": ("f.jpg", enc.tobytes(), "image/jpeg")},
                params=params,
                timeout=15.0   # increased for Colab GPU cold start
            )
            if r.status_code == 200:
                return r.json().get("recognitions", [])
        except requests.exceptions.Timeout:
            print(f"[{self.cam_id}] GPU timeout — skipping frame")
        except Exception as e:
            print(f"[{self.cam_id}] Recognize error: {e}")
        return []

    def push_live_frame(self, frame):
        try:
            small = cv2.resize(frame, (640, 360))
            _, enc = cv2.imencode(
                '.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 70])
            requests.post(
                f"{SERVER_URL}/api/v1/cameras/{self.cam_id}/frame",
                files={"file": ("f.jpg", enc.tobytes(), "image/jpeg")},
                timeout=2.0
            )
        except Exception:
            pass

    def recognition_worker(self):
        while not self.stop_event.is_set():
            try:
                frame = self.rec_queue.get(timeout=1.0)
                results = self.send_for_recognition(frame)
                with self.result_lock:
                    self.last_results = results
            except queue.Empty:
                continue

    def live_push_worker(self):
        while not self.stop_event.is_set():
            try:
                frame = self.live_queue.get(timeout=1.0)
                self.push_live_frame(frame)
            except queue.Empty:
                continue

    def run(self):
        threading.Thread(
            target=self.recognition_worker, daemon=True).start()
        threading.Thread(
            target=self.live_push_worker, daemon=True).start()

        while not self.stop_event.is_set():
            cap = cv2.VideoCapture(self.rtsp_url)
            if not cap.isOpened():
                print(f"[{self.cam_id}] Cannot open — retry in 5s")
                time.sleep(5)
                continue

            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"[{self.cam_id}] Stream opened")
            last_fps_time = time.time()
            fps_count = 0

            while not self.stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    print(f"[{self.cam_id}] Frame fail — reconnect")
                    break

                self.frame_count += 1
                fps_count += 1
                now = time.time()
                if now - last_fps_time >= 1.0:
                    self.fps = fps_count / (now - last_fps_time)
                    fps_count = 0
                    last_fps_time = now

                pf = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

                # Push live frame to server for dashboard streaming
                if self.frame_count % LIVE_EVERY_N_FRAMES == 0:
                    if not self.live_queue.full():
                        self.live_queue.put_nowait(pf.copy())

                # Send for GPU AI recognition
                if self.frame_count % PROCESS_EVERY_N_FRAMES == 0:
                    if self.rec_queue.empty():
                        self.rec_queue.put_nowait(pf.copy())

            cap.release()
            if not self.stop_event.is_set():
                time.sleep(3)

        print(f"[{self.cam_id}] Stopped")

    def stop(self):
        self.stop_event.set()


class MultiCameraProcessor:
    """
    Fetches camera list from server.
    Starts one thread per camera automatically.
    Polls server every 30s for new/removed cameras.
    """

    def __init__(self):
        self.processors = {}   # cam_id -> SingleCameraProcessor
        self.threads    = {}   # cam_id -> Thread
        self.lock       = threading.Lock()

    def fetch_cameras(self):
        try:
            r = requests.get(
                f"{SERVER_URL}/api/v1/cameras", timeout=5)
            if r.status_code == 200:
                return [c for c in r.json().get("cameras", [])
                        if c.get("enabled", True)]
        except Exception as e:
            print(f"[Manager] Cannot fetch cameras: {e}")
        return []

    def start_camera(self, cam: dict):
        cam_id = cam["id"]
        with self.lock:
            if cam_id in self.processors:
                return  # already running
            proc = SingleCameraProcessor(cam)
            t    = threading.Thread(target=proc.run, daemon=True)
            self.processors[cam_id] = proc
            self.threads[cam_id]    = t
            t.start()
            print(f"[Manager] Started camera: {cam_id}")

    def stop_camera(self, cam_id: str):
        with self.lock:
            if cam_id in self.processors:
                self.processors[cam_id].stop()
                self.threads[cam_id].join(timeout=5)
                del self.processors[cam_id]
                del self.threads[cam_id]
                print(f"[Manager] Stopped camera: {cam_id}")

    def run(self):
        print(f"[Manager] Connecting to server: {SERVER_URL}")
        print("[Manager] Fetching camera list...")

        while True:
            cameras = self.fetch_cameras()
            current_ids = set(self.processors.keys())
            server_ids  = {c["id"] for c in cameras}

            # Start new cameras
            for cam in cameras:
                if cam["id"] not in current_ids:
                    self.start_camera(cam)

            # Stop removed cameras
            for cam_id in current_ids - server_ids:
                self.stop_camera(cam_id)

            if cameras:
                print(f"[Manager] Running {len(self.processors)} "
                      f"camera(s): {list(self.processors.keys())}")
            else:
                print("[Manager] No cameras found on server. "
                      "Add cameras via dashboard then retry.")

            time.sleep(30)  # check for new cameras every 30s


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Camera FRS Processor — GPU Mode")
    parser.add_argument(
        '--server', default='http://localhost:8001',
        help='Colab Cloudflare URL or localhost:8001')
    parser.add_argument(
        '--process-every', type=int, default=3,
        help='Send every N frames for AI recognition')
    args = parser.parse_args()

    global SERVER_URL, PROCESS_EVERY_N_FRAMES
    SERVER_URL             = args.server
    PROCESS_EVERY_N_FRAMES = args.process_every

    is_gpu = ("trycloudflare" in SERVER_URL or "ngrok" in SERVER_URL)
    print("=" * 55)
    print(f"  FRS Multi-Camera Processor")
    print(f"  Server : {SERVER_URL}")
    print(f"  Mode   : {'GPU (Colab)' if is_gpu else 'Local CPU'}")
    print(f"  Cameras: auto-fetched from server")
    print("=" * 55)

    manager = MultiCameraProcessor()
    manager.run()


if __name__ == "__main__":
    main()

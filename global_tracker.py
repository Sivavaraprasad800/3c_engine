"""
global_tracker.py — Multi-Camera Global Person ID manager + Room Occupancy

Connects detections across cameras into ONE global identity per person:

  Known persons   -> face recognition person_id -> stable "PERSON_0001" Global ID
  Unknown persons -> face-embedding Re-ID gallery (cosine similarity within a
                     time window) -> "UNK_0001" Global ID, reused across cameras
                     when the same face reappears.

Also maintains live room occupancy:
  camera_type="checkin"  + room_id  -> ENTRY (+1)
  camera_type="checkout" + room_id  -> EXIT  (-1)

Thread-safe: called from multiple camera worker threads concurrently.
"""

import threading
import time
from datetime import datetime
from collections import deque

import numpy as np


# ─── CONFIG ──────────────────────────────────────────────────────
UNKNOWN_MATCH_SIMILARITY = 0.50   # cosine sim threshold for unknown Re-ID
UNKNOWN_MATCH_WINDOW_S   = 600    # match unknowns seen within last 10 min
                                  # (mandatory: same unknown face must keep the
                                  #  SAME Global ID across all cameras)
GALLERY_MAX_PER_DAY      = 500    # cap gallery size
MOVEMENT_LOG_MAX         = 300    # in-memory movement ring buffer


def _cosine_sim(a, b):
    try:
        a = np.asarray(a, dtype=np.float32)
        b = np.asarray(b, dtype=np.float32)
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na < 1e-6 or nb < 1e-6:
            return 0.0
        return float(np.dot(a, b) / (na * nb))
    except Exception:
        return 0.0


class GlobalIDManager:
    """
    Central identity mapper. Usage:

        gid = manager.register(person_id=..., person_name=..., person_type=...,
                               embedding=..., camera_id=...)
    Returns a global ID string like "PERSON_0007" or "UNK_20260826_003".
    """
    def __init__(self):
        self._lock = threading.Lock()
        # known: person_id -> global_id (stable mapping)
        self._known_map = {}
        # unknown gallery: list of dicts {global_id, embedding, last_seen, cameras}
        self._gallery = []
        # daily unknown counter
        self._unk_counter = 0
        self._unk_day = datetime.now().strftime("%Y%m%d")
        # global_id -> track info (for live view)
        self._tracks = {}
        # movement log (ring buffer)
        self.movements = deque(maxlen=MOVEMENT_LOG_MAX)

    # ── main entry ────────────────────────────────────────────
    def register(self, camera_id, person_id=None, person_name="Unknown",
                 person_type="unknown", embedding=None, confidence=0.0,
                 snapshot_b64=None):
        """Register one detection. Returns (global_id, is_new_global_id)."""
        now = time.time()
        now_iso = datetime.now().isoformat()
        with self._lock:
            if person_id is not None:
                gid = self._known_map.get(person_id)
                if gid is None:
                    gid = f"PERSON_{int(person_id):04d}"
                    self._known_map[person_id] = gid
                new = self._tracks.get(gid) is None
                self._update_track(gid, person_name, person_type, camera_id,
                                   now, now_iso, confidence, snapshot_b64)
                self._record_movement(gid, person_name, camera_id, now, now_iso)
                return gid, new

            # ── Unknown person Re-ID ──────────────────────────
            self._rollover_day()
            gid = self._match_unknown_gallery(embedding, camera_id, now)
            if gid is None:
                self._unk_counter += 1
                gid = f"UNK_{self._unk_day}_{self._unk_counter:03d}"
                new = True
            else:
                new = False
            if embedding is not None and len(self._gallery) < GALLERY_MAX_PER_DAY:
                self._gallery.append({
                    "global_id": gid,
                    "embedding": embedding,
                    "last_seen": now,
                    "camera_id": camera_id,
                })
            self._update_track(gid, "Unknown", person_type or "unknown",
                               camera_id, now, now_iso, confidence, snapshot_b64)
            self._record_movement(gid, "Unknown", camera_id, now, now_iso)
            return gid, new

    # ── internals ─────────────────────────────────────────────
    def _rollover_day(self):
        today = datetime.now().strftime("%Y%m%d")
        if today != self._unk_day:
            self._unk_day = today
            self._unk_counter = 0
            self._gallery = []   # fresh day, fresh gallery

    def _match_unknown_gallery(self, embedding, camera_id, now):
        """Return existing global_id if this unknown face was recently seen."""
        if embedding is None:
            return None
        best_gid, best_sim = None, 0.0
        for g in self._gallery:
            if now - g["last_seen"] > UNKNOWN_MATCH_WINDOW_S:
                continue
            sim = _cosine_sim(embedding, g["embedding"])
            if sim > best_sim:
                best_sim, best_gid = sim, g["global_id"]
        if best_gid is not None and best_sim >= UNKNOWN_MATCH_SIMILARITY:
            # refresh gallery entries for this gid (latest embedding wins)
            for g in self._gallery:
                if g["global_id"] == best_gid:
                    g["last_seen"] = now
                    g["camera_id"] = camera_id
                    if embedding is not None:
                        g["embedding"] = embedding
            return best_gid
        return None

    def _update_track(self, gid, name, ptype, camera_id, now, now_iso,
                      confidence, snapshot_b64):
        t = self._tracks.get(gid)
        if t is None:
            t = {
                "global_id":   gid,
                "person_name": name,
                "person_type": ptype,
                "first_seen":  now_iso,
                "last_seen":   now_iso,
                "last_camera": camera_id,
                "cameras":     [camera_id],
                "confidence":  confidence,
                "snapshot":    snapshot_b64,
                "_last_seen_ts": now,
            }
            self._tracks[gid] = t
            return
        # update existing track
        t["last_seen"] = now_iso
        t["last_camera"] = camera_id
        t["_last_seen_ts"] = now
        if name and name != "Unknown":
            t["person_name"] = name
        if confidence:
            t["confidence"] = confidence
        if snapshot_b64:
            t["snapshot"] = snapshot_b64
        if camera_id not in t["cameras"]:
            t["cameras"].append(camera_id)
            # keep only last 6 cameras in path
            del t["cameras"][:-6]

    def _record_movement(self, gid, name, camera_id, now, now_iso):
        self.movements.append({
            "global_id":  gid,
            "person_name": name,
            "camera_id":  camera_id,
            "timestamp":  now_iso,
            "_ts":        now,
        })

    # ── queries ───────────────────────────────────────────────
    def live_tracks(self, active_seconds=300, limit=100):
        """Tracks seen in the last `active_seconds`, newest first."""
        cutoff = time.time() - active_seconds
        with self._lock:
            tracks = [t for t in self._tracks.values()
                      if t["_last_seen_ts"] >= cutoff]
        tracks.sort(key=lambda t: t["_last_seen_ts"], reverse=True)
        out = []
        for t in tracks[:limit]:
            out.append({
                "global_id":   t["global_id"],
                "person_name": t["person_name"],
                "person_type": t["person_type"],
                "first_seen":  t["first_seen"],
                "last_seen":   t["last_seen"],
                "last_camera": t["last_camera"],
                "camera_path": list(t["cameras"]),
                "confidence":  round(t.get("confidence") or 0, 3),
                "snapshot":    t.get("snapshot"),
            })
        return out

    def recent_movements(self, limit=80):
        with self._lock:
            movs = list(self.movements)
        movs.sort(key=lambda m: m["_ts"], reverse=True)
        return [{k: v for k, v in m.items() if not k.startswith("_")}
                for m in movs[:limit]]

    def get_snapshot(self, gid):
        """Latest face snapshot (b64) for a global id, or None."""
        with self._lock:
            t = self._tracks.get(gid)
            return t.get("snapshot") if t else None

    def stats(self):
        with self._lock:
            active = sum(1 for t in self._tracks.values()
                         if time.time() - t["_last_seen_ts"] < 300)
            known = sum(1 for g in self._tracks if g.startswith("PERSON_"))
            return {
                "active_tracks": active,
                "known_tracks": known,
                "unknown_tracks": len(self._tracks) - known,
                "gallery_size": len(self._gallery),
                "total_movements": len(self.movements),
            }


class RoomOccupancyManager:
    """
    Live room occupancy from camera entry/exit sightings.

    Rooms come from cameras' `room_id` field. A camera with
    camera_type="checkin" is an ENTRY door; "checkout" is an EXIT door.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._inside = {}     # room_id -> set of global_ids
        self._counters = {}   # room_id -> {"entries": int, "exits": int}
        # gid -> (room_id, direction, ts) — dedups re-triggering the SAME door
        self._last_room_seen = {}
        # (camera_id, gid) -> last zone/side seen for crossing detection
        self._zone_state = {}
        # (camera_id, gid) -> ts of last counted flip (debounce)
        self._flip_ts = {}
        # per-camera live counting stats (head-count cameras)
        self._cam_stats = {}   # camera_id -> {"in": int, "out": int, "inside": set}

    def _room_counters(self, room_id):
        return self._counters.setdefault(room_id, {"entries": 0, "exits": 0})

    def register(self, room_id, camera_id, camera_type, global_id,
                 person_name="Unknown", person_type="unknown",
                 confidence=0.0, snapshot_b64=None):
        """
        Feed one sighting into the room logic.
        Returns dict describing what happened:
          {"room_id":…, "direction":"entry"/"exit"/None, "inside":N, ...}
        """
        if not room_id:
            return None
        now = time.time()
        now_iso = datetime.now().isoformat()
        direction = None
        with self._lock:
            inside = self._inside.setdefault(room_id, set())
            counters = self._room_counters(room_id)

            # dedup: same person re-triggering the SAME door (room+direction) within 10s
            last = self._last_room_seen.get(global_id)
            if last and last[0] == room_id and now - last[2] < 10:
                # allow opposite direction through (quick entry→exit is legitimate)
                if not (camera_type in ("checkin", "checkout") and last[1] != camera_type):
                    return None
            self._last_room_seen[global_id] = (room_id, camera_type, now)

            if camera_type == "checkin":
                if global_id not in inside:
                    inside.add(global_id)
                    counters["entries"] += 1
                    direction = "entry"
            elif camera_type == "checkout":
                if global_id in inside:
                    inside.discard(global_id)
                    counters["exits"] += 1
                    direction = "exit"
                else:
                    # exited without tracked entry — still count the exit
                    counters["exits"] += 1
                    direction = "exit"

        if direction is None:
            return None
        return {
            "room_id":      room_id,
            "camera_id":    camera_id,
            "global_id":    global_id,
            "person_name":  person_name,
            "person_type":  person_type,
            "direction":    direction,
            "confidence":   confidence,
            "snapshot":     snapshot_b64,
            "inside_count": len(inside),
            "timestamp":    now_iso,
        }

    def register_zone(self, room_id, camera_id, global_id, zone,
                      person_name="Unknown", person_type="unknown",
                      confidence=0.0, snapshot_b64=None):
        """
        Zone-crossing counting for a SINGLE camera:
          person seen in ENTRY zone then EXIT zone  -> EXIT  (left the room)
          person seen in EXIT zone then ENTRY zone  -> ENTRY (entered the room)
        A crossing only counts when BOTH zones are crossed in sequence.
        Returns a movement dict on a valid crossing, else None.
        """
        if zone not in ("entry", "exit"):
            return None
        now = time.time()
        now_iso = datetime.now().isoformat()
        key = (camera_id, global_id)
        direction = None
        with self._lock:
            last = self._zone_state.get(key)
            if zone == "exit" and last == "entry":
                direction = "exit"    # entry point -> exit point = going OUT
            elif zone == "entry" and last == "exit":
                direction = "entry"   # exit point -> entry point = coming IN
            if last != zone:
                self._zone_state[key] = zone
            if direction is None:
                return None

            inside = self._inside.setdefault(room_id, set())
            counters = self._room_counters(room_id)
            if direction == "entry":
                if global_id in inside:
                    return None            # already counted inside
                inside.add(global_id)
                counters["entries"] += 1
            else:
                # every completed entry->exit crossing counts as an exit,
                # even if the person entered before tracking started
                inside.discard(global_id)
                counters["exits"] += 1

        return {
            "room_id":      room_id,
            "camera_id":    camera_id,
            "global_id":    global_id,
            "person_name":  person_name,
            "person_type":  person_type,
            "direction":    direction,
            "confidence":   confidence,
            "snapshot":     snapshot_b64,
            "inside_count": len(self._inside.get(room_id, set())),
            "timestamp":    now_iso,
        }

    def register_line(self, room_id, camera_id, global_id, side,
                      person_name="Unknown", person_type="unknown",
                      confidence=0.0, snapshot_b64=None):
        """
        Single-line head counting for ONE camera:

          The user draws ONE line across the camera view. Each detection is on
          one of two sides of the line (side = +1 or -1, from the cross product
          of the person's position with the line).

          When a person's side FLIPS between detections, they crossed the line:
            moved to side +1  -> IN   (+1 head)
            moved to side -1  -> OUT  (-1 head)

          Debounce: repeated flips within 4s are noise (face box wobble near
          the line) and are ignored.

        Returns a movement dict on a valid crossing, else None.
        """
        if side not in (1, -1):
            return None
        now = time.time()
        now_iso = datetime.now().isoformat()
        key = (camera_id, global_id)
        direction = None
        with self._lock:
            last = self._zone_state.get(key)
            if last is not None and last != side:
                # debounce rapid flips — face boxes wobble near the line
                last_flip = self._flip_ts.get(key, 0)
                if now - last_flip < 4:
                    return None
                direction = "in" if side == 1 else "out"
            if last != side:
                self._zone_state[key] = side
            if direction is None:
                return None
            self._flip_ts[key] = now

            inside = self._inside.setdefault(room_id, set())
            counters = self._room_counters(room_id)
            if direction == "in":
                if global_id in inside:
                    return None            # already counted inside
                inside.add(global_id)
                counters["entries"] += 1
            else:
                # every line crossing outward counts, even if the person
                # entered before tracking started
                inside.discard(global_id)
                counters["exits"] += 1

            # per-camera counting stats (for the camera live popup)
            cst = self._cam_stats.setdefault(camera_id, {"in": 0, "out": 0, "inside": set()})
            if direction == "in":
                cst["in"] += 1
                cst["inside"].add(global_id)
            else:
                cst["out"] += 1
                cst["inside"].discard(global_id)

        return {
            "room_id":      room_id,
            "camera_id":    camera_id,
            "global_id":    global_id,
            "person_name":  person_name,
            "person_type":  person_type,
            "direction":    direction,
            "confidence":   confidence,
            "snapshot":     snapshot_b64,
            "inside_count": len(self._inside.get(room_id, set())),
            "timestamp":    now_iso,
        }

    def cam_stats(self, camera_id):
        """Live per-camera counting stats: {in, out, inside_count}."""
        with self._lock:
            c = self._cam_stats.get(camera_id)
            if not c:
                return {"in": 0, "out": 0, "inside_count": 0}
            return {"in": c["in"], "out": c["out"], "inside_count": len(c["inside"])}

    def all_cam_stats(self):
        """Per-camera stats for every camera that has counted at least once."""
        with self._lock:
            return {cid: {"in": c["in"], "out": c["out"], "inside_count": len(c["inside"])}
                    for cid, c in self._cam_stats.items()}

    def snapshot(self, rooms):
        """Live occupancy for given rooms [{room_id, name, camera_ids, ...}]."""
        with self._lock:
            out = []
            for r in rooms:
                rid = r["room_id"]
                inside = self._inside.get(rid, set())
                c = self._counters.get(rid, {"entries": 0, "exits": 0})
                out.append({
                    **r,
                    "inside_count": len(inside),
                    "inside_ids":   sorted(inside)[:50],
                    "entries":      c["entries"],
                    "exits":        c["exits"],
                })
            return out

    def reset(self, room_id=None):
        with self._lock:
            if room_id:
                self._inside.pop(room_id, None)
                self._counters.pop(room_id, None)
            else:
                self._inside.clear()
                self._counters.clear()


# ─── SINGLETONS ──────────────────────────────────────────────────
global_id_manager = GlobalIDManager()
room_occupancy_manager = RoomOccupancyManager()

"""
face_engine.py — Face Recognition Engine
Uses InsightFace buffalo_l with det_size=(320,320) for speed
while maintaining full compatibility with existing enrolled embeddings.
Multi-index FAISS: Employee / Blacklist / Visitor
Multi-capture: 3-5 embeddings per person for better accuracy.
Quality gate: blur + face size + pose angle filtering.
"""

import os
from pathlib import Path
# ── CPU thread tuning — must be set BEFORE importing onnxruntime ──
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("ORT_NUM_THREADS", "4")

import cv2
import numpy as np
import faiss
from insightface.app import FaceAnalysis
import pickle
from typing import List, Dict, Optional, Tuple, Callable

# Lazy Face class — used for two-stage detect→filter→embed pipeline
try:
    from insightface.app.common import Face as _LazyFace
except Exception:
    _LazyFace = None


# ── QUALITY GATE CONSTANTS ──────────────────────────────────────
# Relaxed thresholds — accept more photos for enrollment
MIN_FACE_SIZE     = 20        # Catch smaller/distant faces — was 30, now 20 for 3MP cameras
BLUR_THRESHOLD    = 15.0      # accept slightly blurry images (was 80.0)
MAX_YAW           = 60.0      # allow side-facing photos (was 35.0)
MAX_PITCH         = 40.0      # allow tilted photos (was 20.0)
MAX_EMBEDDINGS_PER_PERSON = 5  # max embeddings stored per person


def check_face_quality(image: np.ndarray, bbox, landmarks=None) -> tuple:
    """
    Quality gate: checks face size, blur, and pose angle.
    Returns (is_good: bool, reason: str).
    Replicates zdotapps' frontal/quality filter.
    """
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1

    # Size check
    if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
        return False, f"face too small ({w}x{h})"

    # Blur check — Laplacian variance
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    crop = gray[max(0, y1):min(gray.shape[0], y2), max(0, x1):min(gray.shape[1], x2)]
    if crop.size == 0:
        return False, "empty crop"
    laplacian_var = cv2.Laplacian(crop, cv2.CV_64F).var()
    if laplacian_var < BLUR_THRESHOLD:
        return False, f"blurry ({laplacian_var:.0f})"

    # Pose check from landmarks (5-point facial landmarks)
    if landmarks and len(landmarks) >= 5:
        eye_l, eye_r, nose = landmarks[0], landmarks[1], landmarks[2]
        mouth_l, mouth_r = landmarks[3], landmarks[4]

        # Yaw: horizontal offset of nose relative to eyes
        eye_center_x = (eye_l[0] + eye_r[0]) / 2.0
        eye_dist = abs(eye_r[0] - eye_l[0])
        if eye_dist > 1:
            yaw = abs((nose[0] - eye_center_x) / eye_dist * 75.0)
            if yaw > MAX_YAW:
                return False, f"not frontal (yaw={yaw:.0f})"

        # Pitch: vertical offset
        eye_center_y = (eye_l[1] + eye_r[1]) / 2.0
        mouth_center_y = (mouth_l[1] + mouth_r[1]) / 2.0
        eye_mouth_dist = abs(mouth_center_y - eye_center_y)
        if eye_mouth_dist > 1:
            pitch = abs((nose[1] - eye_center_y) / eye_mouth_dist - 0.45) * 80.0
            if pitch > MAX_PITCH:
                return False, f"not frontal (pitch={pitch:.0f})"

    return True, "ok"


class FaceIndex:
    """
    FAISS-based face index supporting multiple embeddings per person.
    Each person can have up to MAX_EMBEDDINGS_PER_PERSON embeddings.
    Search aggregates across all embeddings per person for best match.
    Embeddings are stored in MySQL 3c_eng_face_embeddings for portability.
    """

    # MySQL connection config — set once at app startup
    _mysql_config: dict = {}

    @classmethod
    def set_mysql_config(cls, host, port, user, password, db):
        cls._mysql_config = {"host":host,"port":int(port),"user":user,
                             "password":password,"database":db,"charset":"utf8mb4",
                             "connect_timeout":10}

    def _get_mysql(self):
        """Get a fresh MySQL connection."""
        if not self._mysql_config:
            return None
        try:
            import pymysql
            return pymysql.connect(**self._mysql_config)
        except Exception as e:
            print(f"[FaceIndex] MySQL connect failed: {e}")
            return None

    def __init__(self, index_path: str, map_path: str, watchlist: str = "employee"):
        self.dim        = 512
        self.index_path = index_path
        self.map_path   = map_path
        self.watchlist  = watchlist
        self.id_map: Dict[int, dict] = {}
        self.next_id    = 0

        # Try loading from MySQL first (embeddings now correctly exported with det_size=320)
        loaded_from_mysql = False  # Disabled — use local .faiss which has all 110 persons
        # MySQL only has 79 persons (missing 31 that had no images for re-export)

        if not loaded_from_mysql:
            # Fall back to local .faiss + .pkl files
            if os.path.exists(index_path):
                self.index = faiss.read_index(index_path)
                with open(map_path, 'rb') as f:
                    data = pickle.load(f)
                    self.id_map  = data['id_map']
                    self.next_id = data['next_id']
            else:
                self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))
        else:
            # Also save to local files as backup
            self._save()

    def _load_from_mysql(self) -> bool:
        """Load all embeddings from MySQL into FAISS. Returns True if successful."""
        conn = self._get_mysql()
        if not conn:
            return False
        try:
            import json as _json
            cur = conn.cursor()
            cur.execute("""
                SELECT id, person_id, name, embedding
                FROM 3c_eng_face_embeddings
                WHERE watchlist = %s
                ORDER BY id
            """, (self.watchlist,))
            rows = cur.fetchall()
            conn.close()

            if not rows:
                return False

            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))
            self.id_map = {}
            self.next_id = 0

            for db_id, person_id, name, emb_json in rows:
                try:
                    emb = np.array(_json.loads(emb_json), dtype=np.float32)
                    if emb.shape[0] != 512:
                        continue
                    fid = self.next_id
                    self.index.add_with_ids(emb.reshape(1,-1), np.array([fid], dtype=np.int64))
                    self.id_map[fid] = {"person_id": person_id, "name": name, "db_id": db_id}
                    self.next_id += 1
                except Exception:
                    continue

            print(f"[FaceIndex] Loaded {self.index.ntotal} {self.watchlist} embeddings from MySQL")
            return True

        except Exception as e:
            print(f"[FaceIndex] MySQL load failed: {e}")
            try: conn.close()
            except: pass
            return False

    def add(self, embedding: np.ndarray, person_id: int, name: str) -> dict:
        """Add an embedding. Allows up to MAX_EMBEDDINGS_PER_PERSON per person.
        Also saves to MySQL 3c_eng_face_embeddings for portability."""
        emb = self._normalize(embedding)

        # Count existing embeddings for this person
        existing = [fid for fid, info in self.id_map.items()
                    if info['person_id'] == person_id]
        count = len(existing)

        # Check if this is a near-duplicate of an existing embedding for same person
        if count > 0 and self.index.ntotal > 0:
            scores, ids = self.index.search(emb, min(count, 5))
            for i, fid in enumerate(ids[0]):
                fid = int(fid)
                if fid in self.id_map and self.id_map[fid]['person_id'] == person_id:
                    if float(scores[0][i]) > 0.98:
                        return {"success": True, "note": "duplicate_skipped",
                                "total": self.index.ntotal,
                                "total_enrolled": self.index.ntotal,
                                "embeddings_for_person": count}

        # Enforce max embeddings per person — remove oldest if at limit
        if count >= MAX_EMBEDDINGS_PER_PERSON:
            oldest_fid = existing[0]  # first added = oldest
            # Remove from MySQL
            old_db_id = self.id_map[oldest_fid].get("db_id")
            if old_db_id:
                self._mysql_delete_embedding(old_db_id)
            self.index.remove_ids(np.array([oldest_fid], dtype=np.int64))
            del self.id_map[oldest_fid]
            count -= 1

        fid = self.next_id
        self.index.add_with_ids(emb, np.array([fid], dtype=np.int64))

        # Save to MySQL and get db_id
        import json as _json
        db_id = self._mysql_save_embedding(person_id, name, _json.dumps(emb[0].tolist()))

        self.id_map[fid] = {"person_id": person_id, "name": name, "db_id": db_id}
        self.next_id += 1
        self._save()
        return {"success": True, "total": self.index.ntotal,
                "total_enrolled": self.index.ntotal,
                "embeddings_for_person": count + 1}

    def _mysql_save_embedding(self, person_id: int, name: str, emb_json: str) -> int:
        """Save one embedding to MySQL. Returns db_id or 0 on failure."""
        conn = self._get_mysql()
        if not conn:
            return 0
        try:
            from datetime import datetime
            cur = conn.cursor()
            cur.execute("""INSERT INTO 3c_eng_face_embeddings
                (person_id, name, watchlist, embedding, created_at)
                VALUES(%s,%s,%s,%s,%s)""",
                (person_id, name, self.watchlist, emb_json, datetime.now().isoformat()))
            conn.commit()
            db_id = cur.lastrowid
            conn.close()
            return db_id
        except Exception as e:
            print(f"[FaceIndex] MySQL save failed: {e}")
            try: conn.close()
            except: pass
            return 0

    def _mysql_delete_embedding(self, db_id: int):
        """Delete one embedding from MySQL by db_id."""
        conn = self._get_mysql()
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM 3c_eng_face_embeddings WHERE id=%s", (db_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[FaceIndex] MySQL delete failed: {e}")
            try: conn.close()
            except: pass

    def search(self, embedding: np.ndarray, threshold: float) -> Optional[dict]:
        """
        Search with multi-embedding aggregation.
        Looks at top-10 matches, groups by person_id, picks best overall.
        """
        if self.index.ntotal == 0:
            return None
        emb = self._normalize(embedding)

        # Search top-10 to catch multiple embeddings of same person
        k = min(10, self.index.ntotal)
        scores, ids = self.index.search(emb, k)

        # Group best score per person
        best_per_person: Dict[int, dict] = {}
        for i in range(k):
            fid = int(ids[0][i])
            score = float(scores[0][i])
            if fid not in self.id_map:
                continue
            info = self.id_map[fid]
            pid = info['person_id']
            if pid not in best_per_person or score > best_per_person[pid]['confidence']:
                best_per_person[pid] = {
                    "person_id": pid,
                    "name": info['name'],
                    "confidence": round(score, 4),
                }

        # Pick the overall best person
        if not best_per_person:
            return None
        best = max(best_per_person.values(), key=lambda x: x['confidence'])
        if best['confidence'] >= threshold:
            return best
        return None

    def count_embeddings(self, person_id: int) -> int:
        """Count how many embeddings a person has."""
        return sum(1 for info in self.id_map.values() if info['person_id'] == person_id)

    def replace_worst_template(self, person_id: int, new_embedding: np.ndarray, min_similarity: float = 0.65) -> dict:
        """
        CONTINUOUS LEARNING: Replace the worst template for a person with a better one.
        Called when a person is detected with high confidence on CCTV.
        This makes templates converge to 'how this person looks on THIS camera'.
        
        Returns: {replaced: bool, reason: str, similarity: float}
        """
        emb = self._normalize(new_embedding)
        
        # Find all existing embeddings for this person
        existing_fids = [fid for fid, info in self.id_map.items()
                         if info['person_id'] == person_id]
        
        if not existing_fids:
            # No templates exist — add as first template
            return {"replaced": False, "reason": "no_existing_templates", "similarity": 0}
        
        # Search existing templates for similarity to new embedding
        if self.index.ntotal == 0:
            return {"replaced": False, "reason": "empty_index", "similarity": 0}
        
        k = min(len(existing_fids), 10)
        scores, ids = self.index.search(emb, k)
        
        # Find best and worst similarity among this person's templates
        best_score = 0.0
        worst_score = 1.0
        worst_fid = None
        best_fid = None
        
        for i in range(k):
            fid = int(ids[0][i])
            if fid not in self.id_map or self.id_map[fid]['person_id'] != person_id:
                continue
            score = float(scores[0][i])
            if score > best_score:
                best_score = score
                best_fid = fid
            if score < worst_score:
                worst_score = score
                worst_fid = fid
        
        # Don't update if new embedding is too different from existing (might be wrong match)
        if best_score < min_similarity:
            return {"replaced": False, "reason": "low_similarity", "similarity": round(best_score, 4)}
        
        # Don't update if new embedding is worse than ALL existing templates
        if worst_fid is None or best_score < worst_score:
            return {"replaced": False, "reason": "no_improvement", "similarity": round(best_score, 4)}
        
        # Replace the WORST template with the new one
        old_db_id = self.id_map[worst_fid].get("db_id")
        if old_db_id:
            self._mysql_delete_embedding(old_db_id)
        self.index.remove_ids(np.array([worst_fid], dtype=np.int64))
        del self.id_map[worst_fid]
        
        # Add new template
        import json as _json
        fid = self.next_id
        self.index.add_with_ids(emb, np.array([fid], dtype=np.int64))
        db_id = self._mysql_save_embedding(person_id, self.id_map.get(best_fid, {}).get("name", ""), _json.dumps(emb[0].tolist()))
        self.id_map[fid] = {"person_id": person_id, "name": self.id_map.get(best_fid, {}).get("name", ""), "db_id": db_id}
        self.next_id += 1
        self._save()
        
        return {"replaced": True, "reason": "worst_template_replaced",
                "similarity": round(best_score, 4), "replaced_worst_score": round(worst_score, 4)}

    def remove(self, person_id: int) -> int:
        ids_to_remove = [fid for fid, info in self.id_map.items()
                         if info['person_id'] == person_id]
        for fid in ids_to_remove:
            self.index.remove_ids(np.array([fid], dtype=np.int64))
            del self.id_map[fid]
        if ids_to_remove:
            self._save()
        return len(ids_to_remove)

    def _normalize(self, emb: np.ndarray) -> np.ndarray:
        emb = np.array(emb, dtype=np.float32).flatten()
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb.reshape(1, -1)

    def _save(self):
        faiss.write_index(self.index, self.index_path)
        with open(self.map_path, 'wb') as f:
            pickle.dump({'id_map': self.id_map, 'next_id': self.next_id}, f)

    @property
    def total(self) -> int:
        return self.index.ntotal


class FaceRecognitionEngine:
    """
    InsightFace buffalo_l with det_size=(320,320).
    Multi-capture: stores up to 5 embeddings per person.
    Quality gate: rejects blurry/tiny/non-frontal faces.
    """

    def __init__(self, det_size: Tuple[int, int] = (320, 320)):
        import onnxruntime as ort
        available = ort.get_available_providers()
        if 'CUDAExecutionProvider' in available:
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            print("[FaceEngine] Using CUDA GPU")
        else:
            providers = ['CPUExecutionProvider']
            print(f"[FaceEngine] Using CPU ({os.cpu_count()} cores)")

        # ONNX session options for maximum CPU throughput
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.intra_op_num_threads = 2    # threads per inference
        so.inter_op_num_threads = 4    # parallel operations
        so.execution_mode = ort.ExecutionMode.ORT_PARALLEL

        # Use buffalo_l — MATCHES the model used to build face_index.faiss
        # buffalo_s would produce DIFFERENT embeddings → low similarity → Unknown
        # buffalo_l: 120ms/frame, 99.83% accuracy
        _model = "buffalo_l"
        print(f"[FaceEngine] Loading InsightFace {_model} (det_size={det_size[0]}x{det_size[1]})...")

        self.app = FaceAnalysis(name=_model, providers=providers,
                               allowed_modules=['detection', 'recognition'],
                               session_options=so)
        self.app.prepare(ctx_id=-1, det_size=det_size)
        self.dim = 512

        self.employee_index  = FaceIndex("face_index.faiss",     "id_map.pkl",         watchlist="employee")
        self.blacklist_index = FaceIndex("blacklist_index.faiss", "blacklist_map.pkl",  watchlist="blacklist")
        self.visitor_index   = FaceIndex("visitor_index.faiss",   "visitor_map.pkl",    watchlist="visitor")

        emp_total = self.employee_index.total
        blk_total = self.blacklist_index.total
        vis_total = self.visitor_index.total
        print(f"[FaceEngine] Employees: {emp_total} embeddings | "
              f"Blacklist: {blk_total} | "
              f"Visitors: {vis_total}")

        # ── CRITICAL: Warn if all indexes are empty ──────────────
        if emp_total == 0 and blk_total == 0 and vis_total == 0:
            print("[FaceEngine] ⚠️  ALL FAISS INDEXES ARE EMPTY!")
            print("[FaceEngine] ⚠️  No face embeddings loaded — ALL faces will be 'Unknown'.")
            print("[FaceEngine] ⚠️  Fix: Run POST /api/v1/frd/bulk-enroll-folders")
            print("[FaceEngine] ⚠️       or enroll persons via the dashboard.")
        elif emp_total < 10:
            print(f"[FaceEngine] ⚠️  Only {emp_total} employee embeddings — consider enrolling more photos per person (3-5 photos recommended)")

        print("[FaceEngine] Ready!")

    def detect_and_analyze(self, image: np.ndarray) -> List[dict]:
        faces = self.app.get(image)
        results = []
        for face in faces:
            results.append({
                "bbox":       face.bbox.astype(int).tolist(),
                "confidence": float(face.det_score),
                "embedding":  face.embedding,
                "landmarks":  face.kps.tolist() if face.kps is not None else None,
            })
        return results

    def recognize(self, image: np.ndarray, threshold: float = 0.50,
                  suspected_threshold: float = 0.37,
                  blacklist_threshold: float = 0.35,
                  visitor_threshold: float = 0.50,
                  face_prefilter: Optional[Callable] = None) -> List[dict]:
        """
        Two-stage recognition pipeline:
          Stage 1: SCRFD detection only.
          Stage 2 (optional): face_prefilter(bbox, det_score, landmarks) —
              faces rejected here SKIP embedding extraction entirely
              (huge CPU saving when detection zones / pose limits are active).
          Stage 3: ArcFace embedding + index search for surviving faces only.
        Falls back to the one-shot app.get() pipeline if the lazy path fails.
        """
        faces = None
        if face_prefilter is not None and _LazyFace is not None:
            try:
                bboxes, kpss = self.app.det_model.detect(
                    image, max_num=0, metric='default')
                faces = []
                n = 0 if bboxes is None else bboxes.shape[0]
                _prefilter_pass = 0
                _prefilter_fail = 0
                for i in range(n):
                    score = float(bboxes[i, 4])
                    kps = kpss[i] if kpss is not None else None
                    bbox_i = bboxes[i, :4].astype(int).tolist()
                    landmarks_i = kps.tolist() if kps is not None else None
                    if not face_prefilter(bbox_i, score, landmarks_i):
                        _prefilter_fail += 1
                        continue   # skip embedding — face filtered by zone/conf/pose
                    _prefilter_pass += 1
                    f = _LazyFace(bbox=bboxes[i, :4], kps=kps, det_score=score)
                    for taskname, model in self.app.models.items():
                        if taskname == 'detection':
                            continue
                        model.get(image, f)
                    faces.append(f)
                # Debug: log SCRFD detection vs pre-filter results
                if n > 0 or _prefilter_fail > 0:
                    pass  # silent — throttled in server.py
            except Exception as _e:
                faces = None   # lazy path failed — fall back below

        if faces is None:
            faces = self.app.get(image)

        results = []

        for face in faces:
            emb = getattr(face, "normed_embedding", None)
            if emb is None:
                emb = getattr(face, "embedding", None)
            if emb is None:
                continue

            emb_norm = emb / np.linalg.norm(emb)
            bbox = face.bbox.astype(int).tolist()
            landmarks = face.kps.tolist() if face.kps is not None else None

            # Quality gate
            quality_ok, quality_reason = check_face_quality(image, bbox, landmarks)

            result = {
                "bbox":            bbox,
                "confidence":      float(face.det_score),
                "person_id":       None,
                "person_name":     "Unknown",
                "person_type":     "unknown",
                "match_confidence": 0.0,
                "matched":         False,
                "suspected":       False,
                "quality_ok":      quality_ok,
                "quality_reason":  quality_reason if not quality_ok else None,
                "raw_embedding":   emb_norm.flatten().tolist(),
            }

            if not quality_ok:
                x1, y1, x2, y2 = bbox
                face_w, face_h = x2 - x1, y2 - y1
                is_too_small = face_w < MIN_FACE_SIZE or face_h < MIN_FACE_SIZE
                # No threshold override — use exactly what the user configured

            # Priority: blacklist → employee → visitor
            match = self.blacklist_index.search(emb_norm, blacklist_threshold)
            if match:
                result.update({"person_id": match['person_id'], "person_name": match['name'],
                                "person_type": "blacklisted",
                                "match_confidence": match['confidence'], "matched": True})
                results.append(result)
                continue

            # Employee — full match — always use exactly the configured threshold
            match = self.employee_index.search(emb_norm, threshold)
            if match:
                result.update({"person_id": match['person_id'], "person_name": match['name'],
                                "person_type": "employee",
                                "match_confidence": match['confidence'], "matched": True})
                results.append(result)
                continue

            # Employee — suspected match (suspected_threshold ≤ sim < threshold)
            if suspected_threshold < threshold:
                suspected = self.employee_index.search(emb_norm, suspected_threshold)
                if suspected and suspected['confidence'] < threshold:
                    result.update({
                        "person_id":       suspected['person_id'],
                        "person_name":     suspected['name'],
                        "person_type":     "employee",
                        "match_confidence": suspected['confidence'],
                        "matched":         False,
                        "suspected":       True,
                    })
                    results.append(result)
                    continue

            match = self.visitor_index.search(emb_norm, visitor_threshold)
            if match:
                result.update({"person_id": match['person_id'], "person_name": match['name'],
                                "person_type": "visitor",
                                "match_confidence": match['confidence'], "matched": True})
                results.append(result)
                continue

            results.append(result)

        return results

    def verify_same_person(self, images: list, min_similarity: float = 0.30) -> tuple:
        """
        Before enrolling a folder, verify ALL images belong to the SAME person.
        Extracts embeddings from each image, computes pairwise similarity,
        rejects images that don't match the majority cluster.

        Returns (clean_images, rejected_images, report)
        - clean_images: images that belong to the same person
        - rejected_images: images that don't match (different person / no face)
        - report: dict with details
        """
        embeddings = []
        valid = []

        for img in images:
            faces = self.app.get(img)
            if not faces:
                continue
            face = max(faces, key=lambda f: f.det_score)
            if face.embedding is None:
                continue
            emb = face.embedding
            emb_norm = emb / np.linalg.norm(emb)
            embeddings.append(emb_norm)
            valid.append(img)

        if len(valid) < 2:
            return valid, [], {"verified": len(valid), "rejected": 0, "reason": "not enough detectable faces"}

        # Compute pairwise similarities
        embs = np.array(embeddings)  # shape: (N, 512)
        sim_matrix = embs @ embs.T   # cosine similarity matrix

        # Find the "anchor" — the image most similar to all others
        mean_sims = []
        for i in range(len(valid)):
            others = [sim_matrix[i][j] for j in range(len(valid)) if j != i]
            mean_sims.append(np.mean(others))

        anchor_idx = int(np.argmax(mean_sims))
        anchor_emb = embeddings[anchor_idx]

        # Keep images with similarity >= threshold to the anchor
        clean = []
        rejected = []
        for i, (img, emb) in enumerate(zip(valid, embeddings)):
            sim = float(np.dot(emb, anchor_emb))
            if sim >= min_similarity:
                clean.append(img)
            else:
                rejected.append((img, round(sim, 3)))

        report = {
            "total_detected": len(valid),
            "verified": len(clean),
            "rejected": len(rejected),
            "anchor_idx": anchor_idx,
            "rejected_sims": [r[1] for r in rejected],
        }
        return clean, [r[0] for r in rejected], report

    def enroll(self, image: np.ndarray, person_id: int, name: str,
               watchlist: str = "employee") -> dict:
        """
        Enroll a face with quality gate.
        Rejects blurry/tiny/non-frontal faces.
        Stores up to MAX_EMBEDDINGS_PER_PERSON per person.
        """
        faces = self.app.get(image)
        if not faces:
            return {"success": False, "error": "No face detected"}

        face = max(faces, key=lambda f: f.det_score)
        emb = face.embedding
        if emb is None:
            return {"success": False, "error": "Could not extract embedding"}

        bbox = face.bbox.astype(int).tolist()
        landmarks = face.kps.tolist() if face.kps is not None else None

        # Quality gate
        quality_ok, quality_reason = check_face_quality(image, bbox, landmarks)
        if not quality_ok:
            return {"success": False, "error": f"Quality gate failed: {quality_reason}"}

        emb_norm = emb / np.linalg.norm(emb)
        index = self._get_index(watchlist)
        result = index.add(emb_norm, person_id, name)
        result["watchlist"] = watchlist
        return result

    def remove_person(self, person_id: int, watchlist: str = "employee") -> dict:
        index = self._get_index(watchlist)
        removed = index.remove(person_id)
        return {"success": removed > 0, "removed_embeddings": removed}

    def _get_index(self, watchlist: str) -> FaceIndex:
        if watchlist == "blacklist":
            return self.blacklist_index
        elif watchlist == "visitor":
            return self.visitor_index
        return self.employee_index

    def get_stats(self) -> dict:
        return {
            "total_enrolled_embeddings": self.employee_index.total,
            "blacklist_embeddings":      self.blacklist_index.total,
            "visitor_embeddings":        self.visitor_index.total,
            "unique_persons": len(set(
                v['person_id'] for v in self.employee_index.id_map.values()
            )),
            "embedding_dim": self.dim,
            "detector":      "buffalo_l SCRFD (320x320)",
            "recognizer":    "buffalo_l ArcFace (512-dim, multi-capture)"
        }

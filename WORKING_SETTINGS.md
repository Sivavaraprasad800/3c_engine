# Working Settings — FRS System
Last confirmed working: 27/08/2026, 11AM session (9/10 detection rate)

---

## Face Recognition Settings (system_settings DB table)

| Setting | Value | Notes |
|---------|-------|-------|
| `face_threshold` | **0.45** | Main match threshold — lower = more detections |
| `suspected_threshold` | **0.37** | Shows as "⚠ Suspected" in dashboard |
| `blacklist_threshold` | **0.35** | |
| `visitor_threshold` | **0.50** | |
| `dedup_threshold` | **0.65** | |
| `dedup_seconds` | **60** | Same person re-detectable after 60 seconds |
| `known_suppress_seconds` | **60** | |
| `camera_unknown_cooldown` | **15** | Unknown person cooldown per camera |
| `camera_cooldown` | **120** | |
| `global_cooldown` | **300** | |

**To restore via API (run if settings get changed):**
```
python restore_settings.py
```

---

## face_engine.py Settings

| Setting | Value | Notes |
|---------|-------|-------|
| `MIN_FACE_SIZE` | **40** | Minimum face pixel size (40 = up to ~6m range) |
| `BLUR_THRESHOLD` | **15.0** | Accept blurry images (don't reject, still match) |
| `MAX_YAW` | **60.0** | Side-facing tolerance |
| `MAX_PITCH` | **40.0** | Up/down tilt tolerance |
| `MAX_EMBEDDINGS_PER_PERSON` | **5** | 5 face images per person |
| `det_size` | **(320, 320)** | SCRFD detector size — CRITICAL do not change |
| `OMP_NUM_THREADS` | **4** | CPU threads for AI |
| `MySQL FAISS loading` | **DISABLED** | Uses local .faiss files only |

---

## server.py Settings

| Setting | Value | Notes |
|---------|-------|-------|
| `AI_MAX_CONCURRENT` | **2** | 2 cameras do AI simultaneously |
| `effective_data_freq` | `target_fps // 10` | ~3 FPS AI recognition |
| `live preview` | every 3rd frame | ~10 FPS preview |
| `sleep after inference` | **none** | No artificial delay |

---

## FAISS Index (local files — CRITICAL)

```
face_index.faiss   — 560 employee embeddings (110 persons × 5)
id_map.pkl         — person_id → name mapping
```
**These MUST match the det_size=320. Do NOT delete.**
**MySQL 3c_eng_face_embeddings has wrong embeddings (extracted with det_size=160) — NOT USED.**

---

## Camera Settings (per camera in DB)

| Setting | Value |
|---------|-------|
| `face_confidence` | **0.6** |
| `min_yaw` | **-35** |
| `max_yaw` | **35** |
| `min_pitch` | **-15** |
| `max_pitch` | **15** |
| `detection_zone` | Drawn per camera — check Camera Config page |

---

## What BREAKS Detection

1. **Loading FAISS from MySQL** — MySQL embeddings were extracted with det_size=160, mismatch → low confidence → missed detections
2. **Changing det_size from 320 to 160** — breaks all existing FAISS embeddings
3. **Adding sleep(0.15) after inference** — blocks recognition, drops to 0.5 FPS
4. **AI_MAX_CONCURRENT=1** — all cameras queue behind each other, very slow
5. **face_threshold > 0.50** — misses many valid matches (11AM showed 52-71% confidence)
6. **Wrong detection zones** — zones covering wrong area = person ignored

---

## To Re-Export MySQL Embeddings (when needed)

Run `export_emb_batch.py` ONLY after confirming det_size=320 is active.
This will re-extract embeddings from face_images_export with the correct model.

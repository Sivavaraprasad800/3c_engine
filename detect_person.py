"""
detect_person.py — One-shot person detection & identification from a photo.

Runs the same InsightFace + FAISS pipeline as the server, entirely offline.
Works on small/blurry/side-profile photos (auto-upscale + quality report).

Usage:
  python detect_person.py path\\to\\photo.jpg
  python detect_person.py photo.jpg --no-quality          # force match even if blurry/turned
  python detect_person.py photo.jpg --threshold 0.40      # looser match threshold
  python detect_person.py photo.jpg --save annotated.jpg  # save image with boxes/names
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="FRS one-shot person detection")
    parser.add_argument("image", help="Path to the photo to analyze")
    parser.add_argument("--no-quality", action="store_true",
                        help="Bypass quality gate (blur/size/pose) and force matching")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Match threshold override (default: 0.50 system setting)")
    parser.add_argument("--save", default=None,
                        help="Save annotated image (boxes + names) to this path")
    args = parser.parse_args()

    img_path = Path(args.image)
    if not img_path.exists():
        print(f"[!] Image not found: {img_path}")
        sys.exit(1)

    import cv2
    import numpy as np
    from face_engine import FaceRecognitionEngine, check_face_quality

    image = cv2.imread(str(img_path))
    if image is None:
        print("[!] Could not read image (corrupt or unsupported format)")
        sys.exit(1)

    # Upscale small images — tiny crops (WhatsApp-style) need more pixels
    h, w = image.shape[:2]
    if max(h, w) < 480:
        scale = 480 / max(h, w)
        image = cv2.resize(image, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_CUBIC)
        print(f"[*] Small image upscaled {w}x{h} -> {image.shape[1]}x{image.shape[0]}")

    print("[*] Loading face engine (few seconds)...")
    engine = FaceRecognitionEngine()
    print(f"[*] Indexes: employees={engine.employee_index.total} "
          f"blacklist={engine.blacklist_index.total} "
          f"visitors={engine.visitor_index.total}")

    if engine.employee_index.total == 0 and engine.blacklist_index.total == 0 \
            and engine.visitor_index.total == 0:
        print("[!] ALL INDEXES EMPTY — enroll people first "
              "(POST /api/v1/frd/bulk-enroll-folders)")

    faces = engine.app.get(image)
    if not faces:
        print("[!] NO FACE DETECTED in this photo.")
        sys.exit(0)

    threshold = args.threshold if args.threshold is not None else 0.50
    print(f"[*] {len(faces)} face(s) detected — match threshold {threshold}\n")

    identified = []
    for i, face in enumerate(faces, 1):
        bbox = face.bbox.astype(int).tolist()
        x1, y1, x2, y2 = bbox
        fw, fh = x2 - x1, y2 - y1
        landmarks = face.kps.tolist() if face.kps is not None else None
        det_conf = float(face.det_score)
        print(f"-- Face #{i} - bbox={bbox} size={fw}x{fh} det_conf={det_conf:.2f}")

        ok, reason = check_face_quality(image, bbox, landmarks)
        if ok:
            print(f"    quality : OK")
        else:
            print(f"    quality : WARN ({reason}) -- still attempting match")
        # Always attempt matching -- quality is advisory only

        emb = face.embedding
        if emb is None:
            print("    result  : no embedding extracted\n")
            continue
        emb_norm = emb / np.linalg.norm(emb)

        # Search all three watchlists — report best of each
        best_label, best = None, None
        for label, index in (("BLACKLIST", engine.blacklist_index),
                             ("EMPLOYEE", engine.employee_index),
                             ("VISITOR", engine.visitor_index)):
            m = index.search(emb_norm, threshold=0.0)   # threshold 0 = always report top-1
            if m:
                print(f"    {label:<9}: top-1  {m['name']:<20} "
                      f"id={m['person_id']} sim={m['confidence']:.3f}")
                if best is None or m["confidence"] > best["confidence"]:
                    best_label, best = label, m
            else:
                print(f"    {label:<9}: empty index")

        if best is None:
            print("    result  : UNKNOWN (indexes empty)\n")
            continue

        sim = best["confidence"]
        if sim >= threshold:
            print(f"    result  : OK IDENTIFIED -> [{best_label}] {best['name']} "
                  f"(id={best['person_id']}, sim={sim:.3f})\n")
            identified.append((bbox, f"{best['name']} {sim:.2f}", (0, 200, 0)))
        else:
            print(f"    result  : XX UNKNOWN — closest is {best['name']} "
                  f"sim={sim:.3f} < threshold {threshold}\n")
            identified.append((bbox, f"Unknown {sim:.2f}", (0, 0, 255)))

    if args.save and identified:
        out = image.copy()
        for bbox, label, color in identified:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            cv2.putText(out, label, (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.imwrite(args.save, out)
        print(f"[*] Annotated image saved: {args.save}")

    if not identified:
        print("[*] No identified faces. Tips:")
        print("    - photo too blurry/small? try --no-quality")
        print("    - not enrolled yet? add photos to train_images/<name>/ then")
        print("      call POST /api/v1/frd/bulk-enroll-folders")


if __name__ == "__main__":
    main()

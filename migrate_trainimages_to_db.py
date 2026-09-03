"""
migrate_trainimages_to_db.py
────────────────────────────
One-time migration: reads ALL images from train_images/ folder and stores
them as base64 inside the persons.training_images_b64 DB column.

After running this, the system no longer needs the train_images/ folder —
all training data lives in the SQLite DB (data/frs.db).

Usage:
    python migrate_trainimages_to_db.py
"""

import sys
import cv2
from pathlib import Path

# ── Bootstrap DB ────────────────────────────────────────────
from database import (
    init_db, db_get_persons,
    db_get_person_training_images, db_add_person_training_image,
    db_clear_person_training_images,
)

init_db()

TRAIN_DIR = Path("train_images")

if not TRAIN_DIR.exists():
    print("train_images/ folder not found — nothing to migrate.")
    sys.exit(0)

persons = db_get_persons()
name_to_person = {p["name"].lower(): p for p in persons}

migrated_persons = 0
migrated_images  = 0
skipped_folders  = 0

def migrate_folder(folder: Path, person_name: str):
    global migrated_persons, migrated_images, skipped_folders

    person = name_to_person.get(person_name.lower())
    if not person:
        # Try fuzzy match — replace underscores with spaces
        alt_name = person_name.replace("_", " ").lower()
        person = name_to_person.get(alt_name)
    if not person:
        print(f"  [SKIP] '{person_name}' — not in DB (enroll first)")
        skipped_folders += 1
        return

    person_id = person["id"]

    images = sorted(
        list(folder.glob("*.jpg")) +
        list(folder.glob("*.jpeg")) +
        list(folder.glob("*.png"))
    )
    if not images:
        return

    # Check how many already in DB
    existing = db_get_person_training_images(person_id)
    if existing:
        print(f"  [SKIP] {person_name} — already has {len(existing)} images in DB")
        return

    count = 0
    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        n = db_add_person_training_image(person_id, img, max_images=5)
        count = n

    if count > 0:
        print(f"  [OK] {person_name} (ID={person_id}) — {count} images stored in DB")
        migrated_persons += 1
        migrated_images  += count
    else:
        print(f"  [WARN] {person_name} — images found but none could be read")

print(f"\nMigrating train_images/ → DB ...\n")

for item in sorted(TRAIN_DIR.iterdir()):
    if not item.is_dir():
        continue
    if item.name in ("employee", "visitor", "blacklist"):
        # watchlist subfolder
        for person_dir in sorted(item.iterdir()):
            if person_dir.is_dir():
                migrate_folder(person_dir, person_dir.name)
    else:
        # flat structure
        migrate_folder(item, item.name)

print(f"\n{'='*50}")
print(f"Migration complete:")
print(f"  Persons migrated : {migrated_persons}")
print(f"  Images stored    : {migrated_images}")
print(f"  Folders skipped  : {skipped_folders} (not in DB)")
print(f"\nYou can now safely ignore the train_images/ folder.")
print(f"New enrollments will be stored in DB automatically.")

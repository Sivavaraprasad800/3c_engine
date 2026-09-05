"""
Analyze a face photo for FRS enrollment quality.
Run: python analyze_face.py <path_to_image>
"""
import sys
import cv2
import numpy as np

def analyze(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: Cannot load image: {image_path}")
        return

    h, w = img.shape[:2]
    print(f"\n{'='*50}")
    print(f"IMAGE ANALYSIS: {image_path}")
    print(f"{'='*50}")
    print(f"Resolution: {w}x{h} pixels")
    print(f"Megapixels: {w*h/1_000_000:.1f}MP")

    # Brightness check
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    print(f"Brightness: {brightness:.0f}/255 {'(OK)' if 60 < brightness < 200 else '(TOO DARK/BRIGHT)'}")

    # Blur check (Laplacian variance)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    blur_status = "SHARP" if lap_var > 100 else "SLIGHTLY BLURRY" if lap_var > 30 else "VERY BLURRY"
    print(f"Sharpness: {lap_var:.0f} ({blur_status})")

    # Contrast check
    contrast = np.std(gray)
    print(f"Contrast: {contrast:.0f} {'(OK)' if contrast > 40 else '(LOW - flat lighting)'}")

    # Face detection using OpenCV's Haar cascade (quick check)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))

    print(f"\n--- FACE DETECTION ---")
    if len(faces) == 0:
        print(f"Faces found: 0 ❌ NO FACE DETECTED")
        print(f"  → This image will NOT work for FRS enrollment")
        print(f"  → Ensure face is clearly visible, frontal, and well-lit")
    else:
        print(f"Faces found: {len(faces)} ✅")
        for i, (x, y, fw, fh) in enumerate(faces):
            face_size_ratio = max(fw, fh) / max(w, h) * 100
            face_area = fw * fh
            print(f"  Face #{i+1}: {fw}x{fh}px at ({x},{y}) — {face_size_ratio:.0f}% of frame")

            # Check if face is large enough
            if fw < 80 or fh < 80:
                print(f"    ⚠️ Face is SMALL — may not get good embedding")
            else:
                print(f"    ✅ Face size is GOOD for recognition")

            # Check face centering
            fcx, fcy = x + fw//2, y + fh//2
            center_dist = np.sqrt((fcx - w/2)**2 + (fcy - h/2)**2) / np.sqrt((w/2)**2 + (h/2)**2) * 100
            if center_dist < 30:
                print(f"    ✅ Face is WELL CENTERED")
            elif center_dist < 60:
                print(f"    ⚠️ Face is slightly off-center")
            else:
                print(f"    ⚠️ Face is FAR FROM CENTER — crop it closer")

            # Extract and analyze face region
            face_roi = gray[y:y+fh, x:x+fw]
            face_brightness = np.mean(face_roi)
            face_lap = cv2.Laplacian(face_roi, cv2.CV_64F).var()

            if face_brightness < 50:
                print(f"    ⚠️ Face is DARK — needs better lighting")
            elif face_brightness > 220:
                print(f"    ⚠️ Face is OVEREXPOSED — too much light")
            else:
                print(f"    ✅ Face lighting is GOOD ({face_brightness:.0f})")

            if face_lap > 100:
                print(f"    ✅ Face is SHARP for embedding ({face_lap:.0f})")
            elif face_lap > 30:
                print(f"    ⚠️ Face is slightly blurry ({face_lap:.0f})")
            else:
                print(f"    ❌ Face is TOO BLURRY for reliable recognition ({face_lap:.0f})")

    # Overall rating
    print(f"\n--- OVERALL FRS ENROLLMENT SUITABILITY ---")
    if len(faces) == 0:
        print(f"❌ NOT SUITABLE — no face detected")
    elif any(max(fw, fh) < 80 for (x, y, fw, fh) in faces):
        print(f"⚠️ MARGINAL — face detected but small. Crop closer or use higher resolution")
    elif lap_var < 30:
        print(f"⚠️ MARGINAL — image is blurry. Use a sharper photo")
    else:
        print(f"✅ SUITABLE — good face detection, size, and sharpness for enrollment")

    print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_face.py <image_path>")
        sys.exit(1)
    analyze(sys.argv[1])

"""
make_icon.py — Generate FRS 3C Engine app icon
Creates a face-scan themed icon with:
- Dark background
- Face outline with scan lines
- Corner brackets (like a face detection box)
- Blue accent color matching the dashboard
Outputs: icon.ico (multi-size for exe) and icon_tray.png (tray)
"""
from PIL import Image, ImageDraw, ImageFont
import math
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

# ── Colors ────────────────────────────────────────────────────────────────────
BG       = (20, 23, 28)         # dark background
ACCENT   = (74, 158, 255)       # blue accent
ACCENT2  = (0, 210, 150)        # green accent
WHITE    = (255, 255, 255)
DIM      = (100, 120, 150)

def draw_icon(size):
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s    = size

    # ── Background rounded square ──────────────────────────────────────────
    r = s // 6  # corner radius
    draw.rounded_rectangle([0, 0, s-1, s-1], radius=r, fill=BG)

    # ── Outer glow ring ────────────────────────────────────────────────────
    for i in range(3, 0, -1):
        alpha = 40 + i * 20
        draw.ellipse(
            [s*0.08 - i, s*0.08 - i, s*0.92 + i, s*0.92 + i],
            outline=(*ACCENT, alpha), width=1
        )

    # ── Face outline (oval) ────────────────────────────────────────────────
    fx1, fy1 = s * 0.28, s * 0.18
    fx2, fy2 = s * 0.72, s * 0.72
    draw.ellipse([fx1, fy1, fx2, fy2], outline=(*ACCENT, 220), width=max(1, s//32))

    # ── Eyes ──────────────────────────────────────────────────────────────
    eye_y  = s * 0.36
    eye_r  = s * 0.055
    # Left eye
    draw.ellipse([s*0.37 - eye_r, eye_y - eye_r, s*0.37 + eye_r, eye_y + eye_r],
                 fill=ACCENT, outline=WHITE)
    # Right eye
    draw.ellipse([s*0.63 - eye_r, eye_y - eye_r, s*0.63 + eye_r, eye_y + eye_r],
                 fill=ACCENT, outline=WHITE)

    # ── Nose dot ──────────────────────────────────────────────────────────
    nr = s * 0.025
    draw.ellipse([s*0.5 - nr, s*0.50 - nr, s*0.5 + nr, s*0.50 + nr], fill=DIM)

    # ── Mouth curve ───────────────────────────────────────────────────────
    mx1, my1 = s * 0.38, s * 0.58
    mx2, my2 = s * 0.62, s * 0.65
    draw.arc([mx1, my1 - s*0.04, mx2, my2], start=10, end=170,
             fill=(*ACCENT, 200), width=max(1, s//40))

    # ── Corner brackets (face detection box style) ─────────────────────────
    bx1, by1 = s * 0.12, s * 0.10
    bx2, by2 = s * 0.88, s * 0.90
    bl  = s * 0.12   # bracket length
    bw  = max(2, s // 24)  # line width
    c   = ACCENT2

    # Top-left
    draw.line([(bx1, by1 + bl), (bx1, by1), (bx1 + bl, by1)], fill=c, width=bw)
    # Top-right
    draw.line([(bx2 - bl, by1), (bx2, by1), (bx2, by1 + bl)], fill=c, width=bw)
    # Bottom-left
    draw.line([(bx1, by2 - bl), (bx1, by2), (bx1 + bl, by2)], fill=c, width=bw)
    # Bottom-right
    draw.line([(bx2 - bl, by2), (bx2, by2), (bx2, by2 - bl)], fill=c, width=bw)

    # ── Scan line (animated look) ──────────────────────────────────────────
    scan_y = s * 0.44
    for i, alpha in [(0, 180), (1, 100), (2, 40)]:
        draw.line([(s * 0.15, scan_y + i), (s * 0.85, scan_y + i)],
                  fill=(*ACCENT2, alpha), width=1)

    # ── "3C" text bottom ──────────────────────────────────────────────────
    if size >= 64:
        try:
            fsize = max(8, s // 8)
            font  = ImageFont.truetype("arial.ttf", fsize)
        except Exception:
            font  = ImageFont.load_default()
        text = "3C"
        bb   = draw.textbbox((0, 0), text, font=font)
        tw   = bb[2] - bb[0]
        draw.text(((s - tw) // 2, s * 0.78), text, fill=(*ACCENT, 220), font=font)

    return img

# ── Generate sizes ────────────────────────────────────────────────────────────
print("Generating FRS icon...")

# Tray icon (64x64 PNG)
tray = draw_icon(64)
tray_path = os.path.join(OUT_DIR, "icon_tray.png")
tray.save(tray_path)
print(f"  Saved: {tray_path}")

# App icon (.ico — multiple sizes bundled)
sizes   = [16, 32, 48, 64, 128, 256]
images  = [draw_icon(s) for s in sizes]
ico_path = os.path.join(OUT_DIR, "icon.ico")
images[0].save(
    ico_path,
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=images[1:]
)
print(f"  Saved: {ico_path}")

# Also save a 256x256 PNG preview
preview_path = os.path.join(OUT_DIR, "icon_256.png")
draw_icon(256).save(preview_path)
print(f"  Saved: {preview_path}")

print("Done! Icon files ready.")

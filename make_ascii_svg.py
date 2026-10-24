#!/usr/bin/env python3
"""
ASCII portrait -> animated, theme-aware SVG (face-focused edition)

Usage:
    python make_ascii_svg.py photo.jpg ascii.svg
    python make_ascii_svg.py photo.jpg ascii.svg --cols 260 --debug
"""

import argparse
import html
import sys

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps
from rembg import remove

# ============================================================
# SETTINGS
# ============================================================

COLS = 320                 # 180-260 is the sweet spot for GitHub
RAMP = " .,:;-~=+*oxX#%@"  # light -> dense (16 levels, clean shading)

# Character cell geometry (the row count is derived from these)
CHAR_W = 5.0
LINE_H = 10.0
FONT_SIZE = 8.4
PAD = 16

# Face-centred crop, in multiples of the detected face box
CROP_HALF_WIDTH = 1.5      # total width = 3 x face width
CROP_ABOVE = 0.75          # room for hair above the face box
CROP_BELOW = 2.1           # chin + neck + shoulders

# Tone
GAMMA = 0.99               # < 1 brightens midtones
CLAHE_CLIP = 2.0
CLAHE_MIX = 0.55           # 0 = no local contrast, 1 = full CLAHE
SUBJECT_ALPHA = 0.4        # alpha above this counts as subject

# Animation
ROW_DELAY = 0.03

# Colors (GitHub light / dark)
FG_LIGHT = "#24292f"
FG_DARK = "#e6edf3"


# ============================================================
# LOAD
# ============================================================

def load_image(path):
    print("Loading photo...")
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    print(f"Original size: {img.width} x {img.height}")
    return img


# ============================================================
# FACE DETECTION + CROP
# ============================================================

def detect_face(img):
    arr = np.asarray(img)
    scale = min(1.0, 1000 / max(arr.shape[:2]))
    small = (
        cv2.resize(arr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1 else arr
    )
    gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY))

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    min_side = max(40, min(gray.shape) // 10)
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(min_side, min_side)
    )
    if len(faces) == 0:
        return None

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return tuple(int(v / scale) for v in (x, y, w, h))


def crop_to_portrait(img, face):
    if face is None:
        print("No face detected - using full image (check photo angle/lighting)")
        return img

    x, y, w, h = face
    print(f"Face detected: {w} x {h} at ({x}, {y})")

    cx = x + w / 2
    left = max(0, int(cx - w * CROP_HALF_WIDTH))
    right = min(img.width, int(cx + w * CROP_HALF_WIDTH))
    top = max(0, int(y - h * CROP_ABOVE))
    bottom = min(img.height, int(y + h * CROP_BELOW))

    cropped = img.crop((left, top, right, bottom))
    print(f"Cropped portrait: {cropped.width} x {cropped.height}")
    return cropped


# ============================================================
# BACKGROUND REMOVAL -> gray + mask
# ============================================================

def split_gray_and_alpha(rgb_img):
    print("Removing background...")
    rgba = remove(rgb_img.convert("RGBA"))
    alpha = np.asarray(rgba.getchannel("A"), dtype=np.float32) / 255.0

    # Gray from the ORIGINAL pixels (not multiplied by alpha),
    # so edges/hair keep real brightness.
    rgb = np.asarray(rgb_img, dtype=np.float32)
    gray = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    return gray, alpha


def tighten_if_no_face(gray, alpha):
    """Fallback crop when no face was found: use the subject bbox."""
    ys, xs = np.where(alpha > SUBJECT_ALPHA)
    if len(xs) == 0:
        return gray, alpha
    l, r = xs.min(), xs.max() + 1
    t, b = ys.min(), ys.max() + 1
    b = t + int((b - t) * 0.8)
    return gray[t:b, l:r], alpha[t:b, l:r]


# ============================================================
# RESIZE HELPERS
# ============================================================

def resize(arr, size):
    w, h = size
    interp = cv2.INTER_AREA if w < arr.shape[1] else cv2.INTER_CUBIC
    return cv2.resize(arr, (w, h), interpolation=interp)


# ============================================================
# TONE
# ============================================================

def tone_map(gray, mask):
    print("Tone mapping...")
    g = gray.copy()
    subj = g[mask]

    if subj.size > 100:
        # Fill background with the subject mean so it doesn't skew CLAHE
        g[~mask] = subj.mean()
        lo, hi = np.percentile(subj, (1, 99))
        g = np.clip((g - lo) / max(hi - lo, 1.0), 0, 1) * 255

    g8 = np.clip(g, 0, 255).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(8, 8))
    g = g * (1 - CLAHE_MIX) + clahe.apply(g8).astype(np.float32) * CLAHE_MIX

    g = 255.0 * np.power(np.clip(g / 255.0, 0, 1), GAMMA)
    return np.clip(g, 0, 255).astype(np.uint8)


# ============================================================
# ASCII
# ============================================================

def to_lines(gray_grid, mask_grid, invert):
    """invert=False -> dense = bright (for light text on dark bg)
       invert=True  -> dense = dark   (for dark text on light bg)"""
    n = len(RAMP)
    b = gray_grid.astype(np.float32) / 255.0
    t = (1.0 - b) if invert else b

    idx = np.clip((t * (n - 1)).round().astype(int), 1, n - 1)  # >=1 keeps silhouette
    idx[~mask_grid] = 0

    ramp = np.array(list(RAMP))
    return ["".join(row).rstrip() for row in ramp[idx]]


def build_ascii(gray, alpha):
    h, w = gray.shape
    rows = max(1, round(COLS * (h / w) * (CHAR_W / LINE_H)))
    print(f"ASCII size: {COLS} columns x {rows} rows")

    # Do the heavy processing at 4x grid resolution
    work_w = COLS * 4
    work_h = round(work_w * h / w)

    gray_w = resize(gray, (work_w, work_h))
    alpha_w = resize(alpha, (work_w, work_h))
    mask_w = alpha_w > SUBJECT_ALPHA

    toned = tone_map(gray_w, mask_w)

    # Sharpen at working resolution (this is what recovers eyes/brows/lips)
    pil = Image.fromarray(toned).filter(
        ImageFilter.UnsharpMask(radius=2.0, percent=130, threshold=2)
    )
    toned = np.asarray(pil)

    # Downsample to the character grid
    grid = resize(toned, (COLS, rows))
    grid = np.asarray(
        Image.fromarray(grid).filter(
            ImageFilter.UnsharpMask(radius=0.8, percent=80, threshold=1)
        )
    )
    mask_grid = resize(alpha_w, (COLS, rows)) > SUBJECT_ALPHA

    dark_mode = to_lines(grid, mask_grid, invert=False)
    light_mode = to_lines(grid, mask_grid, invert=True)

    # Trim empty rows at top/bottom (same for both layers)
    keep = np.where(mask_grid.any(axis=1))[0]
    if len(keep):
        a, b = keep.min(), keep.max() + 1
        dark_mode, light_mode = dark_mode[a:b], light_mode[a:b]

    return dark_mode, light_mode, toned


# ============================================================
# SVG
# ============================================================

def build_svg(dark_lines, light_lines, output_path):
    print("Creating animated SVG...")
    rows = len(dark_lines)
    width = int(COLS * CHAR_W + PAD * 2)
    height = int(rows * LINE_H + PAD * 2)

    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="ASCII portrait">
<style>
.a {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: {FONT_SIZE}px;
  font-weight: 500;
  white-space: pre;
}}
.lt {{ fill: {FG_LIGHT}; display: inline; }}
.dk {{ fill: {FG_DARK};  display: none; }}
@media (prefers-color-scheme: dark) {{
  .lt {{ display: none; }}
  .dk {{ display: inline; }}
}}
</style>''']

    for i, (d, l) in enumerate(zip(dark_lines, light_lines)):
        y_top = PAD + i * LINE_H
        base = y_top + LINE_H * 0.8
        text_w = max(len(d), 1) * CHAR_W
        begin = i * ROW_DELAY

        svg.append(
            f'<clipPath id="c{i}"><rect x="{PAD}" y="{y_top:.2f}" width="0" height="{LINE_H:.2f}">'
            f'<animate attributeName="width" from="0" to="{text_w:.2f}" '
            f'begin="{begin:.3f}s" dur="{ROW_DELAY:.3f}s" fill="freeze"/></rect></clipPath>'
        )
        svg.append(
            f'<g clip-path="url(#c{i})">'
            f'<text x="{PAD}" y="{base:.2f}" class="a dk" xml:space="preserve" '
            f'textLength="{text_w:.2f}" lengthAdjust="spacing">{html.escape(d, quote=False)}</text>'
            f'<text x="{PAD}" y="{base:.2f}" class="a lt" xml:space="preserve" '
            f'textLength="{text_w:.2f}" lengthAdjust="spacing">{html.escape(l, quote=False)}</text>'
            f'</g>'
        )

    svg.append("</svg>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg))

    print(f"\nCreated: {output_path}")
    print(f"Rows: {rows}   SVG size: {width} x {height}")


# ============================================================
# MAIN
# ============================================================

def main():
    global COLS

    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("output", nargs="?", default="ascii.svg")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--debug", action="store_true",
                    help="save debug_tone.png to preview the processed image")
    args = ap.parse_args()
    COLS = args.cols

    img = load_image(args.photo)

    face = detect_face(img)
    portrait = crop_to_portrait(img, face)

    gray, alpha = split_gray_and_alpha(portrait)
    if face is None:
        gray, alpha = tighten_if_no_face(gray, alpha)

    dark_lines, light_lines, toned = build_ascii(gray, alpha)

    if args.debug:
        Image.fromarray(toned).save("debug_tone.png")
        print("Saved debug_tone.png")

    build_svg(dark_lines, light_lines, args.output)


if __name__ == "__main__":
    main()
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np
import easyocr
import shutil
from tqdm import tqdm

# -------- CONFIG --------
SRC_DIR = Path("data_raw_all")          # all scraped images
DST_DIR = Path("data_raw_no_text")      # images with no text or only overlays
REJECTED_DIR = Path("data_raw_rejected")  # images with meme-like text or errors

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

# If total chars < this, we treat it as "no text"
MIN_TOTAL_CHARS = 3

USE_GPU = True  # set False if you want CPU

# Heuristic thresholds (tune these)
MAX_OVERLAY_TOTAL_AREA_RATIO = 0.08   # overlays should occupy < 8% of total image area
MAX_OVERLAY_REGION_AREA_RATIO = 0.04  # each overlay region should be < 4% of area

MEME_MIN_REGION_AREA_RATIO = 0.10     # any region > 10% of area is suspiciously meme-like
MEME_MIN_WIDTH_RATIO = 0.7            # meme text often spans >70% width
MEME_MIN_TOTAL_AREA_RATIO = 0.20      # or total text area >20% of image
MEME_MIN_TOTAL_CHARS = 25             # or lots of characters overall
# ------------------------


def is_image(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_EXTS


def classify_text_type(img: Image.Image, reader: easyocr.Reader) -> str:
    """
    Classify the image into:
      - "none"    : no relevant text
      - "overlay" : small overlays (timestamps, camera UI, VHS subs, etc.)
      - "meme"    : big caption / meme-style text

    This is heuristic: use bounding box area, total area, and char count.
    """
    img = ImageOps.exif_transpose(img).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[0], arr.shape[1]
    img_area = float(w * h)

    # EasyOCR: returns list of (bbox, text, confidence)
    results = reader.readtext(arr, detail=1, paragraph=False)

    if not results:
        return "none"

    total_chars = sum(len(text) for (_, text, _) in results)
    if total_chars < MIN_TOTAL_CHARS:
        return "none"

    total_text_area = 0.0
    max_region_area_ratio = 0.0
    max_region_width_ratio = 0.0

    for (bbox, text, conf) in results:
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max_x - min_x
        height = max_y - min_y
        area = width * height

        if area <= 0:
            continue

        area_ratio = area / img_area
        width_ratio = width / w

        total_text_area += area
        max_region_area_ratio = max(max_region_area_ratio, area_ratio)
        max_region_width_ratio = max(max_region_width_ratio, width_ratio)

    total_area_ratio = total_text_area / img_area

    # ---- MEME HEURISTICS ----
    # If any region is big or text dominates the image, call it meme
    if (
        max_region_area_ratio >= MEME_MIN_REGION_AREA_RATIO
        or max_region_width_ratio >= MEME_MIN_WIDTH_RATIO
        or total_area_ratio >= MEME_MIN_TOTAL_AREA_RATIO
        or total_chars >= MEME_MIN_TOTAL_CHARS
    ):
        return "meme"

    # ---- OVERLAY HEURISTICS ----
    # If we got here, there is text but it's relatively small and constrained.
    # Treat as overlay if within reasonable area limits.
    if (
        total_area_ratio <= MAX_OVERLAY_TOTAL_AREA_RATIO
        and max_region_area_ratio <= MAX_OVERLAY_REGION_AREA_RATIO
    ):
        return "overlay"

    # Fallback: if it's not clearly overlay and text is not negligible, be conservative → meme
    return "meme"


def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    # Collect candidate paths
    all_paths = [
        p for p in SRC_DIR.rglob("*")
        if p.is_file() and is_image(p)
    ]

    print(f"Found {len(all_paths)} candidate images in {SRC_DIR}")

    # Initialize EasyOCR reader once
    reader = easyocr.Reader(['en'], gpu=USE_GPU)

    num_kept = 0
    num_rejected = 0

    with tqdm(all_paths, desc="Filtering images", unit="img") as pbar:
        for img_path in pbar:
            try:
                img = Image.open(img_path)
            except Exception:
                # Any error: treat as rejected (put aside to inspect manually)
                out_path = REJECTED_DIR / img_path.name
                if not out_path.exists():
                    shutil.copy2(img_path, out_path)
                num_rejected += 1
                pbar.set_postfix(kept=num_kept, rejected=num_rejected)
                continue

            text_type = classify_text_type(img, reader)

            if text_type in ("none", "overlay"):
                out_path = DST_DIR / img_path.name
                if not out_path.exists():
                    shutil.copy2(img_path, out_path)
                num_kept += 1
            else:  # "meme"
                out_path = REJECTED_DIR / img_path.name
                if not out_path.exists():
                    shutil.copy2(img_path, out_path)
                num_rejected += 1

            pbar.set_postfix(kept=num_kept, rejected=num_rejected)

    print("\nDone.")
    print(f"Kept (none/overlay):     {num_kept}")
    print(f"Rejected (meme/errors):  {num_rejected}")


if __name__ == "__main__":
    main()

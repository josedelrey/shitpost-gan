from pathlib import Path
from PIL import Image, ImageOps
import numpy as np
import easyocr
import shutil
from tqdm import tqdm

# -------- CONFIG --------
SRC_DIR = Path("data_raw_all")      # all scraped images
DST_DIR = Path("data_raw_no_text")  # images with (almost) no text

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

MIN_TOTAL_CHARS = 3    # if EasyOCR finds >= this many chars, treat as "has text"
USE_GPU = True         # set False if you want CPU
# ------------------------


def is_image(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_EXTS


def has_text_easyocr(img: Image.Image, reader: easyocr.Reader) -> bool:
    """Return True if EasyOCR detects a reasonable amount of text."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    arr = np.array(img)

    results = reader.readtext(arr, detail=1, paragraph=False)
    total_chars = sum(len(text) for (_, text, _) in results)

    return total_chars >= MIN_TOTAL_CHARS


def main():
    DST_DIR.mkdir(parents=True, exist_ok=True)

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
                num_rejected += 1
                pbar.set_postfix(kept=num_kept, rejected=num_rejected)
                continue

            if has_text_easyocr(img, reader):
                num_rejected += 1
            else:
                out_path = DST_DIR / img_path.name
                if not out_path.exists():
                    shutil.copy2(img_path, out_path)
                num_kept += 1

            pbar.set_postfix(kept=num_kept, rejected=num_rejected)

    print("\nDone.")
    print(f"Kept (no text):        {num_kept}")
    print(f"Rejected (text/errors): {num_rejected}")


if __name__ == "__main__":
    main()

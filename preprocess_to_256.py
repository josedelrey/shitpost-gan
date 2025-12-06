from pathlib import Path
from PIL import Image, ImageOps
import itertools

# -------- CONFIG --------
SRC_DIR = Path("data_raw_no_text")      # input folder with your raw, no-text shitposts
DST_DIR = Path("data_preprocessed_256") # output folder for 256x256 images

TARGET_RES = 256      # final resolution (256x256)
MIN_SIZE = 128        # skip images smaller than this in either dimension (optional)
PAD_COLOR = (128, 128, 128)  # padding color for non-square images (gray)

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}  # extensions to accept
# ------------------------


def is_image(path: Path) -> bool:
    return path.suffix.lower() in ALLOWED_EXTS


def preprocess():
    DST_DIR.mkdir(parents=True, exist_ok=True)

    counter = itertools.count(1)
    num_input = 0
    num_saved = 0
    num_skipped = 0

    for img_path in SRC_DIR.rglob("*"):
        if not img_path.is_file() or not is_image(img_path):
            continue

        num_input += 1

        try:
            img = Image.open(img_path)
            # apply EXIF orientation (important for photos)
            img = ImageOps.exif_transpose(img)

            # Handle palette+alpha properly
            if img.mode == "P":
                img = img.convert("RGBA")
                
            img = img.convert("RGB")
        except Exception:
            # unreadable / corrupt
            num_skipped += 1
            continue

        w, h = img.size

        # skip very small images (optional but recommended)
        if w < MIN_SIZE or h < MIN_SIZE:
            num_skipped += 1
            continue

        # pad to square to preserve aspect ratio (no cropping of content)
        if w != h:
            dim = max(w, h)
            new_im = Image.new("RGB", (dim, dim), PAD_COLOR)
            new_im.paste(img, ((dim - w) // 2, (dim - h) // 2))
            img = new_im

        # final resize to 256x256
        img = img.resize((TARGET_RES, TARGET_RES), Image.LANCZOS)

        idx = next(counter)
        out_name = f"img_{idx:08d}.png"
        out_path = DST_DIR / out_name
        img.save(out_path)
        num_saved += 1

        if idx % 500 == 0:
            print(f"Saved {idx} images so far...")

    print("Done.")
    print(f"Total candidate files: {num_input}")
    print(f"Saved: {num_saved}")
    print(f"Skipped (corrupt/small): {num_skipped}")


if __name__ == "__main__":
    preprocess()

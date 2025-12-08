#!/usr/bin/env python3
import argparse
import hashlib
import os
from pathlib import Path
import shutil

# Allowed image extensions (customize if needed)
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


def is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTS


def sha1_of_file(path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA1 hash of a file, reading in chunks."""
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def flatten_images(input_dir: Path, output_dir: Path) -> None:
    if not input_dir.is_dir():
        raise ValueError(f"Input path is not a directory: {input_dir}")

    # Create destination folder
    output_dir.mkdir(parents=True, exist_ok=True)

    count_total = 0
    count_copied = 0
    count_skipped = 0

    # Walk directory tree
    for root, dirs, files in os.walk(input_dir):
        root_path = Path(root)
        for name in files:
            src_path = root_path / name
            if not is_image(src_path):
                continue

            count_total += 1

            # Compute SHA1 and build destination filename
            file_hash = sha1_of_file(src_path)
            ext = src_path.suffix.lower() or ".jpg"
            dst_name = f"{file_hash}{ext}"
            dst_path = output_dir / dst_name

            if dst_path.exists():
                # Same SHA1 already there -> same content, skip
                count_skipped += 1
                continue

            shutil.copy2(src_path, dst_path)
            count_copied += 1

            # Log every 100 copies (optional)
            if count_copied % 100 == 0:
                print(f"[INFO] Copied {count_copied} images so far...")

    print("--------------------------------------------------")
    print(f"Total image files found: {count_total}")
    print(f"Copied to {output_dir}: {count_copied}")
    print(f"Skipped (already present by SHA1): {count_skipped}")
    print("Done.")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Recursively find all images in a folder and copy them into "
            "a flat 'data_raw_all' folder using SHA1-based filenames."
        )
    )
    parser.add_argument(
        "input_dir",
        type=str,
        help="Path to the root folder containing image subfolders.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=(
            "Optional explicit output directory. "
            "If not provided, 'data_raw_all' will be created next to input_dir."
        ),
    )

    args = parser.parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()

    if args.output_dir is None:
        output_dir = input_dir.parent / "data_raw_all"
    else:
        output_dir = Path(args.output_dir).expanduser().resolve()

    print(f"[INFO] Input directory:  {input_dir}")
    print(f"[INFO] Output directory: {output_dir}")

    flatten_images(input_dir, output_dir)


if __name__ == "__main__":
    main()

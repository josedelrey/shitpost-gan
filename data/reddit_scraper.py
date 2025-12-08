import os
import time
import hashlib
from urllib.parse import urlparse
import requests

# ------------- CONFIG -------------
SUBREDDITS = [
    "blursedimages",
    "cursedimages",
    "Cursed_Images",
    "Cursed",
    "hmmm",
    "oddlyterrifying",
]

OUTPUT_ROOT_DIR = "reddit_cursed_images"

# If you set this to None, there is no max per subreddit (loop until no more posts).
# If you set it to an int, it will stop after scanning that many posts.
MAX_POSTS_PER_SUBREDDIT = None

REQUEST_SLEEP = 1.0
TIMEOUT = 20

# ------------- UTILS -------------


def safe_filename(url: str) -> str:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    ext = os.path.splitext(urlparse(url).path)[1]
    if not ext:
        ext = ".jpg"
    return f"{h}{ext}"


def download_image(url: str, out_dir: str) -> bool:
    os.makedirs(out_dir, exist_ok=True)
    filename = safe_filename(url)
    path = os.path.join(out_dir, filename)

    if os.path.exists(path):
        return False

    try:
        resp = requests.get(url, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
    except Exception:
        return False

    try:
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception:
        return False


def extract_image_urls_from_post(post_data: dict) -> list:
    urls = []

    # Direct link
    url = post_data.get("url_overridden_by_dest") or post_data.get("url")
    if isinstance(url, str):
        lower = url.lower()
        if any(lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            urls.append(url)

    # Preview images
    preview = post_data.get("preview")
    if preview and "images" in preview:
        for img in preview["images"]:
            src = img.get("source", {})
            u = src.get("url")
            if u:
                urls.append(u)

    # Galleries
    if post_data.get("is_gallery") and post_data.get("media_metadata"):
        for item in post_data["media_metadata"].values():
            if "s" in item and "u" in item["s"]:
                urls.append(item["s"]["u"])

    # Deduplicate + HTML entity fix
    seen = set()
    clean = []
    for u in urls:
        u = u.replace("&amp;", "&")
        if u not in seen:
            seen.add(u)
            clean.append(u)

    return clean


# ------------- CORE PER-SUBREDDIT LOGIC -------------


def scrape_subreddit(subreddit: str) -> int:
    print(f"\n[INFO] Scraping r/{subreddit} ...")

    # Each subreddit goes to its own folder
    out_dir = os.path.join(OUTPUT_ROOT_DIR, subreddit)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "script:cursedimages_downloader:v1.1 (by u/yourusername)"
    })

    after = None
    scanned_posts = 0
    downloaded_count = 0

    while True:
        # Respect MAX_POSTS_PER_SUBREDDIT only if it's not None
        if MAX_POSTS_PER_SUBREDDIT is not None and scanned_posts >= MAX_POSTS_PER_SUBREDDIT:
            break

        params = {"limit": 100}
        if after:
            params["after"] = after

        try:
            resp = session.get(
                f"https://www.reddit.com/r/{subreddit}/.json",
                params=params,
                timeout=TIMEOUT
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"[ERROR] Cannot fetch subreddit listing for r/{subreddit}: {e}")
            break

        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        after = data.get("data", {}).get("after")

        if not posts:
            print("[INFO] No more posts.")
            break

        for post in posts:
            scanned_posts += 1
            post_data = post.get("data", {})
            image_urls = extract_image_urls_from_post(post_data)

            for u in image_urls:
                if download_image(u, out_dir):
                    downloaded_count += 1
                    if downloaded_count % 100 == 0:
                        print(f"[LOG][r/{subreddit}] Downloaded {downloaded_count} images so far")

            # Again, only check the limit if it's not None
            if MAX_POSTS_PER_SUBREDDIT is not None and scanned_posts >= MAX_POSTS_PER_SUBREDDIT:
                break

        if not after:
            break

        time.sleep(REQUEST_SLEEP)

    print(f"[DONE][r/{subreddit}] Total scanned posts: {scanned_posts}")
    print(f"[DONE][r/{subreddit}] Total images downloaded from this subreddit: {downloaded_count}")

    # Return the per-subreddit count so main() can aggregate
    return downloaded_count


# ------------- MAIN -------------


def main():
    os.makedirs(OUTPUT_ROOT_DIR, exist_ok=True)

    total_downloaded_all = 0

    for subreddit in SUBREDDITS:
        downloaded_from_sub = scrape_subreddit(subreddit)
        total_downloaded_all += downloaded_from_sub
        print(f"[AGGREGATE] After r/{subreddit}: {total_downloaded_all} total images downloaded across all subreddits so far")

    print("\n==============================")
    print(f"[GLOBAL DONE] Total images downloaded from all subreddits: {total_downloaded_all}")
    print("==============================")


if __name__ == "__main__":
    main()

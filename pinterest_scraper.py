import os
import time
import hashlib
import requests
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# -------------------
# CONFIG
# -------------------
SEARCH_URL = "https://www.pinterest.com/search/boards/?q=cursed%20images"
OUTPUT_DIR = "pinterest_cursed_images"

MAX_BOARDS = 100000
SCROLL_PAUSE = 0.5
MAX_SCROLLS_SEARCH = 200
MAX_SCROLLS_BOARD = 500


# -------------------
# UTILS
# -------------------
def safe_filename(url: str) -> str:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    ext = os.path.splitext(urlparse(url).path)[1]
    if not ext:
        ext = ".jpg"
    return f"{h}{ext}"


def download_image(url: str, out_dir: str, timeout: int = 15):
    os.makedirs(out_dir, exist_ok=True)
    filename = safe_filename(url)
    path = os.path.join(out_dir, filename)

    if os.path.exists(path):
        return False

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        return True
    except:
        return False


# -------------------
# SCRAPING LOGIC (unchanged)
# -------------------
def maybe_accept_cookies(page):
    for label in ("Accept all", "Aceptar todo"):
        try:
            btn = page.get_by_role("button", name=label)
            if btn.is_visible():
                btn.click()
                time.sleep(1)
                return
        except:
            continue


def get_board_urls(page, max_boards=MAX_BOARDS):
    page.goto(SEARCH_URL, wait_until="domcontentloaded")
    time.sleep(3)
    maybe_accept_cookies(page)

    board_urls = set()
    last_height = 0

    for _ in range(MAX_SCROLLS_SEARCH):
        anchors = page.query_selector_all("a[href]")
        for a in anchors:
            href = a.get_attribute("href")
            if not href:
                continue

            if href.startswith("/"):
                href = "https://www.pinterest.com" + href

            if "/pin/" in href:
                continue
            if "/search/" in href:
                continue
            if "login" in href:
                continue

            if "pinterest.com" in href:
                href = href.split("?")[0]
                board_urls.add(href)

        if len(board_urls) >= max_boards:
            break

        page.mouse.wheel(0, 3000)
        time.sleep(SCROLL_PAUSE)

        new_height = page.evaluate("() => document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    return list(board_urls)[:max_boards]


def get_image_urls_from_board(page, board_url):
    page.goto(board_url, wait_until="domcontentloaded")
    time.sleep(3)

    image_urls = set()
    last_height = 0

    for i in range(MAX_SCROLLS_BOARD):
        imgs = page.query_selector_all("img[src]")
        for img in imgs:
            src = img.get_attribute("src")
            if not src:
                continue
            if "i.pinimg.com" in src:
                src = src.split("?")[0]
                image_urls.add(src)

        page.mouse.wheel(0, 3000)
        time.sleep(SCROLL_PAUSE)

        new_height = page.evaluate("() => document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

        if i == 4 and len(image_urls) == 0:
            break

    return list(image_urls)


# -------------------
# MAIN (clean logs + new total-after-board log)
# -------------------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total_downloaded = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )

        page = context.new_page()
        page.set_default_navigation_timeout(60000)
        page.set_default_timeout(60000)

        board_urls = get_board_urls(page, MAX_BOARDS)

        for board_url in board_urls:
            print(f"Processing board: {board_url}")
            image_urls = get_image_urls_from_board(page, board_url)

            for img_url in image_urls:
                if download_image(img_url, OUTPUT_DIR):
                    total_downloaded += 1

            # NEW LOG HERE:
            print(f"Finished board: {board_url} — total downloaded so far: {total_downloaded}")

        browser.close()

    print(f"\nDownloaded {total_downloaded} images total.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import requests
import piexif
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# ==========================
# CONFIG – loaded from config.json
# ==========================
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
OUTPUT_DIR = SCRIPT_DIR / "downloads"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(
            f"Config file not found: {CONFIG_PATH}\n"
            f"Copy config.json.template to config.json and fill in your credentials.",
            file=sys.stderr,
        )
        sys.exit(1)
    with CONFIG_PATH.open() as f:
        cfg = json.load(f)
    for key in ("email", "password", "child_id", "kindergarten_id"):
        if not cfg.get(key):
            print(f"Missing '{key}' in {CONFIG_PATH}", file=sys.stderr)
            sys.exit(1)
    return cfg

LOGIN_URL = "https://usergateway-services.kinderpedia.co/api/login"
GALLERY_LIST_URL = (
    "https://app.kinderpedia.co/web-api/data/gallery"
    "?mode=albums&page={page}&items_per_page=15"
    "&search_title=&search_date_start=&search_date_end=&search_author_id="
    "&order_by=updated_at&order_type=DESC"
)
ALBUM_DETAIL_URL = "https://app.kinderpedia.co/web-api/data/gallery/{album_id}"

VIDEO_GALLERY_LIST_URL = (
    "https://app.kinderpedia.co/web-api/data/gallery"
    "?mode=videos&page={page}&items_per_page=15"
    "&search_title=&search_date_start=&search_date_end=&search_author_id="
    "&order_by=updated_at&order_type=DESC"
)
VIDEO_DETAIL_URL = "https://app.kinderpedia.co/web-api/data/gallery/{video_id}?mode=video"

API_KEY = "Web01Pari3l4em|v1.02"   # from your curl command


# ==========================
# RETRY / RATE-LIMIT HANDLING
# ==========================

MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 10   # seconds; doubles each retry

def api_get(session: requests.Session, url: str) -> requests.Response:
    """
    GET with automatic retry on HTTP 429 (Too Many Requests).
    Uses exponential back-off: 10 s, 20 s, 40 s, 80 s, 160 s.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        resp = session.get(url)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
        print(f"    [RATE-LIMITED] 429 on attempt {attempt}/{MAX_RETRIES}, "
              f"retrying in {wait}s …")
        time.sleep(wait)
    # Final attempt – let the exception propagate
    resp.raise_for_status()
    return resp   # unreachable, but keeps type-checkers happy


# ==========================
# HELPER FUNCTIONS
# ==========================

def slugify(value: str) -> str:
    """
    Make a filesystem-safe folder/file name from arbitrary text.
    """
    value = value.strip()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)  # remove weird chars
    value = re.sub(r"[-\s]+", " ", value).strip()           # collapse whitespace
    value = value.replace(" ", "_")                          # spaces -> underscore
    if not value:
        value = "album"
    return value


def parse_dateadd(date_str: str):
    """
    Parse dateadd string like '2025-11-07T14:01:06+0200' into a POSIX timestamp (float).
    Returns None on failure.
    """
    if not date_str:
        return None
    try:
        # Normalize timezone offset from +HHMM to +HH:MM if needed
        # Example: '2025-11-07T14:01:06+0200' -> '2025-11-07T14:01:06+02:00'
        if len(date_str) > 5 and (date_str[-5] in ["+", "-"]) and date_str[-3] != ":":
            date_str = date_str[:-2] + ":" + date_str[-2:]
        dt = datetime.fromisoformat(date_str)
        return dt.timestamp()
    except Exception:
        return None


def login(email: str, password: str) -> str:
    """
    Perform login and return JWToken.
    """
    print("[*] Logging in…")
    resp = requests.post(LOGIN_URL, json={"email": email, "password": password})
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token")
    if not token:
        raise RuntimeError("Login succeeded but no 'token' field in response.")
    print("[+] Got JWT token.")
    return token


def make_session(token: str, cfg: dict) -> requests.Session:
    """
    Create a requests Session with default headers and JWToken cookie.
    """
    s = requests.Session()
    s.cookies.set("JWToken", token, domain="kinderpedia.co")

    s.headers.update({
        "x-child-id": cfg["child_id"],
        "x-kindergarten-id": cfg["kindergarten_id"],
        "x-requested-with": "XMLHttpRequest",
        "x-api-key": API_KEY,
        "User-Agent": "KinderpediaDownloader/1.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })
    return s


def fetch_gallery_page(session: requests.Session, page: int) -> dict:
    url = GALLERY_LIST_URL.format(page=page)
    resp = api_get(session, url)
    return resp.json()


def fetch_all_albums(session: requests.Session) -> list[dict]:
    """
    Fetch all album entries across paginated gallery.
    """
    print("[*] Fetching gallery albums (page 1)…")
    first = fetch_gallery_page(session, 1)
    result = first.get("result") or {}
    albums = result.get("albums") or []
    pagination = result.get("pagination") or {}
    pages_count = pagination.get("pages_count", 1)

    print(f"[+] Found {len(albums)} albums on page 1, total pages: {pages_count}")

    for page in range(2, pages_count + 1):
        print(f"[*] Fetching gallery page {page}/{pages_count}…")
        data = fetch_gallery_page(session, page)
        r = data.get("result") or {}
        page_albums = r.get("albums") or []
        print(f"    -> {len(page_albums)} albums")
        albums.extend(page_albums)

    print(f"[+] Total albums: {len(albums)}")
    return albums


def fetch_video_gallery_page(session: requests.Session, page: int) -> dict:
    """
    Fetch a page of videos from the gallery.
    """
    url = VIDEO_GALLERY_LIST_URL.format(page=page)
    resp = api_get(session, url)
    return resp.json()


def fetch_all_videos(session: requests.Session) -> list[dict]:
    """
    Fetch all video entries across the paginated video gallery.
    """
    print("[*] Fetching video gallery (page 1)…")
    first = fetch_video_gallery_page(session, 1)
    result = first.get("result") or {}
    videos = result.get("videos") or []
    pagination = result.get("pagination") or {}
    pages_count = pagination.get("pages_count", 1)

    print(f"[+] Found {len(videos)} videos on page 1, total pages: {pages_count}")

    for page in range(2, pages_count + 1):
        print(f"[*] Fetching video gallery page {page}/{pages_count}…")
        data = fetch_video_gallery_page(session, page)
        r = data.get("result") or {}
        page_videos = r.get("videos") or []
        print(f"    -> {len(page_videos)} videos")
        videos.extend(page_videos)

    print(f"[+] Total videos: {len(videos)}")
    return videos


def fetch_video_detail(session: requests.Session, video_id: int) -> dict:
    """
    Fetch detailed information for a single video.
    """
    url = VIDEO_DETAIL_URL.format(video_id=video_id)
    resp = api_get(session, url)
    return resp.json()


def fetch_album_detail(session: requests.Session, album_id: int) -> dict:
    url = ALBUM_DETAIL_URL.format(album_id=album_id)
    resp = api_get(session, url)
    return resp.json()


def download_all_videos(session: requests.Session, out_base: Path):
    """
    Download all videos from the video gallery.

    Behaviour:
      * Group videos by album name (video 'name' field).
      * Folder name is slugified album name, same logic as for photos.
      * For each album, name files "{album_name} 1.mp4", "{album_name} 2.mp4", etc.
      * Create folder if it doesn't exist (video-only album).
      * For Vimeo videos, use yt_dlp (if installed) to download from the
        player/share URL into the computed filename.
      * For non-Vimeo videos (if any), fall back to using images["l"] as a
        direct URL and download via a simple GET, like the photos.
    """
    videos = fetch_all_videos(session)
    if not videos:
        print("\n[+] No videos found in gallery.")
        return

    # Group videos by album (name)
    albums: dict[str, list[dict]] = {}
    album_display_names: dict[str, str] = {}

    for video in videos:
        video_name = video.get("name") or f"video_{video.get('id')}"
        safe_album_name = slugify(video_name)

        albums.setdefault(safe_album_name, []).append(video)
        # Keep the first human-readable display name for this album
        album_display_names.setdefault(safe_album_name, video_name)

    print(f"\n[+] Starting video download for {len(videos)} video(s) in {len(albums)} album(s).")

    # Process videos per album
    for safe_album_name, album_videos in albums.items():
        album_folder = out_base / safe_album_name
        is_new_folder = False
        if not album_folder.exists():
            album_folder.mkdir(parents=True, exist_ok=True)
            is_new_folder = True

        album_name = album_display_names.get(safe_album_name, safe_album_name)

        print(f"\n[VIDEO ALBUM] {album_name}")
        print(f"  Folder    : {album_folder}")
        print(f"  Videos    : {len(album_videos)}")
        print(f"  Status    : {'created folder (video-only or new album)' if is_new_folder else 'using existing folder'}")

        # Optional: sort videos in album by date for deterministic order
        def video_sort_key(v: dict) -> str:
            return v.get("date") or ""

        album_videos_sorted = sorted(album_videos, key=video_sort_key)

        # Now iterate videos in this album and name them sequentially
        for idx_in_album, video in enumerate(album_videos_sorted, start=1):
            video_id = video.get("id")
            if video_id is None:
                continue

            print(f"\n  [VIDEO] id={video_id} (album index {idx_in_album})")

            # Try to get a detailed record; fall back to list entry if it fails
            detail = None
            try:
                detail = fetch_video_detail(session, video_id)
            except Exception as e:
                print(f"    [WARN] Could not fetch detail for video {video_id}: {e}")

            if detail and isinstance(detail, dict):
                result = detail.get("result") or {}
                video_info = result.get("video") or {}
            else:
                video_info = video

            video_name = video_info.get("name") or album_name
            date_str = video_info.get("date") or video.get("date")
            ts = parse_dateadd(date_str)

            # Base filename is the album name (as requested), sanitized
            base_filename = album_name.replace("/", "-").replace("\\", "-")
            filename = f"{base_filename} {idx_in_album}.mp4"
            dest = album_folder / filename

            if dest.exists():
                print(f"    -> File already exists, skipping: {dest.name}")
                continue

            # Determine platform (e.g. vimeo)
            platform = video_info.get("platform") or video.get("platform") or {}
            platform_type = (platform.get("type") or "").lower()

            # Vimeo videos: use yt_dlp, since direct config access is blocked (403)
            if platform_type == "vimeo":
                player_url = (
                    video_info.get("url")
                    or video_info.get("share_url")
                    or video.get("url")
                    or video.get("share_url")
                )

                if not player_url:
                    print("    [WARN] Vimeo platform but no player/share URL found, skipping.")
                    continue

                print(f"    Vimeo player URL: {player_url}")
                print("    [INFO] Downloading Vimeo video via yt_dlp…")
                success = download_vimeo_with_yt_dlp(player_url, dest)
                if success:
                    print(f"    -> Downloaded via yt_dlp to {dest.name}")
                    if ts is not None:
                        try:
                            os.utime(dest, (ts, ts))
                        except Exception as e:
                            print(f"       [WARN] Could not set mtime for {dest}: {e}")
                else:
                    print("    [WARN] Vimeo video could not be downloaded (yt_dlp failed or is missing).")
                # Regardless of success or failure, continue to next video
                continue

            # Non-Vimeo (if ever present) – use images['l'] as a direct URL
            images = video_info.get("images") or video.get("images") or {}
            video_url = images.get("l")
            if not video_url:
                print("    [WARN] Non-Vimeo video with no URL; skipping.")
                continue

            print(f"    Non-Vimeo video URL: {video_url}")
            print(f"    -> Downloading video to {dest.name}")
            try:
                download_file(session, video_url, dest)
                if ts is not None:
                    try:
                        os.utime(dest, (ts, ts))
                    except Exception as e:
                        print(f"       [WARN] Could not set mtime for {dest}: {e}")
            except Exception as e:
                print(f"       [ERROR] Failed to download video {video_id} from {video_url}: {e}")

            time.sleep(0.5)


def download_file(session: requests.Session, url: str, dest: Path):
    """
    Download a single file to 'dest', skipping if it already exists.
    """
    if dest.exists():
        return
    resp = session.get(url, stream=True)
    resp.raise_for_status()
    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def download_vimeo_with_yt_dlp(vimeo_url: str, dest: Path) -> bool:
    """
    Fallback: use yt_dlp (Python lib) to download the Vimeo video directly
    to 'dest'.

    Returns True on success, False otherwise.
    """
    if yt_dlp is None:
        print("    [WARN] yt_dlp is not installed, cannot use fallback Vimeo downloader.")
        print("           Install with: pip install yt-dlp")
        return False

    # yt_dlp will create the file itself; outtmpl must be a string path
    ydl_opts = {
        "outtmpl": str(dest),   # use exact path+name we computed
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([vimeo_url])
        return True
    except Exception as e:
        print(f"    [WARN] yt_dlp failed for {vimeo_url}: {e}")
        return False


# ==========================
# IMAGE / ALBUM DOWNLOAD (UNCHANGED)
# ==========================

def process_image_file_exif_and_timestamp(
    path: Path,
    ts: float | None,
    description: str = "",
):
    """
    Update EXIF DateTimeOriginal / CreateDate, filesystem mtime/atime,
    and optionally embed a description into ImageDescription + UserComment
    (so Apple Photos shows it in the "i" / Get Info panel).
    """
    if ts is None and not description:
        return

    try:
        try:
            exif_dict = piexif.load(str(path))
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        exif_dict.setdefault("0th", {})
        exif_dict.setdefault("Exif", {})

        if ts is not None:
            dt = datetime.fromtimestamp(ts)
            exif_ts = dt.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_ts.encode("utf-8")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = exif_ts.encode("utf-8")

        if description:
            # Primary field Apple Photos reads for the description / caption
            exif_dict["0th"][piexif.ImageIFD.ImageDescription] = description.encode("utf-8")
            # UserComment requires an 8-byte character-code prefix
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = (
                b"ASCII\x00\x00\x00" + description.encode("utf-8")
            )

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(path))

        if ts is not None:
            os.utime(path, (ts, ts))
    except Exception as e:
        print(f"       [WARN] Could not update EXIF/timestamps for {path}: {e}")


def download_album_images(session: requests.Session, album_id: int, list_album_name: str, out_base: Path, idx: int, total: int):
    """
    Download all images for a single album and write metadata/EXIF.
    Skips the remote album detail call entirely if the album folder already exists,
    to avoid unnecessary requests (and 429 rate limits).
    """
    # First decide the folder name based on the name from the album list
    base_album_name = list_album_name or f"album_{album_id}"
    safe_album_name = slugify(base_album_name)
    album_folder = out_base / safe_album_name

    # EARLY SKIP: only if the folder exists AND contains actual media files
    # (not just readme.txt or an empty directory from a video-only pass)
    if album_folder.exists():
        existing_files = [
            f for f in album_folder.iterdir()
            if f.is_file() and f.name.lower() != "readme.txt"
        ]
        if existing_files:
            print(f"\n[ALBUM {idx}/{total}] id={album_id}")
            print(f"  Name      : {base_album_name}")
            print(f"  Folder    : {album_folder}")
            print(f"  Status    : SKIP (folder already has {len(existing_files)} media file(s))")
            return

    # Only now call the album detail endpoint
    detail = fetch_album_detail(session, album_id)

    # Be defensive: result / album / images might be null
    result = detail.get("result") or {}
    album_info = result.get("album") or {}
    images = result.get("images") or []

    album_name = album_info.get("name") or base_album_name
    album_desc = album_info.get("description") or ""

    # Recompute folder name from the detailed album name (usually the same)
    safe_album_name = slugify(album_name)
    album_folder = out_base / safe_album_name
    album_folder.mkdir(parents=True, exist_ok=True)

    print(f"\n[ALBUM {idx}/{total}] id={album_id}")
    print(f"  Name      : {album_name}")
    print(f"  Folder    : {album_folder}")
    print(f"  Images    : {len(images)}")

    # Write description to readme.txt
    readme_path = album_folder / "readme.txt"
    if album_desc:
        readme_path.write_text(album_desc, encoding="utf-8")

    # Download each image
    for i, img in enumerate(images, start=1):
        fullsize_url = (
            img.get("download_url")
            or img.get("fullsize")
            or img.get("thumb")
            or img.get("url_l")
            or img.get("url_m")
            or img.get("url_s")
        )
        if not fullsize_url:
            print(f"    -> Image {i}/{len(images)} has no download URL, skipping.")
            continue

        ts = parse_dateadd(img.get("dateadd"))

        base_filename = album_name.replace("/", "-").replace("\\", "-")
        ext = img.get("extension") or "jpg"
        if not ext.startswith("."):
            ext = "." + ext

        filename = f"{base_filename} {i}{ext}"
        dest = album_folder / filename

        print(f"    -> Downloading image {i}/{len(images)} to {dest.name}")
        try:
            download_file(session, fullsize_url, dest)
            if ts is not None or album_desc:
                try:
                    process_image_file_exif_and_timestamp(dest, ts, description=album_desc)
                except Exception as e:
                    print(f"       [WARN] Could not set timestamps for {dest}: {e}")
        except Exception as e:
            print(f"       [ERROR] Failed to download {fullsize_url}: {e}")

        time.sleep(0.5)


# ==========================
# MAIN
# ==========================

def main():
    cfg = load_config()

    out_base = Path(OUTPUT_DIR)
    out_base.mkdir(parents=True, exist_ok=True)

    # 1. Login
    token = login(cfg["email"], cfg["password"])

    # 2. Prepare session with headers + cookie
    session = make_session(token, cfg)

    # 3. Get all albums
    albums = fetch_all_albums(session)

    # 4. Download images for each album
    for idx, album in enumerate(albums, start=1):
        album_id = album.get("id")
        if album_id is None:
            continue
        list_album_name = album.get("name") or f"album_{album_id}"
        download_album_images(session, album_id, list_album_name, out_base, idx, len(albums))

    # 5. Download videos into album folders (creating video-only folders if needed)
    download_all_videos(session, out_base)

    print("\n[✓] Done. All albums and videos processed. Output in:", out_base.resolve())


if __name__ == "__main__":
    main()

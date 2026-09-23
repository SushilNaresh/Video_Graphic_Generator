from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlparse, urlencode

import httpx

from .models import StockDownloadRequest, StockDownloadResponse, StockMediaItem, StockSearchResponse
from .storage import ensure_project_dirs, safe_filename

PEXELS_KEY   = os.getenv("PEXELS_API_KEY", "")
PIXABAY_KEY  = os.getenv("PIXABAY_API_KEY", "")
_UA          = "AIVideoStudio/1.0 (studio@example.com)"
_TIMEOUT     = 12


# ── Pexels ────────────────────────────────────────────────────────────────────

def _pexels_search(query: str, media_type: str, per_page: int = 6) -> list[StockMediaItem]:
    if not PEXELS_KEY:
        return []
    endpoint = "https://api.pexels.com/videos/search" if media_type == "video" else "https://api.pexels.com/v1/search"
    try:
        r = httpx.get(
            endpoint,
            params={"query": query, "per_page": per_page, "orientation": "portrait"},
            headers={"Authorization": PEXELS_KEY},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results: list[StockMediaItem] = []
    if media_type == "video":
        for v in data.get("videos", []):
            files = v.get("video_files", [])
            dl = next((f["link"] for f in files if f.get("quality") in ("hd", "sd")), None)
            if not dl:
                continue
            results.append(StockMediaItem(
                id=f"pexels_v_{v['id']}",
                provider="pexels",
                media_type="video",
                title=v.get("url", "Pexels video").split("/")[-2].replace("-", " ").title(),
                thumb_url=v.get("image", ""),
                download_url=dl,
                width=v.get("width", 1080),
                height=v.get("height", 1920),
                duration=float(v.get("duration", 0)),
                license="Pexels License (free)",
            ))
    else:
        for p in data.get("photos", []):
            results.append(StockMediaItem(
                id=f"pexels_{p['id']}",
                provider="pexels",
                media_type="image",
                title=p.get("alt", "Pexels photo").title(),
                thumb_url=p["src"].get("medium", ""),
                download_url=p["src"].get("large2x", p["src"].get("original", "")),
                width=p.get("width", 1080),
                height=p.get("height", 1920),
                license="Pexels License (free)",
            ))
    return results


# ── Pixabay ───────────────────────────────────────────────────────────────────

def _pixabay_search(query: str, media_type: str, per_page: int = 6) -> list[StockMediaItem]:
    if not PIXABAY_KEY:
        return []
    endpoint = "https://pixabay.com/api/videos/" if media_type == "video" else "https://pixabay.com/api/"
    try:
        r = httpx.get(
            endpoint,
            params={"key": PIXABAY_KEY, "q": query, "per_page": per_page,
                    "image_type": "photo", "orientation": "vertical", "safesearch": "true"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results: list[StockMediaItem] = []
    if media_type == "video":
        for v in data.get("hits", []):
            videos = v.get("videos", {})
            dl = (videos.get("large") or videos.get("medium") or {}).get("url", "")
            if not dl:
                continue
            results.append(StockMediaItem(
                id=f"pixabay_v_{v['id']}",
                provider="pixabay",
                media_type="video",
                title=v.get("tags", "Pixabay video").split(",")[0].strip().title(),
                thumb_url=v.get("picture_id", ""),
                download_url=dl,
                width=videos.get("large", {}).get("width", 1080),
                height=videos.get("large", {}).get("height", 1920),
                duration=float(v.get("duration", 0)),
                license="Pixabay License (free)",
            ))
    else:
        for p in data.get("hits", []):
            results.append(StockMediaItem(
                id=f"pixabay_{p['id']}",
                provider="pixabay",
                media_type="image",
                title=p.get("tags", "Pixabay image").split(",")[0].strip().title(),
                thumb_url=p.get("webformatURL", ""),
                download_url=p.get("largeImageURL", p.get("webformatURL", "")),
                width=p.get("imageWidth", 1080),
                height=p.get("imageHeight", 1920),
                license="Pixabay License (free)",
            ))
    return results


# ── Wikimedia Commons ─────────────────────────────────────────────────────────

def _wikimedia_search(query: str, per_page: int = 4) -> list[StockMediaItem]:
    try:
        r = httpx.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": "6",
                "gsrlimit": str(per_page),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": "800",
                "format": "json",
                "origin": "*",
            },
            headers={"User-Agent": _UA},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results: list[StockMediaItem] = []
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        ii = (page.get("imageinfo") or [{}])[0]
        mime = ii.get("mime", "")
        if not mime.startswith("image/"):
            continue
        url = ii.get("url", "")
        thumb = ii.get("thumburl", url)
        if not url:
            continue
        title = page.get("title", "").replace("File:", "").rsplit(".", 1)[0].replace("_", " ")
        results.append(StockMediaItem(
            id=f"wiki_{abs(hash(url)) % 10**8}",
            provider="wikimedia",
            media_type="image",
            title=title[:80],
            thumb_url=thumb,
            download_url=url,
            width=ii.get("width", 800),
            height=ii.get("height", 600),
            license="Wikimedia Commons (check individual license)",
        ))
    return results


# ── Placeholder fallback ──────────────────────────────────────────────────────

def _placeholder_svg(title: str, color_a: str, color_b: str) -> str:
    safe = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='1080' height='1920' viewBox='0 0 1080 1920'>"
        f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        f"<stop stop-color='{color_a}'/><stop offset='1' stop-color='{color_b}'/></linearGradient></defs>"
        f"<rect width='1080' height='1920' fill='url(#g)'/>"
        f"<circle cx='850' cy='330' r='210' fill='rgba(255,255,255,0.18)'/>"
        f"<circle cx='170' cy='1450' r='270' fill='rgba(15,23,42,0.28)'/>"
        f"<text x='80' y='860' font-family='Inter, Arial' font-size='72' font-weight='800' fill='white'>{safe}</text>"
        f"<text x='84' y='945' font-family='Inter, Arial' font-size='30' fill='rgba(255,255,255,0.82)'>Local placeholder</text>"
        f"</svg>"
    )


def _placeholder_results(query: str) -> list[StockMediaItem]:
    digest = hashlib.sha1(query.encode()).hexdigest()[:8]
    palette = [("#0f172a", "#2563eb"), ("#581c87", "#db2777"), ("#064e3b", "#14b8a6")]
    return [
        StockMediaItem(
            id=f"local_{digest}_{i}",
            provider="local-placeholder",
            media_type="image",
            title=f"{query.title()} #{i}",
            thumb_url=f"/api/media/stock/placeholder/local_{digest}_{i}.svg?title={query}",
            download_url=f"local://placeholder/local_{digest}_{i}.svg?title={query}&a={a.lstrip('#')}&b={b.lstrip('#')}",
            width=1080, height=1920,
            license="Generated placeholder",
        )
        for i, (a, b) in enumerate(palette, 1)
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def search_stock(query: str, media_type: str = "image") -> StockSearchResponse:
    normalized = query.strip() or "medical documentary"
    results: list[StockMediaItem] = []

    results += _pexels_search(normalized, media_type, per_page=4)
    results += _pixabay_search(normalized, media_type, per_page=4)
    if media_type == "image":
        results += _wikimedia_search(normalized, per_page=3)

    # Always pad with placeholders so the UI always has something to show
    if len(results) < 3:
        results += _placeholder_results(normalized)

    return StockSearchResponse(query=normalized, results=results[:12])


def placeholder_svg_response(item_id: str, title: str | None = None) -> str:
    return _placeholder_svg(title or item_id, "#0f172a", "#2563eb")


def _download_url_to_file(url: str, dest: Path) -> None:
    """Stream a remote URL to disk."""
    with httpx.stream("GET", url, headers={"User-Agent": _UA}, timeout=30, follow_redirects=True) as r:
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fh:
            for chunk in r.iter_bytes(chunk_size=64 * 1024):
                fh.write(chunk)


def download_stock(request: StockDownloadRequest) -> StockDownloadResponse:
    pdir = ensure_project_dirs(request.project_id)
    item = request.item
    parsed = urlparse(item.download_url)

    # ── Local placeholder ──
    if parsed.scheme == "local":
        qs = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        filename = safe_filename(f"{item.id}_{item.title}.svg").replace(" ", "_")
        if not filename.endswith(".svg"):
            filename += ".svg"
        path = pdir / "media" / "downloaded" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _placeholder_svg(item.title, f"#{qs.get('a','0f172a')}", f"#{qs.get('b','2563eb')}"),
            encoding="utf-8",
        )
        return StockDownloadResponse(
            media_url=f"/api/media/{request.project_id}/asset/downloaded/{filename}",
            filename=filename,
        )

    # ── Remote URL (Pexels / Pixabay / Wikimedia) ──
    ext = Path(parsed.path).suffix.lower() or (".mp4" if item.media_type == "video" else ".jpg")
    slug = re.sub(r"[^a-z0-9]+", "_", item.title.lower())[:40]
    filename = f"{item.provider}_{item.id}_{slug}{ext}"
    path = pdir / "media" / "downloaded" / filename
    if not path.exists():
        _download_url_to_file(item.download_url, path)
    return StockDownloadResponse(
        media_url=f"/api/media/{request.project_id}/asset/downloaded/{filename}",
        filename=filename,
    )


def auto_download_for_graphic(project_id: str, search_query: str, media_type: str = "image") -> str | None:
    """
    Search + download the best matching stock asset for a graphic automatically.
    Returns the media_url string to attach to the graphic, or None on failure.
    """
    try:
        results = search_stock(search_query, media_type)
        # Prefer real providers over local placeholders
        real = [r for r in results.results if r.provider != "local-placeholder"]
        item = real[0] if real else (results.results[0] if results.results else None)
        if not item:
            return None
        from .models import StockDownloadRequest
        resp = download_stock(StockDownloadRequest(project_id=project_id, item=item))
        return resp.media_url
    except Exception:
        return None

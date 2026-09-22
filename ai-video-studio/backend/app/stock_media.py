from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException

from .models import StockDownloadRequest, StockDownloadResponse, StockMediaItem, StockSearchResponse
from .storage import ensure_project_dirs, safe_filename


def _placeholder_svg(title: str, color_a: str, color_b: str) -> str:
    safe = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='1080' height='1920' viewBox='0 0 1080 1920'>
<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop stop-color='{color_a}'/><stop offset='1' stop-color='{color_b}'/></linearGradient></defs>
<rect width='1080' height='1920' fill='url(#g)'/>
<circle cx='850' cy='330' r='210' fill='rgba(255,255,255,0.18)'/>
<circle cx='170' cy='1450' r='270' fill='rgba(15,23,42,0.28)'/>
<text x='80' y='860' font-family='Inter, Arial' font-size='72' font-weight='800' fill='white'>{safe}</text>
<text x='84' y='945' font-family='Inter, Arial' font-size='30' fill='rgba(255,255,255,0.82)'>Generated local stock placeholder</text>
</svg>"""


def search_stock(query: str, media_type: str = "image") -> StockSearchResponse:
    normalized = query.strip() or "medical documentary"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:8]
    palette = [("#0f172a", "#2563eb"), ("#581c87", "#db2777"), ("#064e3b", "#14b8a6")]
    results: list[StockMediaItem] = []
    for idx, (a, b) in enumerate(palette, start=1):
        item_id = f"local_{digest}_{idx}"
        results.append(
            StockMediaItem(
                id=item_id,
                provider="local-placeholder",
                media_type="image",
                title=f"{normalized.title()} #{idx}",
                thumb_url=f"/api/media/stock/placeholder/{item_id}.svg?title={normalized}",
                download_url=f"local://placeholder/{item_id}.svg?title={normalized}&a={a.lstrip('#')}&b={b.lstrip('#')}",
                width=1080,
                height=1920,
                license="Generated placeholder, safe for local drafts",
            )
        )
    return StockSearchResponse(query=normalized, results=results)


def placeholder_svg_response(item_id: str, title: str | None = None) -> str:
    return _placeholder_svg(title or item_id, "#0f172a", "#2563eb")


def download_stock(request: StockDownloadRequest) -> StockDownloadResponse:
    pdir = ensure_project_dirs(request.project_id)
    parsed = urlparse(request.item.download_url)
    if parsed.scheme != "local":
        raise HTTPException(status_code=400, detail="Only local placeholder downloads are enabled in this scaffold")

    filename = safe_filename(f"{request.item.id}_{request.item.title}.svg").replace(" ", "_")
    if not filename.endswith(".svg"):
        filename += ".svg"
    path = pdir / "media" / "downloaded" / filename
    path.write_text(_placeholder_svg(request.item.title, "#0f172a", "#2563eb"), encoding="utf-8")
    return StockDownloadResponse(media_url=f"/api/media/{request.project_id}/asset/downloaded/{filename}", filename=filename)

from __future__ import annotations

import mimetypes
import os
import subprocess
from pathlib import Path
from urllib.parse import unquote

from fastapi import Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from .storage import free_bytes_for_project, relative_symlink_or_copy, safe_filename

CHUNK_SIZE = 64 * 1024
MIN_FREE_BUFFER_BYTES = 100 * 1024 * 1024
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def decode_upload_filename(raw: str | None, fallback: str = "source.mp4") -> str:
    if not raw:
        return fallback
    return safe_filename(unquote(raw))


def guess_media_type(path: Path) -> str:
    if path.suffix.lower() == ".svg":
        return "image/svg+xml"
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def probe_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return max(0.0, float(result.stdout.strip()))
    except Exception:
        return 0.0


async def stream_request_to_file(
    request: Request,
    project_id: str,
    destination: Path,
    content_length: int | None = Header(default=None),
) -> int:
    if content_length:
        needed = content_length + MIN_FREE_BUFFER_BYTES
        available = free_bytes_for_project(project_id)
        if available < needed:
            raise HTTPException(
                status_code=507,
                detail=(
                    "Insufficient disk space for upload. "
                    f"Need at least {needed} bytes, only {available} bytes available."
                ),
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".upload_{destination.name}.tmp")
    bytes_written = 0
    try:
        with temp_path.open("wb") as handle:
            async for chunk in request.stream():
                if not chunk:
                    continue
                bytes_written += len(chunk)
                handle.write(chunk)
        temp_path.replace(destination)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return bytes_written


def create_proxy(source: Path, proxy_path: Path) -> Path:
    if source.suffix.lower() in {".mp4", ".mov", ".m4v"}:
        relative_symlink_or_copy(source, proxy_path)
        return proxy_path

    proxy_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vf",
                "scale='min(720,iw)':-2",
                "-c:v",
                "libx264",
                "-crf",
                "28",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                str(proxy_path),
            ],
            capture_output=True,
            check=True,
            timeout=120,
        )
    except Exception:
        relative_symlink_or_copy(source, proxy_path)
    return proxy_path


def ranged_file_response(path: Path, request: Request) -> Response:
    if not path.exists():
        raise HTTPException(status_code=404, detail="Media file not found")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    media_type = guess_media_type(path)
    if not range_header:
        return FileResponse(path, media_type=media_type)

    try:
        units, byte_range = range_header.split("=", 1)
        if units != "bytes":
            raise ValueError
        start_text, end_text = byte_range.split("-", 1)
        start = int(start_text or 0)
        end = int(end_text) if end_text else file_size - 1
        end = min(end, file_size - 1)
        if start > end or start >= file_size:
            raise ValueError
    except ValueError:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

    def iterator():
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = handle.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    return StreamingResponse(iterator(), status_code=206, media_type=media_type, headers=headers)

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from . import renderer, stock_media, twelve_labs
from .auto_producer import run_auto_production, synthetic_transcript
from .whisper_transcribe import transcribe as whisper_transcribe
from .media_utils import (
    create_proxy,
    decode_upload_filename,
    guess_media_type,
    probe_duration,
    ranged_file_response,
    stream_request_to_file,
)
from .models import (
    ProjectState,
    RenderProgress,
    RenderResponse,
    StockDownloadRequest,
    StockDownloadResponse,
    StockSearchResponse,
    TaskStatus,
    TwelveLabsCredits,
    TwelveLabsKeyRequest,
    UploadResponse,
)
from .storage import (
    append_activity,
    append_skill_note,
    delete_project,
    default_project,
    ensure_project_dirs,
    list_project_summaries,
    load_project,
    read_activity,
    read_skill_notes,
    safe_filename,
    save_project,
)


def _ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


app = FastAPI(title="AI Video Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-video-studio"}


# ── Projects ──────────────────────────────────────────────────────────────────

@app.get("/api/projects")
def list_projects():
    return list_project_summaries()


@app.post("/api/projects", response_model=ProjectState)
def create_project(payload: dict | None = None):
    name = (payload or {}).get("name") or "Untitled Video Studio Project"
    project = default_project(name=name)
    project = save_project(project)
    append_activity(project.id, [{
        "ts": _ts(), "event": "project_created",
        "reason": f"New project '{project.name}' created with id {project.id}.",
    }])
    return project


@app.get("/api/projects/{project_id}", response_model=ProjectState)
def get_project(project_id: str):
    return load_project(project_id)


@app.delete("/api/projects/{project_id}")
def remove_project(project_id: str):
    try:
        deleted = delete_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": project_id, "deleted": deleted}


@app.post("/api/projects/{project_id}/autosave", response_model=ProjectState)
def autosave_project(project_id: str, project: ProjectState):
    if project.id != project_id:
        project.id = project_id
    saved = save_project(project)
    append_activity(project_id, [{
        "ts": _ts(), "event": "project_autosaved",
        "reason": (
            f"Project autosaved — {len(project.captions)} captions, "
            f"{len(project.graphics)} graphics, duration {project.duration_seconds:.1f}s."
        ),
    }])
    return saved


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.post("/api/projects/{project_id}/transcribe", response_model=ProjectState)
def transcribe_project(project_id: str):
    project = load_project(project_id)
    video_path = Path(project.source_media_path) if project.source_media_path else None
    ts = _ts()
    append_activity(project_id, [{
        "ts": ts, "event": "transcribe_start",
        "reason": f"Transcription requested. Source: {video_path.name if video_path else 'none'}.",
    }])
    if video_path and video_path.exists():
        try:
            project.captions = whisper_transcribe(video_path)
            append_activity(project_id, [{
                "ts": _ts(), "event": "transcribe_done",
                "caption_count": len(project.captions),
                "reason": (
                    f"Whisper (faster-whisper base model) transcribed {len(project.captions)} segments "
                    f"with word-level timestamps from '{video_path.name}'. "
                    f"Language auto-detected. VAD filter applied to skip silence."
                ),
            }])
        except Exception as exc:
            project.captions = synthetic_transcript(project.duration_seconds)
            append_activity(project_id, [{
                "ts": _ts(), "event": "transcribe_fallback",
                "reason": (
                    f"Whisper failed: {exc}. "
                    f"Fell back to synthetic {len(project.captions)}-line placeholder transcript."
                ),
            }])
    else:
        project.captions = synthetic_transcript(project.duration_seconds)
        append_activity(project_id, [{
            "ts": _ts(), "event": "transcribe_synthetic",
            "reason": "No source video on disk. Generated synthetic placeholder transcript.",
        }])
    return save_project(project)


# ── Auto Produce ──────────────────────────────────────────────────────────────

@app.post("/api/projects/{project_id}/auto-produce", response_model=ProjectState)
def auto_produce(project_id: str):
    project = load_project(project_id)
    ts = _ts()
    append_activity(project_id, [{
        "ts": ts, "event": "auto_produce_requested",
        "reason": (
            f"Auto Produce triggered by user. "
            f"Project has {len(project.captions)} existing captions and "
            f"{len(project.graphics)} existing graphics."
        ),
    }])
    project = run_auto_production(project)
    return save_project(project)


# ── Activity Log ──────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/activity-log")
def get_activity_log(project_id: str):
    return read_activity(project_id)


# ── Skill Notes ───────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/skill-notes")
def get_skill_notes(project_id: str):
    return read_skill_notes(project_id)


@app.post("/api/projects/{project_id}/skill-notes")
def add_skill_note(project_id: str, payload: dict):
    from datetime import datetime as _dt
    note = {
        "ts": _dt.utcnow().isoformat() + "Z",
        "graphic_id": payload.get("graphic_id", ""),
        "template_id": payload.get("template_id", ""),
        "trigger": payload.get("trigger", ""),
        "note": payload.get("note", "").strip(),
        "author": payload.get("author", "user"),
    }
    append_skill_note(project_id, note)
    _export_skill_md(project_id)
    return note


def _export_skill_md(project_id: str) -> None:
    """Re-write .agents/skills/ai-video-studio/SKILL.md with latest skill notes appended."""
    import json as _json
    from pathlib import Path as _Path
    notes = read_skill_notes(project_id)
    if not notes:
        return
    skill_path = _Path(__file__).resolve().parents[3] / ".agents" / "skills" / "ai-video-studio" / "SKILL.md"
    if not skill_path.exists():
        return
    base = skill_path.read_text(encoding="utf-8")
    # Remove previous auto-generated block if present
    marker = "\n\n## Learned skill notes (auto-generated)\n"
    base = base.split(marker)[0]
    lines = [marker.lstrip("\n")]
    for n in notes:
        lines.append(f"- **[{n['ts'][:10]}]** `{n['template_id']}` trigger=`{n['trigger']}` — {n['note']}")
    skill_path.write_text(base + marker + "\n".join(lines) + "\n", encoding="utf-8")


# ── Manual Graphics ───────────────────────────────────────────────────────────

@app.post("/api/projects/{project_id}/graphics", response_model=ProjectState)
def add_graphic(project_id: str, payload: dict):
    import uuid as _uuid
    from .models import MotionGraphicItem
    project = load_project(project_id)
    graphic = MotionGraphicItem(
        id=f"gfx_{_uuid.uuid4().hex[:8]}",
        start=float(payload.get("start", 0)),
        end=float(payload.get("end", 1)),
        template_id=payload.get("template_id", "contextual_broll"),
        title=payload.get("title", "New Graphic"),
        parameters=payload.get("parameters", {}),
        track=payload.get("track", "V3"),
        scale=float(payload.get("scale", 1.0)),
    )
    project.graphics.append(graphic)
    append_activity(project_id, [{
        "ts": _ts(), "event": "graphic_added_manual",
        "graphic_id": graphic.id,
        "template_id": graphic.template_id,
        "title": graphic.title,
        "track": graphic.track,
        "start": graphic.start,
        "end": graphic.end,
        "reason": (
            f"User manually placed '{graphic.template_id}' graphic titled '{graphic.title}' "
            f"at {graphic.start:.2f}s–{graphic.end:.2f}s on track {graphic.track}."
        ),
    }])
    return save_project(project)


@app.delete("/api/projects/{project_id}/graphics/{graphic_id}", response_model=ProjectState)
def remove_graphic(project_id: str, graphic_id: str):
    project = load_project(project_id)
    target = next((g for g in project.graphics if g.id == graphic_id), None)
    project.graphics = [g for g in project.graphics if g.id != graphic_id]
    if target:
        append_activity(project_id, [{
            "ts": _ts(), "event": "graphic_deleted",
            "graphic_id": graphic_id,
            "template_id": target.template_id,
            "title": target.title,
            "track": target.track,
            "start": target.start,
            "end": target.end,
            "reason": (
                f"User deleted '{target.template_id}' graphic '{target.title}' "
                f"({target.start:.2f}s–{target.end:.2f}s, track {target.track})."
            ),
        }])
    return save_project(project)


# ── Media Upload ──────────────────────────────────────────────────────────────

@app.post("/api/media/{project_id}/upload", response_model=UploadResponse)
async def upload_video_stream(
    project_id: str,
    request: Request,
    x_filename: str | None = Header(default=None, alias="X-Filename"),
    content_length: int | None = Header(default=None),
):
    pdir = ensure_project_dirs(project_id)
    filename = decode_upload_filename(x_filename)
    destination = pdir / "media" / filename

    append_activity(project_id, [{
        "ts": _ts(), "event": "upload_start",
        "reason": f"Video upload started: '{filename}' ({(content_length or 0) // (1024*1024)} MB).",
    }])

    bytes_written = await stream_request_to_file(request, project_id, destination, content_length=content_length)
    duration = probe_duration(destination)
    proxy_path = create_proxy(destination, pdir / "proxies" / "proxy_720p.mp4")

    project = load_project(project_id)
    project.name = project.name if project.name != project.id else Path(filename).stem
    project.source_media_path = str(destination)
    project.proxy_media_path = str(proxy_path)
    project.duration_seconds = duration
    project = save_project(project)

    append_activity(project_id, [{
        "ts": _ts(), "event": "upload_done",
        "reason": (
            f"Upload complete: '{filename}' — {bytes_written // (1024*1024)} MB written. "
            f"Duration: {duration:.1f}s. "
            f"Proxy: {'symlink' if Path(proxy_path).is_symlink() else 'transcoded'}."
        ),
    }])

    return UploadResponse(
        id=project.id, project_id=project.id, filename=filename,
        bytes_written=bytes_written, duration_seconds=duration, project=project,
    )


@app.get("/api/media/{project_id}/source-video")
def source_video(project_id: str, request: Request):
    project = load_project(project_id)
    path = Path(project.proxy_media_path or project.source_media_path or "")
    return ranged_file_response(path, request)


# ── Asset Upload ──────────────────────────────────────────────────────────────

@app.post("/api/media/{project_id}/upload-asset")
async def upload_asset(project_id: str, file: UploadFile):
    pdir = ensure_project_dirs(project_id)
    filename = safe_filename(file.filename or "asset.bin")
    path = pdir / "assets" / filename
    size = 0
    with path.open("wb") as handle:
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            handle.write(chunk)
    append_activity(project_id, [{
        "ts": _ts(), "event": "asset_uploaded",
        "reason": f"Custom asset '{filename}' uploaded ({size // 1024} KB). Saved to assets/.",
    }])
    return {"filename": filename, "url": f"/api/media/{project_id}/asset/{filename}"}


@app.get("/api/media/{project_id}/asset/{filename}")
def get_asset(project_id: str, filename: str):
    path = ensure_project_dirs(project_id) / "assets" / safe_filename(unquote(filename))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path, media_type=guess_media_type(path))


@app.get("/api/media/{project_id}/asset/downloaded/{filename}")
def get_downloaded_asset(project_id: str, filename: str, request: Request):
    path = ensure_project_dirs(project_id) / "media" / "downloaded" / safe_filename(unquote(filename))
    return ranged_file_response(path, request)


# ── Stock Media ───────────────────────────────────────────────────────────────

@app.get("/api/media/stock/search", response_model=StockSearchResponse)
def stock_search(q: str, media_type: str = "image", project_id: str | None = None):
    result = stock_media.search_stock(q, media_type=media_type)
    if project_id:
        providers = list({r.provider for r in result.results})
        real_count = sum(1 for r in result.results if r.provider != "local-placeholder")
        append_activity(project_id, [{
            "ts": _ts(), "event": "stock_search",
            "search_query": q,
            "reason": (
                f"Stock search for '{q}' ({media_type}) returned {len(result.results)} results "
                f"({real_count} real, rest placeholders). Providers: {', '.join(providers)}."
            ),
        }])
    return result


@app.get("/api/media/stock/placeholder/{item_id}.svg")
def stock_placeholder(item_id: str, title: str | None = None):
    return Response(content=stock_media.placeholder_svg_response(item_id, title), media_type="image/svg+xml")


@app.post("/api/media/stock/download", response_model=StockDownloadResponse)
def stock_download(request: StockDownloadRequest):
    result = stock_media.download_stock(request)
    append_activity(request.project_id, [{
        "ts": _ts(), "event": "stock_downloaded",
        "search_query": request.item.title,
        "reason": (
            f"Stock asset '{request.item.title}' downloaded from {request.item.provider}. "
            f"Saved as '{result.filename}'. Attached to project media."
        ),
    }])
    return result


# ── Twelve Labs ───────────────────────────────────────────────────────────────

@app.get("/api/media/twelve-labs/credits", response_model=TwelveLabsCredits)
def get_twelve_labs_credits():
    return twelve_labs.credits()


@app.post("/api/media/twelve-labs/set-key")
def set_twelve_labs_key(payload: TwelveLabsKeyRequest):
    result = twelve_labs.set_key(payload.api_key)
    # Log to all open projects is not practical; key is global — no project_id here
    return result


@app.post("/api/media/{project_id}/twelve-labs/analyze", response_model=TaskStatus)
def analyze_twelve_labs(project_id: str):
    project = load_project(project_id)
    append_activity(project_id, [{
        "ts": _ts(), "event": "analyze_start",
        "reason": (
            "Twelve Labs Analyze triggered. Running local semantic engine "
            "(stub — configure Twelve Labs API key for real video intelligence)."
        ),
    }])
    task = twelve_labs.analyze_project(project)
    append_activity(project_id, [{
        "ts": _ts(), "event": "analyze_done",
        "graphic_count": len(task.graphics),
        "reason": (
            f"Analysis complete. {len(task.graphics)} graphics generated. "
            f"Task id: {task.task_id}. Status: {task.status}."
        ),
    }])
    return task


@app.get("/api/media/twelve-labs/task/{task_id}", response_model=TaskStatus)
def get_twelve_labs_task(task_id: str):
    return twelve_labs.task(task_id)


# ── Render ────────────────────────────────────────────────────────────────────

@app.post("/api/media/{project_id}/render-burnin", response_model=RenderResponse)
def render_burnin(project_id: str):
    project = load_project(project_id)
    append_activity(project_id, [{
        "ts": _ts(), "event": "render_start",
        "reason": (
            f"Burn-in render started. Source: '{Path(project.source_media_path or '').name}'. "
            f"Graphics: {len(project.graphics)}, Captions: {len(project.captions)}. "
            f"Encoder: h264_videotoolbox (falls back to stream copy)."
        ),
    }])
    render_id, output_url = renderer.start_render(project)
    return RenderResponse(render_id=render_id, status="queued", output_url=output_url)


@app.get("/api/media/{project_id}/burnin-progress", response_model=RenderProgress)
def burnin_progress(project_id: str):
    progress = renderer.get_render_progress(project_id)
    # Log terminal states once (renderer sets them exactly once)
    if progress.status == "ready" and progress.progress == 1.0:
        existing = read_activity(project_id)
        already_logged = any(e.get("event") == "render_done" for e in existing[-5:])
        if not already_logged:
            append_activity(project_id, [{
                "ts": _ts(), "event": "render_done",
                "reason": f"Render complete. Output ready for download. Render id: {progress.render_id}.",
            }])
    elif progress.status == "failed":
        existing = read_activity(project_id)
        already_logged = any(e.get("event") == "render_failed" for e in existing[-5:])
        if not already_logged:
            append_activity(project_id, [{
                "ts": _ts(), "event": "render_failed",
                "reason": f"Render failed: {progress.message}.",
            }])
    return progress


@app.get("/api/media/{project_id}/download-mp4")
def download_mp4(project_id: str):
    path = renderer.latest_render_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Rendered file not found")
    append_activity(project_id, [{
        "ts": _ts(), "event": "render_downloaded",
        "reason": f"Rendered MP4 downloaded by user. File: '{path.name}' ({path.stat().st_size // (1024*1024)} MB).",
    }])
    return FileResponse(path, media_type="video/mp4", filename=f"{project_id}_burned.mp4")

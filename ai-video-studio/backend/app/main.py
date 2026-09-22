from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from . import renderer, stock_media, twelve_labs
from .auto_producer import run_auto_production, synthetic_transcript
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
    delete_project,
    default_project,
    ensure_project_dirs,
    list_project_summaries,
    load_project,
    safe_filename,
    save_project,
)

app = FastAPI(title="AI Video Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-video-studio"}


@app.get("/api/projects")
def list_projects():
    return list_project_summaries()


@app.post("/api/projects", response_model=ProjectState)
def create_project(payload: dict | None = None):
    project = default_project(name=(payload or {}).get("name"))
    return save_project(project)


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
    return save_project(project)


@app.post("/api/projects/{project_id}/transcribe", response_model=ProjectState)
def transcribe_project(project_id: str):
    project = load_project(project_id)
    project.captions = synthetic_transcript(project.duration_seconds)
    return save_project(project)


@app.post("/api/projects/{project_id}/auto-produce", response_model=ProjectState)
def auto_produce(project_id: str):
    project = load_project(project_id)
    return save_project(run_auto_production(project))


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
    bytes_written = await stream_request_to_file(request, project_id, destination, content_length=content_length)

    duration = probe_duration(destination)
    proxy_path = create_proxy(destination, pdir / "proxies" / "proxy_720p.mp4")

    project = load_project(project_id)
    project.name = project.name if project.name != project.id else Path(filename).stem
    project.source_media_path = str(destination)
    project.proxy_media_path = str(proxy_path)
    project.duration_seconds = duration
    project = save_project(project)

    return UploadResponse(
        id=project.id,
        project_id=project.id,
        filename=filename,
        bytes_written=bytes_written,
        duration_seconds=duration,
        project=project,
    )


@app.get("/api/media/{project_id}/source-video")
def source_video(project_id: str, request: Request):
    project = load_project(project_id)
    path = Path(project.proxy_media_path or project.source_media_path or "")
    return ranged_file_response(path, request)


@app.post("/api/media/{project_id}/upload-asset")
async def upload_asset(project_id: str, file: UploadFile):
    pdir = ensure_project_dirs(project_id)
    filename = safe_filename(file.filename or "asset.bin")
    path = pdir / "assets" / filename
    with path.open("wb") as handle:
        while True:
            chunk = await file.read(64 * 1024)
            if not chunk:
                break
            handle.write(chunk)
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


@app.get("/api/media/stock/search", response_model=StockSearchResponse)
def stock_search(q: str, media_type: str = "image"):
    return stock_media.search_stock(q, media_type=media_type)


@app.get("/api/media/stock/placeholder/{item_id}.svg")
def stock_placeholder(item_id: str, title: str | None = None):
    return Response(content=stock_media.placeholder_svg_response(item_id, title), media_type="image/svg+xml")


@app.post("/api/media/stock/download", response_model=StockDownloadResponse)
def stock_download(request: StockDownloadRequest):
    return stock_media.download_stock(request)


@app.get("/api/media/twelve-labs/credits", response_model=TwelveLabsCredits)
def get_twelve_labs_credits():
    return twelve_labs.credits()


@app.post("/api/media/twelve-labs/set-key")
def set_twelve_labs_key(payload: TwelveLabsKeyRequest):
    return twelve_labs.set_key(payload.api_key)


@app.post("/api/media/{project_id}/twelve-labs/analyze", response_model=TaskStatus)
def analyze_twelve_labs(project_id: str):
    return twelve_labs.analyze_project(load_project(project_id))


@app.get("/api/media/twelve-labs/task/{task_id}", response_model=TaskStatus)
def get_twelve_labs_task(task_id: str):
    return twelve_labs.task(task_id)


@app.post("/api/media/{project_id}/render-burnin", response_model=RenderResponse)
def render_burnin(project_id: str):
    project = load_project(project_id)
    render_id, output_url = renderer.start_render(project)
    return RenderResponse(render_id=render_id, status="queued", output_url=output_url)


@app.get("/api/media/{project_id}/burnin-progress", response_model=RenderProgress)
def burnin_progress(project_id: str):
    return renderer.get_render_progress(project_id)


@app.get("/api/media/{project_id}/download-mp4")
def download_mp4(project_id: str):
    path = renderer.latest_render_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Rendered file not found")
    return FileResponse(path, media_type="video/mp4", filename=f"{project_id}_burned.mp4")

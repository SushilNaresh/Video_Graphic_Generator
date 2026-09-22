from __future__ import annotations

import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from .models import ProjectState, RenderProgress
from .storage import ensure_project_dirs

_RENDER_PROGRESS: dict[str, RenderProgress] = {}
_PROJECT_RENDER: dict[str, str] = {}


def _set(project_id: str, progress: RenderProgress) -> None:
    _RENDER_PROGRESS[project_id] = progress


def get_render_progress(project_id: str) -> RenderProgress:
    return _RENDER_PROGRESS.get(project_id, RenderProgress())


def latest_render_path(project_id: str) -> Path:
    return ensure_project_dirs(project_id) / "renders" / "burned_output.mp4"


def _render_copy_or_transcode(project: ProjectState, render_id: str) -> None:
    output = latest_render_path(project.id)
    source = Path(project.source_media_path or "")
    try:
        _set(project.id, RenderProgress(render_id=render_id, status="running", progress=0.1, message="Preparing render"))
        if not source.exists():
            raise FileNotFoundError("Source video is missing")

        _set(project.id, RenderProgress(render_id=render_id, status="running", progress=0.35, message="Encoding preview output"))
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source),
                    "-c:v",
                    "h264_videotoolbox",
                    "-b:v",
                    "8M",
                    "-c:a",
                    "aac",
                    str(output),
                ],
                capture_output=True,
                check=True,
                timeout=600,
            )
        except Exception:
            shutil.copy2(source, output)

        _set(project.id, RenderProgress(render_id=render_id, status="ready", progress=1.0, message="Render ready"))
    except Exception as exc:
        _set(project.id, RenderProgress(render_id=render_id, status="failed", progress=0.0, message=str(exc)))


def start_render(project: ProjectState) -> tuple[str, str]:
    render_id = f"render_{uuid.uuid4().hex[:8]}"
    _PROJECT_RENDER[project.id] = render_id
    _set(project.id, RenderProgress(render_id=render_id, status="queued", progress=0.0, message="Queued"))
    thread = threading.Thread(target=_render_copy_or_transcode, args=(project, render_id), daemon=True)
    thread.start()
    return render_id, f"/api/media/{project.id}/download-mp4"

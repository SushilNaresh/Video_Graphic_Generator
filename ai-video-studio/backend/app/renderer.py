from __future__ import annotations

import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from .models import ProjectState, RenderProgress
from .storage import append_activity, ensure_project_dirs

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
        append_activity(project.id, [{"ts": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            "event": "render_running",
            "reason": f"Render thread started. Checking source file: '{source.name}'."}])

        if not source.exists():
            raise FileNotFoundError(f"Source video not found: {source}")

        _set(project.id, RenderProgress(render_id=render_id, status="running", progress=0.35, message="Encoding with VideoToolbox"))
        encoder_used = "h264_videotoolbox"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(source),
                 "-c:v", "h264_videotoolbox", "-b:v", "8M", "-c:a", "aac", str(output)],
                capture_output=True, check=True, timeout=600,
            )
        except Exception:
            encoder_used = "stream_copy_fallback"
            _set(project.id, RenderProgress(render_id=render_id, status="running", progress=0.6, message="VideoToolbox unavailable — copying stream"))
            append_activity(project.id, [{"ts": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
                "event": "render_encoder_fallback",
                "reason": "h264_videotoolbox unavailable. Falling back to direct stream copy."}])
            shutil.copy2(source, output)

        size_mb = output.stat().st_size // (1024 * 1024) if output.exists() else 0
        _set(project.id, RenderProgress(render_id=render_id, status="ready", progress=1.0, message="Render ready"))
        append_activity(project.id, [{"ts": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            "event": "render_done",
            "reason": f"Render complete. Encoder: {encoder_used}. Output: '{output.name}' ({size_mb} MB)."}])

    except Exception as exc:
        _set(project.id, RenderProgress(render_id=render_id, status="failed", progress=0.0, message=str(exc)))
        append_activity(project.id, [{"ts": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            "event": "render_failed",
            "reason": f"Render failed: {exc}."}])


def start_render(project: ProjectState) -> tuple[str, str]:
    render_id = f"render_{uuid.uuid4().hex[:8]}"
    _PROJECT_RENDER[project.id] = render_id
    _set(project.id, RenderProgress(render_id=render_id, status="queued", progress=0.0, message="Queued"))
    thread = threading.Thread(target=_render_copy_or_transcode, args=(project, render_id), daemon=True)
    thread.start()
    return render_id, f"/api/media/{project.id}/download-mp4"

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import ProjectState, ProjectSummary


ROOT_DIR = Path(__file__).resolve().parents[2]
PROJECTS_DIR = Path(os.getenv("STUDIO_PROJECTS_DIR", ROOT_DIR / "projects")).resolve()
STATE_FILE = "project.json"


def utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def ensure_projects_dir() -> Path:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTS_DIR


def project_dir(project_id: str) -> Path:
    safe_id = project_id.replace("/", "_").replace("..", "_")
    return ensure_projects_dir() / safe_id


def ensure_project_dirs(project_id: str) -> Path:
    pdir = project_dir(project_id)
    for subdir in ("media", "media/downloaded", "assets", "renders", "thumbnails", "proxies"):
        (pdir / subdir).mkdir(parents=True, exist_ok=True)
    return pdir


def new_project_id(prefix: str = "proj") -> str:
    return f"{prefix}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def default_project(name: str | None = None, project_id: str | None = None) -> ProjectState:
    pid = project_id or new_project_id()
    return ProjectState(id=pid, name=name or "Untitled Video Studio Project")


def state_path(project_id: str) -> Path:
    return project_dir(project_id) / STATE_FILE


def save_project(project: ProjectState) -> ProjectState:
    ensure_project_dirs(project.id)
    project.updated_at = utc_now()
    path = state_path(project.id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)
    return project


def load_project(project_id: str) -> ProjectState:
    path = state_path(project_id)
    if not path.exists():
        project = default_project(project_id=project_id, name=project_id)
        return save_project(project)
    return ProjectState.model_validate_json(path.read_text(encoding="utf-8"))


def iter_projects() -> Iterable[ProjectState]:
    ensure_projects_dir()
    for path in sorted(PROJECTS_DIR.glob(f"*/{STATE_FILE}"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            project = ProjectState.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if project_dir(project.id).exists():
            yield project


def list_project_summaries() -> list[ProjectSummary]:
    summaries: list[ProjectSummary] = []
    for project in iter_projects():
        summaries.append(
            ProjectSummary(
                id=project.id,
                name=project.name,
                duration_seconds=project.duration_seconds,
                has_source_video=bool(project.source_media_path and Path(project.source_media_path).exists()),
                updated_at=project.updated_at,
            )
        )
    return summaries


def delete_project(project_id: str) -> bool:
    root = ensure_projects_dir().resolve()
    pdir = project_dir(project_id).resolve()
    if root == pdir or root not in pdir.parents:
        raise ValueError("Refusing to delete outside the projects directory")
    if not pdir.exists():
        return False
    shutil.rmtree(pdir)
    return True


def free_bytes_for_project(project_id: str) -> int:
    pdir = ensure_project_dirs(project_id)
    return shutil.disk_usage(pdir).free


def relative_symlink_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        rel = os.path.relpath(source, target.parent)
        target.symlink_to(rel)
    except OSError:
        shutil.copy2(source, target)


def safe_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in "._- ()[]").strip()
    return cleaned or f"upload_{uuid.uuid4().hex[:8]}.mp4"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


ACTIVITY_LOG_FILE = "activity_log.json"
SKILL_NOTES_FILE = "skill_notes.json"


def activity_log_path(project_id: str) -> Path:
    return project_dir(project_id) / ACTIVITY_LOG_FILE


def append_activity(project_id: str, entries: list[dict]) -> None:
    """Append entries to the project activity log (creates if missing)."""
    path = activity_log_path(project_id)
    existing: list[dict] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    write_json(path, existing + entries)


def read_activity(project_id: str) -> list[dict]:
    path = activity_log_path(project_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def skill_notes_path(project_id: str) -> Path:
    return project_dir(project_id) / SKILL_NOTES_FILE


def append_skill_note(project_id: str, note: dict) -> None:
    """Append a manual skill note to skill_notes.json."""
    path = skill_notes_path(project_id)
    existing: list[dict] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    write_json(path, existing + [note])


def read_skill_notes(project_id: str) -> list[dict]:
    path = skill_notes_path(project_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

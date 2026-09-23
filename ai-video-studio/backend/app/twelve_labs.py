from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from .auto_producer import run_auto_production
from .models import ProjectState, TaskStatus, TwelveLabsCredits
from .storage import PROJECTS_DIR, append_activity, ensure_projects_dir, save_project, write_json

TASKS: dict[str, TaskStatus] = {}
KEY_FILE = "twelve_labs_key.json"
USAGE_FILE = "twelve_labs_usage.json"


def _ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _key_path() -> Path:
    return ensure_projects_dir() / KEY_FILE


def _usage_path() -> Path:
    return ensure_projects_dir() / USAGE_FILE


def set_key(api_key: str) -> dict[str, str | bool]:
    masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "configured"
    write_json(_key_path(), {"api_key": api_key, "masked": masked})
    return {"configured": True, "masked": masked}


def credits() -> TwelveLabsCredits:
    configured = _key_path().exists()
    consumed = 0.0
    if _usage_path().exists():
        try:
            consumed = float(json.loads(_usage_path().read_text(encoding="utf-8")).get("consumed_minutes", 0.0))
        except Exception:
            consumed = 0.0
    return TwelveLabsCredits(configured=configured, consumed_minutes=consumed, remaining_minutes=max(0.0, 600.0 - consumed))


def analyze_project(project: ProjectState) -> TaskStatus:
    task_id = f"tl_{uuid.uuid4().hex[:10]}"
    append_activity(project.id, [{
        "ts": _ts(), "event": "twelve_labs_analyze_start",
        "reason": (
            f"Twelve Labs analyze_project called. Task id: {task_id}. "
            "Running local semantic engine (stub). "
            "Configure TWELVE_LABS_API_KEY to enable real Pegasus 1.5 video intelligence."
        ),
    }])
    project = run_auto_production(project)
    save_project(project)
    status = TaskStatus(
        task_id=task_id,
        status="ready",
        progress=1.0,
        message="Local semantic analysis complete. Configure Twelve Labs key to replace this stub with remote video intelligence.",
        graphics=project.graphics,
    )
    TASKS[task_id] = status
    append_activity(project.id, [{
        "ts": _ts(), "event": "twelve_labs_analyze_done",
        "graphic_count": len(project.graphics),
        "reason": (
            f"Analysis complete via local engine. {len(project.graphics)} graphics placed. "
            f"Task {task_id} marked ready."
        ),
    }])
    return status


def task(task_id: str) -> TaskStatus:
    return TASKS.get(task_id, TaskStatus(task_id=task_id, status="failed", progress=0.0, message="Task not found"))

from __future__ import annotations

import re
import uuid
from pathlib import Path

from .models import CaptionItem, MotionGraphicItem, ProjectState, WordTiming
from .storage import append_activity, ensure_project_dirs, write_json

BROLL_SECONDS = 1.0
MEASUREMENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:cm|mm|feet|ft|%|percent|stage)\b", re.I)
MEDICAL_TOPICS = {
    "aging": "accelerated biological aging",
    "obesity": "obesity metabolism clinical health",
    "alcohol": "alcohol liver health documentary",
    "sedentary": "sedentary lifestyle health risk",
    "ct": "radiology chest CT scan",
    "tuberculosis": "tuberculosis lung xray clinical",
    "surgery": "surgeon operating room medical",
    "cancer": "oncology cancer cells clinical research",
    "pollution": "air pollution smog health",
    "research": "medical research report",
    "study": "medical journal research paper",
}


def clamp_broll(start: float, end: float) -> tuple[float, float]:
    if end <= start:
        end = start + BROLL_SECONDS
    return start, min(end, start + BROLL_SECONDS)


def synthetic_transcript(duration: float) -> list[CaptionItem]:
    lines = [
        "Upload complete and ready for editorial production.",
        "Add subtitles, article reconstructions, b-roll, and medical end cards.",
        "The automation engine detects research moments and visual cutaways.",
    ]
    total = max(duration, 9.0)
    step = total / len(lines)
    captions: list[CaptionItem] = []
    for idx, text in enumerate(lines):
        start = round(idx * step, 2)
        end = round(min(total, start + step * 0.82), 2)
        words = []
        tokens = text.split()
        word_step = max(0.2, (end - start) / max(1, len(tokens)))
        for word_idx, token in enumerate(tokens):
            w_start = round(start + word_idx * word_step, 2)
            words.append(WordTiming(text=token, start=w_start, end=round(min(end, w_start + word_step * 0.85), 2)))
        captions.append(CaptionItem(id=f"cap_{idx + 1}", start=start, end=end, text=text, words=words))
    return captions


def graphic_from_topic(topic: str, start: float, line_end: float) -> MotionGraphicItem:
    start, end = clamp_broll(start, line_end)
    return MotionGraphicItem(
        id=f"gfx_{uuid.uuid4().hex[:8]}",
        start=start,
        end=end,
        template_id="contextual_broll",
        title=f"B-roll: {topic.title()}",
        parameters={
            "search_query": topic,
            "visual_reasoning": f"Generated from dialogue topic '{topic}' and clamped to 1 second.",
        },
        track="V3",
    )


def measurement_callout(value: str, start: float) -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"measure_{uuid.uuid4().hex[:8]}",
        start=start,
        end=start + 2.5,
        template_id="dimension_callout",
        title=f"Dimension: {value}",
        parameters={"value": value.upper(), "label": "Measured Statement"},
        track="V5",
    )


def article_reconstruction(start: float, end: float, title: str) -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"article_{uuid.uuid4().hex[:8]}",
        start=start,
        end=max(end, start + 5.0),
        template_id="article_reconstruction",
        title=title,
        parameters={
            "publisher": "Clinical Archive",
            "headline": title,
            "headline_size": 26,
            "paragraph": "A reconstructed research card gives viewers enough time to read evidence while preserving the editorial pace.",
            "paragraph_size": 16,
            "show_highlight": True,
            "highlight_quote": "research card gives viewers enough time to read evidence",
            "marker_color": "#FB923C",
            "show_image": False,
        },
        track="V4",
    )


def medical_endcard(duration: float) -> MotionGraphicItem:
    start = max(0.0, duration)
    return MotionGraphicItem(
        id="medical_endcard_final",
        start=start,
        end=start + 3.0,
        template_id="medical_endcard",
        title="Medical Outro",
        parameters={
            "doctor_name": "Dr. Studio",
            "tagline": "Evidence-first video explainers",
            "handle": "@aivideostudio",
            "cta": "Follow for more",
        },
        track="V5",
    )


def generate_graphics(project: ProjectState) -> list[MotionGraphicItem]:
    captions = project.captions or synthetic_transcript(project.duration_seconds)
    graphics: list[MotionGraphicItem] = []
    article_added = False

    for caption in captions:
        lowered = caption.text.lower()
        measurement = MEASUREMENT_RE.search(caption.text)
        if measurement:
            graphics.append(measurement_callout(measurement.group(0), caption.start))

        if any(word in lowered for word in ("research", "study", "trial", "journal")) and not article_added:
            graphics.append(article_reconstruction(caption.start, caption.end + 3.0, "Clinical Evidence Snapshot"))
            article_added = True
            continue

        for key, query in MEDICAL_TOPICS.items():
            if key in lowered:
                graphics.append(graphic_from_topic(query, caption.start, caption.end))
                break

    if not article_added and captions:
        first = captions[min(1, len(captions) - 1)]
        graphics.append(article_reconstruction(first.start, first.end + 3.0, "AI Video Studio Research Card"))

    graphics.append(medical_endcard(project.duration_seconds))
    return graphics


def run_auto_production(project: ProjectState) -> ProjectState:
    if not project.captions:
        project.captions = synthetic_transcript(project.duration_seconds)
    project.graphics = generate_graphics(project)

    ts = __import__('datetime').datetime.utcnow().isoformat() + 'Z'
    log_entries = [
        {
            "ts": ts,
            "event": "graphic_placed",
            "graphic_id": g.id,
            "template_id": g.template_id,
            "title": g.title,
            "track": g.track,
            "start": g.start,
            "end": g.end,
            "reason": g.parameters.get("visual_reasoning", "Generated by local semantic trigger engine."),
            "search_query": g.parameters.get("search_query", ""),
        }
        for g in project.graphics
    ]
    append_activity(project.id, [
        {"ts": ts, "event": "auto_produce_start", "caption_count": len(project.captions), "reason": "Auto-produce triggered by user."},
        *log_entries,
        {"ts": ts, "event": "auto_produce_done", "graphic_count": len(project.graphics), "reason": f"Placed {len(project.graphics)} graphics across V3/V4/V5."},
    ])

    # Also write legacy visual_reasoning_log for compatibility
    write_json(ensure_project_dirs(project.id) / "thumbnails" / "visual_reasoning_log.json", log_entries)
    return project

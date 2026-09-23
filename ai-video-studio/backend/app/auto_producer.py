from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from .models import CaptionItem, MotionGraphicItem, ProjectState, TrackId, WordTiming
from .storage import append_activity, ensure_project_dirs, write_json

BROLL_SECONDS = 1.0

# ── Regex patterns ────────────────────────────────────────────────────────────

MEASUREMENT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s?(cm|mm|feet|ft|meter|metre|inch|inches|%|percent|stage\s?\d+)\b", re.I
)
STAT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s?(%|percent|times|x\b|fold)", re.I)
CITATION_RE = re.compile(
    r"\b(according to|published in|study by|journal of|new england|lancet|jama|bmj|nejm|"
    r"clinical trial|randomized|meta.analysis|systematic review)\b", re.I
)
JARGON_RE = re.compile(
    r"\b(metastasis|carcinoma|neoplasm|adenocarcinoma|fibrosis|atherosclerosis|"
    r"hypertension|dyslipidemia|comorbidity|pathogenesis|etiology|prognosis)\b", re.I
)
COMPARATIVE_RE = re.compile(
    r"\b(compared to|versus|vs\.?|on the other hand|in contrast|whereas|"
    r"higher than|lower than|more than|less than|double|triple|half)\b", re.I
)

# ── Topic → (search_query, template, track, duration) ────────────────────────

TOPIC_RULES: list[tuple[str, str, str, TrackId, float]] = [
    # (keyword, search_query, visual_reasoning_label, track, duration)
    ("aging",       "accelerated biological aging cells",        "contextual_broll", "V3", 1.0),
    ("obesity",     "obesity metabolism body weight health",     "contextual_broll", "V3", 1.0),
    ("alcohol",     "alcohol liver health documentary",          "contextual_broll", "V3", 1.0),
    ("sedentary",   "sedentary lifestyle sitting health risk",   "contextual_broll", "V3", 1.0),
    ("smoking",     "smoking cigarette lung health",             "contextual_broll", "V3", 1.0),
    ("ct scan",     "radiology chest CT scan medical",           "contextual_broll", "V3", 1.0),
    ("mri",         "MRI brain scan radiology",                  "contextual_broll", "V3", 1.0),
    ("tuberculosis","tuberculosis lung xray clinical",           "contextual_broll", "V3", 1.0),
    ("surgery",     "surgeon operating room medical procedure",  "contextual_broll", "V3", 1.0),
    ("cancer",      "oncology cancer cells clinical research",   "contextual_broll", "V3", 1.0),
    ("tumor",       "tumor biopsy pathology laboratory",         "contextual_broll", "V3", 1.0),
    ("pollution",   "air pollution smog city health",            "contextual_broll", "V3", 1.0),
    ("diabetes",    "diabetes blood sugar insulin medical",      "contextual_broll", "V3", 1.0),
    ("heart",       "heart cardiology echocardiogram medical",   "contextual_broll", "V3", 1.0),
    ("brain",       "brain neurology mri scan medical",          "contextual_broll", "V3", 1.0),
    ("blood",       "blood cells laboratory microscope",         "contextual_broll", "V3", 1.0),
    ("vaccine",     "vaccine syringe immunization medical",      "contextual_broll", "V3", 1.0),
    ("diet",        "healthy diet nutrition food medical",       "contextual_broll", "V3", 1.0),
    ("exercise",    "exercise fitness health workout",           "contextual_broll", "V3", 1.0),
    ("stress",      "stress mental health anxiety",              "contextual_broll", "V3", 1.0),
    ("sleep",       "sleep disorder insomnia health",            "contextual_broll", "V3", 1.0),
    ("research",    "medical research laboratory scientist",     "contextual_broll", "V3", 1.0),
    ("study",       "medical journal research paper",            "contextual_broll", "V3", 1.0),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.utcnow().isoformat() + "Z"


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
        tokens = text.split()
        word_step = max(0.2, (end - start) / max(1, len(tokens)))
        words = [
            WordTiming(
                text=token,
                start=round(start + wi * word_step, 2),
                end=round(min(end, start + wi * word_step + word_step * 0.85), 2),
            )
            for wi, token in enumerate(tokens)
        ]
        captions.append(CaptionItem(id=f"cap_{idx + 1}", start=start, end=end, text=text, words=words))
    return captions


# ── Point 4: Collision detection ─────────────────────────────────────────────

def _resolve_collisions(graphics: list[MotionGraphicItem]) -> list[MotionGraphicItem]:
    """
    For each track, sort graphics by start time and push any overlapping clip
    forward so its start = previous clip's end. Preserves duration.
    """
    by_track: dict[str, list[MotionGraphicItem]] = {}
    for g in graphics:
        by_track.setdefault(g.track, []).append(g)

    resolved: list[MotionGraphicItem] = []
    for track, clips in by_track.items():
        clips.sort(key=lambda c: c.start)
        prev_end = 0.0
        for clip in clips:
            duration = clip.end - clip.start
            start = max(clip.start, prev_end)
            end = round(start + duration, 3)
            prev_end = end
            resolved.append(clip.model_copy(update={"start": round(start, 3), "end": end}))

    # Restore original order (by original start time)
    resolved.sort(key=lambda c: c.start)
    return resolved


# ── Graphic factory functions ─────────────────────────────────────────────────

def _broll(query: str, reasoning: str, start: float, end: float,
           media_url: str | None = None) -> MotionGraphicItem:
    s, e = clamp_broll(start, end)
    params: dict = {"search_query": query, "visual_reasoning": reasoning}
    if media_url:
        params["media_url"] = media_url
    return MotionGraphicItem(
        id=f"gfx_{uuid.uuid4().hex[:8]}", start=s, end=e,
        template_id="contextual_broll", title=f"B-roll: {query.split()[0].title()}",
        parameters=params, track="V3",
    )


def _split_screen(query: str, reasoning: str, start: float, end: float,
                  media_url: str | None = None) -> MotionGraphicItem:
    s, e = clamp_broll(start, end)
    params: dict = {"search_query": query, "visual_reasoning": reasoning}
    if media_url:
        params["media_url"] = media_url
    return MotionGraphicItem(
        id=f"split_{uuid.uuid4().hex[:8]}", start=s, end=e,
        template_id="split_screen_vertical", title=f"Split: {query.split()[0].title()}",
        parameters=params, track="V3",
    )


def _stat_counter(value: str, unit: str, start: float) -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"stat_{uuid.uuid4().hex[:8]}", start=start, end=start + 3.0,
        template_id="stat_counter", title=f"Stat: {value}{unit}",
        parameters={
            "value": value, "unit": unit,
            "visual_reasoning": f"Speaker stated a statistic '{value}{unit}' — animated counter emphasises the number.",
        },
        track="V5",
    )


def _dimension_callout(value: str, start: float) -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"dim_{uuid.uuid4().hex[:8]}", start=start, end=start + 2.5,
        template_id="dimension_callout", title=f"Dimension: {value}",
        parameters={
            "value": value.upper(), "label": "Measured Statement",
            "visual_reasoning": f"Speaker stated a physical measurement '{value}' — HUD callout highlights the dimension.",
        },
        track="V5",
    )


def _kinetic_typography(text: str, start: float) -> MotionGraphicItem:
    snippet = text[:40].rstrip()
    return MotionGraphicItem(
        id=f"kt_{uuid.uuid4().hex[:8]}", start=start, end=start + 2.0,
        template_id="kinetic_typography", title=f"KT: {snippet}",
        parameters={
            "text": snippet,
            "visual_reasoning": "Punchy comparative phrase detected — kinetic typography pop emphasises the contrast.",
        },
        track="V5",
    )


def _source_citation(source: str, start: float) -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"cite_{uuid.uuid4().hex[:8]}", start=start, end=start + 2.5,
        template_id="source_citation", title=f"Citation: {source[:30]}",
        parameters={
            "source": source,
            "visual_reasoning": f"Speaker cited a source or study ('{source}') — citation overlay adds credibility.",
        },
        track="V5",
    )


def _jargon_card(term: str, start: float) -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"jargon_{uuid.uuid4().hex[:8]}", start=start, end=start + 3.5,
        template_id="jargon_translation", title=f"Jargon: {term}",
        parameters={
            "term": term,
            "visual_reasoning": f"Medical jargon '{term}' detected — translation card helps viewers understand the term.",
        },
        track="V4",
    )


def _article(start: float, end: float, title: str, paragraph: str = "",
             highlight: str = "") -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"article_{uuid.uuid4().hex[:8]}", start=start, end=max(end, start + 5.0),
        template_id="article_reconstruction", title=title,
        parameters={
            "publisher": "Clinical Archive",
            "headline": title,
            "headline_size": 26,
            "paragraph": paragraph or "A reconstructed research card gives viewers time to read the evidence.",
            "paragraph_size": 16,
            "show_highlight": bool(highlight),
            "highlight_quote": highlight or "",
            "marker_color": "#FB923C",
            "show_image": False,
            "visual_reasoning": f"Research/study reference detected — article reconstruction surfaces the evidence on screen.",
        },
        track="V4",
    )


def _endcard(duration: float) -> MotionGraphicItem:
    start = max(0.0, duration)
    return MotionGraphicItem(
        id="medical_endcard_final", start=start, end=start + 3.0,
        template_id="medical_endcard", title="Medical Outro",
        parameters={
            "doctor_name": "Dr. Studio", "tagline": "Evidence-first video explainers",
            "handle": "@aivideostudio", "cta": "Follow for more",
        },
        track="V5",
    )


# ── Point 3: Expanded trigger engine ─────────────────────────────────────────

def generate_graphics(project: ProjectState) -> list[MotionGraphicItem]:
    from .stock_media import auto_download_for_graphic

    captions = project.captions
    graphics: list[MotionGraphicItem] = []
    article_added = False

    for caption in captions:
        text = caption.text
        lowered = text.lower()
        s, e = caption.start, caption.end

        # ── Measurements → dimension_callout ──────────────────────────────
        for m in MEASUREMENT_RE.finditer(text):
            graphics.append(_dimension_callout(m.group(0), s))

        # ── Stats / percentages → stat_counter ───────────────────────────
        stat_m = STAT_RE.search(text)
        if stat_m and not MEASUREMENT_RE.search(text):
            graphics.append(_stat_counter(stat_m.group(1), stat_m.group(2), s))

        # ── Research / study reference → article_reconstruction ──────────
        if CITATION_RE.search(text) and not article_added:
            g = _article(s, e + 4.0, title=text[:60].rstrip(".,:") + "…", paragraph=text, highlight=text[:80])
            graphics.append(g)
            article_added = True
            continue

        # ── Medical jargon → jargon_translation ──────────────────────────
        jargon_m = JARGON_RE.search(text)
        if jargon_m:
            graphics.append(_jargon_card(jargon_m.group(0), s))
            continue

        # ── Comparative statement → split_screen_vertical ────────────────
        if COMPARATIVE_RE.search(text):
            query = f"comparison {' '.join(text.split()[:4])}"
            media_url = auto_download_for_graphic(project.id, query)
            graphics.append(_split_screen(
                query,
                f"Comparative language detected ('{COMPARATIVE_RE.search(text).group(0)}') — split screen shows contrast.",
                s, e, media_url,
            ))
            continue

        # ── Topic keyword → contextual_broll ─────────────────────────────
        for keyword, query, reasoning_label, track, dur in TOPIC_RULES:
            if keyword in lowered:
                media_url = auto_download_for_graphic(project.id, query)
                g = _broll(query, f"Topic '{keyword}' detected — B-roll illustrates the concept.", s, e, media_url)
                graphics.append(g)
                break

    # ── Fallback article if none was created ─────────────────────────────
    if not article_added and captions:
        anchor = captions[min(1, len(captions) - 1)]
        graphics.append(_article(anchor.start, anchor.end + 4.0, "Clinical Evidence Snapshot"))

    # ── End card ─────────────────────────────────────────────────────────
    graphics.append(_endcard(project.duration_seconds))

    # ── Point 4: Resolve collisions ───────────────────────────────────────
    graphics = _resolve_collisions(graphics)

    return graphics


# ── Main entry point ──────────────────────────────────────────────────────────

def run_auto_production(project: ProjectState) -> ProjectState:
    # ── Point 1: Transcribe with Whisper if no captions exist ─────────────
    ts = _ts()
    if not project.captions:
        video_path = Path(project.source_media_path) if project.source_media_path else None
        if video_path and video_path.exists():
            try:
                from .whisper_transcribe import transcribe as whisper_transcribe
                project.captions = whisper_transcribe(video_path)
                append_activity(project.id, [{
                    "ts": ts, "event": "transcribe_done",
                    "caption_count": len(project.captions),
                    "reason": f"Auto Produce ran Whisper on {video_path.name} — {len(project.captions)} segments.",
                }])
            except Exception as exc:
                project.captions = synthetic_transcript(project.duration_seconds)
                append_activity(project.id, [{
                    "ts": ts, "event": "transcribe_fallback",
                    "reason": f"Whisper failed during Auto Produce ({exc}). Used synthetic transcript.",
                }])
        else:
            project.captions = synthetic_transcript(project.duration_seconds)
            append_activity(project.id, [{
                "ts": ts, "event": "transcribe_synthetic",
                "reason": "No source video found during Auto Produce. Used synthetic transcript.",
            }])

    # ── Generate graphics (points 2, 3, 4) ───────────────────────────────
    project.graphics = generate_graphics(project)

    log_entries = [
        {
            "ts": ts, "event": "graphic_placed",
            "graphic_id": g.id, "template_id": g.template_id,
            "title": g.title, "track": g.track,
            "start": g.start, "end": g.end,
            "reason": g.parameters.get("visual_reasoning", "Generated by semantic trigger engine."),
            "search_query": g.parameters.get("search_query", ""),
        }
        for g in project.graphics
    ]

    append_activity(project.id, [
        {"ts": ts, "event": "auto_produce_start",
         "caption_count": len(project.captions), "reason": "Auto-produce triggered by user."},
        *log_entries,
        {"ts": ts, "event": "auto_produce_done",
         "graphic_count": len(project.graphics),
         "reason": f"Placed {len(project.graphics)} graphics across V3/V4/V5 with collision resolution."},
    ])

    write_json(ensure_project_dirs(project.id) / "thumbnails" / "visual_reasoning_log.json", log_entries)
    return project

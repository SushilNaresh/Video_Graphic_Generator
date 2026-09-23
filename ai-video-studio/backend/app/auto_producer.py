from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import CaptionItem, MotionGraphicItem, ProjectState, TrackId, WordTiming
from .storage import append_activity, ensure_project_dirs, write_json

BROLL_SECONDS = 1.0

# ── Regex patterns (Pass 3 — Extraction) ─────────────────────────────────────

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


# ── Pass 3: Extraction ───────────────────────────────────────────────────────
# All regex/NER extraction lives here. generate_graphics() must not do extraction.

@dataclass
class CaptionAnnotation:
    caption: CaptionItem
    measurements: list[str] = field(default_factory=list)   # matched strings
    stats: list[tuple[str, str]] = field(default_factory=list)  # (value, unit)
    citations: list[str] = field(default_factory=list)      # matched phrases
    jargon: list[str] = field(default_factory=list)         # matched terms
    comparatives: list[str] = field(default_factory=list)   # matched phrases
    topic_keyword: Optional[tuple[str, str]] = None         # (keyword, search_query)

    @property
    def has_any(self) -> bool:
        return bool(self.measurements or self.stats or self.citations
                    or self.jargon or self.comparatives or self.topic_keyword)


def extract_annotations(captions: list[CaptionItem], project_id: str = "") -> list[CaptionAnnotation]:
    """Pass 3 — Entity Extraction / Claim Extraction.
    Runs all regexes over every caption and returns structured annotations.
    No graphic decisions are made here.
    """
    results: list[CaptionAnnotation] = []
    activity_entries: list[dict] = []
    ts = datetime.utcnow().isoformat() + "Z"

    for caption in captions:
        text = caption.text
        lowered = text.lower()
        ann = CaptionAnnotation(caption=caption)

        ann.measurements = [m.group(0) for m in MEASUREMENT_RE.finditer(text)]

        stat_m = STAT_RE.search(text)
        if stat_m and not ann.measurements:
            ann.stats = [(stat_m.group(1), stat_m.group(2))]

        cite_m = CITATION_RE.search(text)
        if cite_m:
            ann.citations = [cite_m.group(0)]

        jargon_m = JARGON_RE.search(text)
        if jargon_m:
            ann.jargon = [jargon_m.group(0)]

        comp_m = COMPARATIVE_RE.search(text)
        if comp_m:
            ann.comparatives = [comp_m.group(0)]

        for keyword, query, *_ in TOPIC_RULES:
            if keyword in lowered:
                ann.topic_keyword = (keyword, query)
                break

        results.append(ann)

        if ann.has_any:
            found: list[str] = []
            if ann.measurements:
                found.append(f"measurement: {', '.join(ann.measurements)}")
            if ann.stats:
                found.append(f"stat: {''.join(v+u for v,u in ann.stats)}")
            if ann.citations:
                found.append(f"citation: {ann.citations[0]}")
            if ann.jargon:
                found.append(f"jargon: {ann.jargon[0]}")
            if ann.comparatives:
                found.append(f"comparative: {ann.comparatives[0]}")
            if ann.topic_keyword:
                found.append(f"topic keyword: {ann.topic_keyword[0]}")

            summary = " | ".join(found)
            print(f"[PASS3] t={caption.start:.2f}s {summary} | '{text[:60]}'")

            activity_entries.append({
                "ts": ts,
                "event": "pass3_extraction",
                "start": caption.start,
                "end": caption.end,
                "caption_text": text,
                "matched_text": summary,
                "trigger_rule": "pass3",
                "reason": (
                    f"Pass 3 extracted from caption at {caption.start:.2f}s: {summary}. "
                    f"No graphic decision yet — this is pure extraction."
                ),
            })

    if project_id and activity_entries:
        append_activity(project_id, [
            {
                "ts": ts, "event": "pass3_start",
                "caption_count": len(captions),
                "reason": f"Pass 3 (Extraction) scanning {len(captions)} captions for measurements, stats, citations, jargon, comparatives, topic keywords.",
            },
            *activity_entries,
            {
                "ts": ts, "event": "pass3_done",
                "caption_count": len(captions),
                "reason": (
                    f"Pass 3 complete. {len(activity_entries)}/{len(captions)} captions had extractable signals. "
                    f"Citations found: {sum(1 for a in results if a.citations)}. "
                    f"Jargon: {sum(1 for a in results if a.jargon)}. "
                    f"Stats: {sum(1 for a in results if a.stats)}. "
                    f"Topic keywords: {sum(1 for a in results if a.topic_keyword)}."
                ),
            },
        ])

    return results


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
           media_url: str | None = None, matched_text: str = "",
           caption_text: str = "") -> MotionGraphicItem:
    s, e = clamp_broll(start, end)
    params: dict = {
        "search_query": query, "visual_reasoning": reasoning,
        "trigger_rule": "topic_keyword", "matched_text": matched_text,
        "caption_text": caption_text,
    }
    if media_url:
        params["media_url"] = media_url
    return MotionGraphicItem(
        id=f"gfx_{uuid.uuid4().hex[:8]}", start=s, end=e,
        template_id="contextual_broll", title=f"B-roll: {query.split()[0].title()}",
        parameters=params, track="V3",
    )


def _split_screen(query: str, reasoning: str, start: float, end: float,
                  media_url: str | None = None, matched_text: str = "",
                  caption_text: str = "") -> MotionGraphicItem:
    s, e = clamp_broll(start, end)
    params: dict = {
        "search_query": query, "visual_reasoning": reasoning,
        "trigger_rule": "comparative", "matched_text": matched_text,
        "caption_text": caption_text,
    }
    if media_url:
        params["media_url"] = media_url
    return MotionGraphicItem(
        id=f"split_{uuid.uuid4().hex[:8]}", start=s, end=e,
        template_id="split_screen_vertical", title=f"Split: {query.split()[0].title()}",
        parameters=params, track="V3",
    )


def _stat_counter(value: str, unit: str, start: float,
                  matched_text: str = "", caption_text: str = "") -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"stat_{uuid.uuid4().hex[:8]}", start=start, end=start + 3.0,
        template_id="stat_counter", title=f"Stat: {value}{unit}",
        parameters={
            "value": value, "unit": unit,
            "visual_reasoning": f"Speaker stated a statistic '{value}{unit}' — animated counter emphasises the number.",
            "trigger_rule": "stat_regex", "matched_text": matched_text, "caption_text": caption_text,
        },
        track="V5",
    )


def _dimension_callout(value: str, start: float,
                       matched_text: str = "", caption_text: str = "") -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"dim_{uuid.uuid4().hex[:8]}", start=start, end=start + 2.5,
        template_id="dimension_callout", title=f"Dimension: {value}",
        parameters={
            "value": value.upper(), "label": "Measured Statement",
            "visual_reasoning": f"Speaker stated a physical measurement '{value}' — HUD callout highlights the dimension.",
            "trigger_rule": "measurement_regex", "matched_text": matched_text, "caption_text": caption_text,
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
            "trigger_rule": "comparative", "matched_text": snippet, "caption_text": snippet,
        },
        track="V5",
    )


def _source_citation(source: str, start: float,
                     caption_text: str = "") -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"cite_{uuid.uuid4().hex[:8]}", start=start, end=start + 2.5,
        template_id="source_citation", title=f"Citation: {source[:30]}",
        parameters={
            "source": source,
            "visual_reasoning": f"Speaker cited a source or study ('{source}') — citation overlay adds credibility.",
            "trigger_rule": "citation_regex", "matched_text": source, "caption_text": caption_text,
        },
        track="V5",
    )


def _jargon_card(term: str, start: float, caption_text: str = "") -> MotionGraphicItem:
    return MotionGraphicItem(
        id=f"jargon_{uuid.uuid4().hex[:8]}", start=start, end=start + 3.5,
        template_id="jargon_translation", title=f"Jargon: {term}",
        parameters={
            "term": term,
            "visual_reasoning": f"Medical jargon '{term}' detected — translation card helps viewers understand the term.",
            "trigger_rule": "jargon_regex", "matched_text": term, "caption_text": caption_text,
        },
        track="V4",
    )


def _article(start: float, end: float, title: str, paragraph: str = "",
             highlight: str = "", matched_text: str = "",
             caption_text: str = "", trigger_rule: str = "citation_regex") -> MotionGraphicItem:
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
            "trigger_rule": trigger_rule, "matched_text": matched_text, "caption_text": caption_text,
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


# ── Pass 5 (partial): Graphic generation from annotations ───────────────────────

def generate_graphics(project: ProjectState) -> list[MotionGraphicItem]:
    from .stock_media import auto_download_for_graphic

    annotations = extract_annotations(project.captions, project_id=project.id)
    graphics: list[MotionGraphicItem] = []

    # Globally check if any citation exists across all captions
    # Fixes false-positive fallback article_reconstruction
    any_citation = any(ann.citations for ann in annotations)
    article_added = False

    for ann in annotations:
        caption = ann.caption
        text = caption.text
        s, e = caption.start, caption.end

        for m in ann.measurements:
            print(f"[TRIGGER] dimension_callout | match={m!r} | caption={text[:60]!r} | t={s:.2f}s")
            graphics.append(_dimension_callout(m, s, matched_text=m, caption_text=text))

        for value, unit in ann.stats:
            print(f"[TRIGGER] stat_counter | match={value+unit!r} | caption={text[:60]!r} | t={s:.2f}s")
            graphics.append(_stat_counter(value, unit, s, matched_text=value+unit, caption_text=text))

        if ann.citations and not article_added:
            cite = ann.citations[0]
            print(f"[TRIGGER] article_reconstruction | match={cite!r} | caption={text[:60]!r} | t={s:.2f}s")
            g = _article(s, e + 4.0, title=text[:60].rstrip(".,: ") + "…",
                         paragraph=text, highlight=text[:80],
                         matched_text=cite, caption_text=text, trigger_rule="citation_regex")
            graphics.append(g)
            article_added = True
            continue

        if ann.jargon:
            term = ann.jargon[0]
            print(f"[TRIGGER] jargon_translation | match={term!r} | caption={text[:60]!r} | t={s:.2f}s")
            graphics.append(_jargon_card(term, s, caption_text=text))
            continue

        if ann.comparatives:
            comp = ann.comparatives[0]
            print(f"[TRIGGER] split_screen_vertical | match={comp!r} | caption={text[:60]!r} | t={s:.2f}s")
            query = "comparison " + " ".join(text.split()[:4])
            media_url = auto_download_for_graphic(project.id, query)
            graphics.append(_split_screen(
                query,
                f"Comparative language detected ({comp!r}) — split screen shows contrast.",
                s, e, media_url, matched_text=comp, caption_text=text,
            ))
            continue

        if ann.topic_keyword:
            keyword, query = ann.topic_keyword
            print(f"[TRIGGER] contextual_broll | keyword={keyword!r} | query={query!r} | caption={text[:60]!r} | t={s:.2f}s")
            media_url = auto_download_for_graphic(project.id, query)
            graphics.append(_broll(
                query, f"Topic {keyword!r} detected — B-roll illustrates the concept.",
                s, e, media_url, matched_text=keyword, caption_text=text,
            ))

    # Fallback article only when NO citation exists anywhere in transcript
    if not article_added and not any_citation and project.captions:
        anchor = project.captions[min(1, len(project.captions) - 1)]
        print(f"[TRIGGER] article_reconstruction | fallback (no citation in transcript) | t={anchor.start:.2f}s")
        graphics.append(_article(
            anchor.start, anchor.end + 4.0, "Clinical Evidence Snapshot",
            caption_text=anchor.text, trigger_rule="fallback_no_citation",
            matched_text="(no citation found in transcript)",
        ))

    graphics.append(_endcard(project.duration_seconds))
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
            "trigger_rule": g.parameters.get("trigger_rule", ""),
            "matched_text": g.parameters.get("matched_text", ""),
            "caption_text": g.parameters.get("caption_text", ""),
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

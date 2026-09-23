# AI Video Studio Skill

Use this skill when editing the fresh AI Video Studio codebase generated from `STUDIO_FEATURE_MANUAL.md`.

## Core rules

- Preserve the manual's WYSIWYG intent: preview behavior should match export behavior.
- Keep the backend API schema compatible with `frontend/src/types.ts` and `backend/app/models.py`.
- Keep large video upload memory-safe: do not replace XHR streaming with `file.arrayBuffer()` or backend `await request.body()`.
- Keep default automated B-roll and stock cutaways clamped to `1.0` second unless a user manually extends them.
- Allow `article_reconstruction` and `digital_highlighter` to run longer than 1 second for readability.
- Keep project state saves atomic through `backend/app/storage.py`.
- Avoid adding mandatory external services; use stubs or graceful fallback when API keys are absent.

## Important files

- Backend API routes: `backend/app/main.py`
- Shared backend schema: `backend/app/models.py`
- Frontend API client: `frontend/src/api/client.ts`
- Main editor shell: `frontend/src/App.tsx`
- Live preview overlay: `frontend/src/components/CanvasOverlay.tsx`
- Timeline: `frontend/src/components/Timeline.tsx`
- Inspector: `frontend/src/components/Inspector.tsx`

## Validation checklist

1. `python3 -m py_compile backend/app/*.py`
2. `npm install` in `frontend` if dependencies are missing.
3. `npm run build` in `frontend`.
4. Start backend on `8002` and frontend on `5173`.
5. Upload a large video and confirm progress displays without browser memory spikes.

## Trigger engine logic (`auto_producer.py`)

Each caption is tested in priority order — first match wins (except measurements which stack):

| Priority | Regex / Rule | Template | Track | Duration |
|----------|-------------|----------|-------|----------|
| 1 | `MEASUREMENT_RE` — numbers with units (cm, mm, ft, %, stage N) | `dimension_callout` | V5 | 2.5s |
| 2 | `STAT_RE` — numbers with %, times, x, fold (no measurement match) | `stat_counter` | V5 | 3.0s |
| 3 | `CITATION_RE` — "according to", journal names, study types (first only) | `article_reconstruction` | V4 | ≥5.0s |
| 4 | `JARGON_RE` — medical terms (metastasis, carcinoma, fibrosis…) | `jargon_translation` | V4 | 3.5s |
| 5 | `COMPARATIVE_RE` — versus, compared to, higher/lower than… | `split_screen_vertical` | V3 | 1.0s |
| 6 | `TOPIC_RULES` — 23 keyword strings (aging, cancer, heart…) | `contextual_broll` | V3 | 1.0s |
| fallback | No match on any caption with citation | `article_reconstruction` | V4 | ≥5.0s |
| always | End of video | `medical_endcard` | V5 | 3.0s |

All trigger decisions are printed to backend stdout as `[TRIGGER] template | match='...' | caption='...' | t=Xs`.

## Skill notes

- Per-project notes are stored in `projects/{id}/skill_notes.json`.
- Every save re-writes `.agents/skills/ai-video-studio/SKILL.md` appending a `## Learned skill notes` section.
- Frontend: open Activity Log → expand any `graphic_placed` entry → click **Add note** → type improvement → **Save to skill**.
- Notes are keyed by `graphic_id`, `template_id`, and `trigger` so future iterations can refine regex patterns.

## 5-Pass Auto-Production Architecture

The auto-producer is structured as 5 sequential passes. Each pass has one input artifact and one output artifact. Never collapse passes — the dependency order is strict.

### Pass 1 — Signal Understanding
**Terms**: Multimodal Video Understanding, Temporal Grounding, Shot Boundary Detection
**Input**: video file + raw transcript
**Output**: `signal_map` — time-anchored segments with `{start, end, words[], shot_boundary, scene_label}`
**Status**: Whisper (Temporal Grounding) ✓ done. Shot boundary + scene label = stubs.
**Rule**: This is the only pass that reads the video file directly.

### Pass 2 — Segmentation
**Terms**: Semantic Segmentation, Narrative/Discourse Segmentation
**Input**: `signal_map`
**Output**: `segments[]` — each with `{start, end, captions[], semantic_topic, narrative_role: hook|setup|explanation|example|contrast|payoff|cta}`
**Status**: Not implemented. Currently captions are used raw (each caption = one unit).
**Rule**: Never segment while still reading signal. Pass 1 must be complete first.

### Pass 3 — Extraction
**Terms**: Entity Extraction/NER, Claim Extraction
**Input**: `segments[]`
**Output**: `annotations[]` — each segment gains `entities: [{text, type}]` and `claims: [{text, confidence}]`
**Status**: Regexes exist (`STAT_RE`, `MEASUREMENT_RE`, `CITATION_RE`, `JARGON_RE`) but run inside the trigger loop. Must be moved to a dedicated `extract_annotations()` function.
**Rule**: All regex/NER extraction belongs here only. The trigger loop must not do extraction.

### Pass 4 — Decision
**Terms**: Visual Opportunity Detection, Visual Intent Classification, Saliency/Importance Scoring, Visual Redundancy Detection, Editorial Density/Pacing Control
**Input**: `annotations[]`
**Output**: `opportunities[]` — `{segment_ref, intent: illustrate|prove|define|contrast|emphasise, saliency: float, composition: overlay|fullscreen|lower_third|split_screen, approved: bool}`
**Status**: Not implemented. Keywords fire immediately without scoring, redundancy check, or pacing.
**Rule**: Max 1 graphic per 8 seconds of video (pacing cap). Redundancy check must run before approval.

### Pass 5 — Execution
**Terms**: Editorial Planning, Asset Planning, Query Expansion, Visual Grounding, Temporal Placement, Composition Planning
**Input**: `opportunities[]`
**Output**: `project.graphics[]` — final `MotionGraphicItem` list
**Status**: Factory functions (`_broll`, `_article`, etc.) exist but are called directly from trigger loop, bypassing Passes 2–4.
**Rule**: This is the only pass that calls external APIs (Pexels, Pixabay, Wikimedia). Query expansion must derive from semantic meaning, not raw caption words.

### Implementation order
1. ✅ Pass 3 extraction — move regexes to `extract_annotations()` (no new dependencies)
2. Pass 4 decision — add `score_opportunities()` with saliency ranking + 8s density cap
3. Pass 2 segmentation — group captions by topic coherence (TF-IDF cosine, no ML needed)
4. Pass 1 shot detection + Pass 5 visual grounding — stub until Twelve Labs API is wired

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

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

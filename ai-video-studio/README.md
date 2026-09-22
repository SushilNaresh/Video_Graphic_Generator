# AI Video Studio

Fresh full-stack scaffold generated from `../STUDIO_FEATURE_MANUAL.md`.

## What is included

- React 18 + TypeScript + Vite frontend editor.
- FastAPI backend on port `8002`.
- Streaming video upload using native browser `XMLHttpRequest` and backend chunked writes.
- Project JSON persistence under `backend/projects` by default.
- Multi-track timeline model: `V5`, `V4`, `V3`, `V2`, `V1`, `A1`, `A2`.
- Subtitle controls, graphics inspector, local stock placeholders, Twelve Labs key storage stub, and render/download endpoints.
- Burn-in render scaffold that uses `ffmpeg` with `h264_videotoolbox` when available and falls back to copying the source video.

## Run backend

```bash
cd /Users/kunjan/Documents/Sushil/OONEX/Video_Graphic_Generator/ai-video-studio/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Backend health check:

```bash
curl http://localhost:8002/api/health
```

## Run frontend

```bash
cd /Users/kunjan/Documents/Sushil/OONEX/Video_Graphic_Generator/ai-video-studio/frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

Open `http://localhost:5173`.

## Key API routes

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{id}`
- `DELETE /api/projects/{id}`
- `POST /api/projects/{id}/autosave`
- `POST /api/projects/{id}/transcribe`
- `POST /api/projects/{id}/auto-produce`
- `POST /api/media/{id}/upload`
- `GET /api/media/{id}/source-video`
- `GET /api/media/stock/search`
- `POST /api/media/stock/download`
- `GET /api/media/twelve-labs/credits`
- `POST /api/media/twelve-labs/set-key`
- `POST /api/media/{id}/twelve-labs/analyze`
- `POST /api/media/{id}/render-burnin`
- `GET /api/media/{id}/burnin-progress`
- `GET /api/media/{id}/download-mp4`

## Next implementation targets

1. Replace synthetic transcript generation with Whisper word timestamps.
2. Replace local Twelve Labs stub with real Marengo/Pegasus API calls.
3. Replace placeholder stock search with Pexels, Pixabay, and Wikimedia clients.
4. Expand renderer from copy/transcode scaffold to full Pillow/PyAV compositing.
5. Add drag-trim handles with persisted autosave on the timeline.

## Step-by-step: transcribe and graphic overlay

1. Start backend and frontend, then open `http://localhost:5173`.
2. Click `+` in Projects or use the auto-created project.
3. Drop an MP4/MOV into the upload box and wait for `Upload complete`.
4. Click `Transcribe`; the scaffold creates word-timed captions and places them on `V2`.
5. Open the `Subtitles` inspector to adjust font, size, colors, uppercase, active-word highlight, keyword highlight, and shadow.
6. Click `Auto Produce`; the backend creates graphic overlays from captions, writes `thumbnails/visual_reasoning_log.json`, clamps B-roll to 1 second, and places overlays on `V3/V4/V5`.
7. Scrub the timeline and click any graphic block to select it.
8. Open the `Graphics` inspector, adjust start/end/scale, search local stock placeholders, and attach a visual to the selected graphic.
9. Use `Analyze` when you want the Twelve Labs-compatible flow; currently it runs the local semantic generator until the real API client is wired.
10. Click `Render MP4`, wait for render progress, then download the burned output.

## Delete projects

Use the red trash button beside any project in the left drawer. Deleting removes that project's JSON state, uploaded media, downloaded assets, proxies, thumbnails, and renders from `backend/projects/{project_id}`.

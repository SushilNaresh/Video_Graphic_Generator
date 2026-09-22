import { CheckCircle2, Download, Film, Loader2 } from 'lucide-react';
import type { ProjectState, RenderProgress } from '../types';

export function ExportPanel({
  project,
  renderProgress,
  onRender,
  downloadUrl
}: {
  project: ProjectState | null;
  renderProgress: RenderProgress | null;
  onRender: () => void;
  downloadUrl: string | null;
}) {
  const progress = Math.round((renderProgress?.progress ?? 0) * 100);
  const isRunning = renderProgress?.status === 'running' || renderProgress?.status === 'queued';
  const isReady = renderProgress?.status === 'ready';

  return (
    <div className="stack">
      <h3>Burn-In Render</h3>
      <p className="muted">Hardware-accelerated MP4 with all graphics, subtitles, and B-roll composited.</p>

      <button className="primary-btn wide" onClick={onRender} disabled={!project?.source_media_path || isRunning}>
        {isRunning ? <Loader2 size={16} className="spin" /> : <Film size={16} />}
        {isRunning ? `Rendering ${progress}%…` : 'Render MP4'}
      </button>

      {renderProgress && !isReady && (
        <div className="render-progress-wrap">
          <progress value={progress} max={100} />
          <span className="render-progress-label">{renderProgress.message}</span>
        </div>
      )}

      {isReady && downloadUrl && (
        <div className="render-ready-card">
          <CheckCircle2 size={18} className="render-ready-icon" />
          <span>Render complete</span>
          <a className="primary-btn" href={downloadUrl} download>
            <Download size={15} /> Download MP4
          </a>
        </div>
      )}
    </div>
  );
}

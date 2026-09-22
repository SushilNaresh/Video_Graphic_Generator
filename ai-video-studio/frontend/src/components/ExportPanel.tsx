import { Download, Film } from 'lucide-react';
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
  return (
    <section className="panel export-panel">
      <p className="eyebrow">Export</p>
      <h3>Burn-In Render</h3>
      <p>Hardware-accelerated MP4 output when FFmpeg VideoToolbox is available.</p>
      <button className="primary-btn wide" onClick={onRender} disabled={!project?.source_media_path}><Film size={16} /> Render MP4</button>
      {renderProgress && <progress value={progress} max={100} />}
      {downloadUrl && renderProgress?.status === 'ready' && <a className="secondary-btn wide" href={downloadUrl}><Download size={16} /> Download</a>}
    </section>
  );
}

import { useEffect, useRef, useState } from 'react';
import { Activity, AlertCircle, CheckCircle2, ChevronDown, ChevronUp, Download, Film, FileVideo, Plus, RefreshCw, Save, Trash2, Upload, Wand2, Search, Sparkles } from 'lucide-react';

export interface ActivityEntry {
  ts: string;
  event: string;
  reason: string;
  graphic_id?: string;
  template_id?: string;
  title?: string;
  track?: string;
  start?: number;
  end?: number;
  caption_count?: number;
  graphic_count?: number;
  search_query?: string;
}

const EVENT_META: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  // Project
  project_created:            { icon: <Plus size={13} />,        color: '#38bdf8', label: 'Project created' },
  project_autosaved:          { icon: <Save size={13} />,        color: '#64748b', label: 'Autosaved' },
  // Upload
  upload_start:               { icon: <Upload size={13} />,      color: '#fb923c', label: 'Upload started' },
  upload_done:                { icon: <Upload size={13} />,      color: '#4ade80', label: 'Upload complete' },
  asset_uploaded:             { icon: <Upload size={13} />,      color: '#38bdf8', label: 'Asset uploaded' },
  // Transcription
  transcribe_start:           { icon: <FileVideo size={13} />,   color: '#94a3b8', label: 'Transcribe started' },
  transcribe_done:            { icon: <FileVideo size={13} />,   color: '#22d3ee', label: 'Transcribed' },
  transcribe_fallback:        { icon: <AlertCircle size={13} />, color: '#f59e0b', label: 'Transcribe fallback' },
  transcribe_synthetic:       { icon: <AlertCircle size={13} />, color: '#64748b', label: 'Synthetic transcript' },
  // Auto Produce
  auto_produce_requested:     { icon: <Wand2 size={13} />,       color: '#c084fc', label: 'Auto Produce requested' },
  auto_produce_start:         { icon: <Wand2 size={13} />,       color: '#a78bfa', label: 'Auto Produce started' },
  auto_produce_done:          { icon: <Wand2 size={13} />,       color: '#a78bfa', label: 'Auto Produce done' },
  // Graphics
  graphic_placed:             { icon: <Activity size={13} />,    color: '#34d399', label: 'Graphic placed' },
  graphic_added_manual:       { icon: <Plus size={13} />,        color: '#38bdf8', label: 'Graphic added' },
  graphic_deleted:            { icon: <Trash2 size={13} />,      color: '#f87171', label: 'Graphic deleted' },
  // Stock
  stock_search:               { icon: <Search size={13} />,      color: '#94a3b8', label: 'Stock search' },
  stock_downloaded:           { icon: <Download size={13} />,    color: '#34d399', label: 'Stock downloaded' },
  stock_auto_downloaded:      { icon: <Download size={13} />,    color: '#34d399', label: 'Auto-downloaded' },
  stock_auto_download_skip:   { icon: <AlertCircle size={13} />, color: '#64748b', label: 'Download skipped' },
  stock_auto_download_failed: { icon: <AlertCircle size={13} />, color: '#f59e0b', label: 'Download failed' },
  // Twelve Labs
  analyze_start:              { icon: <Sparkles size={13} />,    color: '#c084fc', label: 'Analyze started' },
  analyze_done:               { icon: <Sparkles size={13} />,    color: '#a78bfa', label: 'Analyze done' },
  twelve_labs_analyze_start:  { icon: <Sparkles size={13} />,    color: '#c084fc', label: '12Labs started' },
  twelve_labs_analyze_done:   { icon: <Sparkles size={13} />,    color: '#a78bfa', label: '12Labs done' },
  // Render
  render_start:               { icon: <Film size={13} />,        color: '#fb923c', label: 'Render started' },
  render_running:             { icon: <RefreshCw size={13} />,   color: '#fb923c', label: 'Render running' },
  render_encoder_fallback:    { icon: <AlertCircle size={13} />, color: '#f59e0b', label: 'Encoder fallback' },
  render_done:                { icon: <CheckCircle2 size={13} />,color: '#4ade80', label: 'Render done' },
  render_failed:              { icon: <AlertCircle size={13} />, color: '#f87171', label: 'Render failed' },
  render_downloaded:          { icon: <Download size={13} />,    color: '#38bdf8', label: 'MP4 downloaded' },
};

function fallbackMeta(event: string) {
  return { icon: <Activity size={13} />, color: '#94a3b8', label: event.replace(/_/g, ' ') };
}

function formatTime(ts: string) {
  try { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
  catch { return ts; }
}

export function ActivityLog({
  entries,
  onJumpTo,
}: {
  entries: ActivityEntry[];
  onJumpTo?: (time: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length, open]);

  return (
    <div className={`activity-log-bar ${open ? 'open' : ''}`}>
      <button className="activity-log-toggle" onClick={() => setOpen((v) => !v)}>
        <Activity size={14} />
        <span>Activity Log</span>
        <span className="activity-log-count">{entries.length}</span>
        {open ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>

      {open && (
        <div className="activity-log-body">
          {entries.length === 0 && (
            <p className="activity-log-empty">No activity yet. Transcribe or Auto Produce to get started.</p>
          )}
          {entries.map((entry, idx) => {
            const meta = EVENT_META[entry.event] ?? fallbackMeta(entry.event);
            return (
              <div key={idx} className="activity-entry">
                <span className="activity-icon" style={{ color: meta.color }}>{meta.icon}</span>
                <div className="activity-body">
                  <div className="activity-header">
                    <span className="activity-label" style={{ color: meta.color }}>{meta.label}</span>
                    {entry.template_id && <span className="activity-tag">{entry.template_id}</span>}
                    {entry.track && <span className="activity-tag track-tag">{entry.track}</span>}
                    {entry.start !== undefined && onJumpTo && (
                      <button className="activity-jump" onClick={() => onJumpTo(entry.start!)}>
                        {entry.start.toFixed(2)}s
                      </button>
                    )}
                    <span className="activity-ts">{formatTime(entry.ts)}</span>
                  </div>
                  <p className="activity-reason">{entry.reason}</p>
                  {entry.search_query && (
                    <p className="activity-meta">Search query: <em>{entry.search_query}</em></p>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

import { useEffect, useRef, useState } from 'react';
import { Activity, AlertCircle, BookOpen, CheckCircle2, ChevronDown, ChevronUp, Download, Film, FileVideo, Plus, RefreshCw, Save, Trash2, Upload, Wand2, Search, Sparkles } from 'lucide-react';
import type { SkillNote } from '../types';

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
  trigger_rule?: string;
  matched_text?: string;
  caption_text?: string;
}

const EVENT_META: Record<string, { icon: unknown; color: string; label: string }> = {
  project_created:            { icon: <Plus size={13} />,        color: '#38bdf8', label: 'Project created' },
  project_autosaved:          { icon: <Save size={13} />,        color: '#64748b', label: 'Autosaved' },
  upload_start:               { icon: <Upload size={13} />,      color: '#fb923c', label: 'Upload started' },
  upload_done:                { icon: <Upload size={13} />,      color: '#4ade80', label: 'Upload complete' },
  asset_uploaded:             { icon: <Upload size={13} />,      color: '#38bdf8', label: 'Asset uploaded' },
  transcribe_start:           { icon: <FileVideo size={13} />,   color: '#94a3b8', label: 'Transcribe started' },
  transcribe_done:            { icon: <FileVideo size={13} />,   color: '#22d3ee', label: 'Transcribed' },
  transcribe_fallback:        { icon: <AlertCircle size={13} />, color: '#f59e0b', label: 'Transcribe fallback' },
  transcribe_synthetic:       { icon: <AlertCircle size={13} />, color: '#64748b', label: 'Synthetic transcript' },
  auto_produce_requested:     { icon: <Wand2 size={13} />,       color: '#c084fc', label: 'Auto Produce requested' },
  auto_produce_start:         { icon: <Wand2 size={13} />,       color: '#a78bfa', label: 'Auto Produce started' },
  auto_produce_done:          { icon: <Wand2 size={13} />,       color: '#a78bfa', label: 'Auto Produce done' },
  pass3_start:                { icon: <Search size={13} />,      color: '#38bdf8', label: 'Pass 3: Extraction started' },
  pass3_extraction:           { icon: <Search size={13} />,      color: '#22d3ee', label: 'Pass 3: Signal found' },
  pass3_done:                 { icon: <CheckCircle2 size={13} />,color: '#38bdf8', label: 'Pass 3: Extraction done' },
  graphic_placed:             { icon: <Activity size={13} />,    color: '#34d399', label: 'Graphic placed' },
  graphic_added_manual:       { icon: <Plus size={13} />,        color: '#38bdf8', label: 'Graphic added' },
  graphic_deleted:            { icon: <Trash2 size={13} />,      color: '#f87171', label: 'Graphic deleted' },
  stock_search:               { icon: <Search size={13} />,      color: '#94a3b8', label: 'Stock search' },
  stock_downloaded:           { icon: <Download size={13} />,    color: '#34d399', label: 'Stock downloaded' },
  stock_auto_downloaded:      { icon: <Download size={13} />,    color: '#34d399', label: 'Auto-downloaded' },
  stock_auto_download_skip:   { icon: <AlertCircle size={13} />, color: '#64748b', label: 'Download skipped' },
  stock_auto_download_failed: { icon: <AlertCircle size={13} />, color: '#f59e0b', label: 'Download failed' },
  analyze_start:              { icon: <Sparkles size={13} />,    color: '#c084fc', label: 'Analyze started' },
  analyze_done:               { icon: <Sparkles size={13} />,    color: '#a78bfa', label: 'Analyze done' },
  twelve_labs_analyze_start:  { icon: <Sparkles size={13} />,    color: '#c084fc', label: '12Labs started' },
  twelve_labs_analyze_done:   { icon: <Sparkles size={13} />,    color: '#a78bfa', label: '12Labs done' },
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

function NoteForm({ graphicId, templateId, trigger, onSave }: {
  graphicId: string;
  templateId: string;
  trigger: string;
  onSave: (note: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!text.trim()) return;
    setSaving(true);
    await onSave(text.trim());
    setText('');
    setOpen(false);
    setSaving(false);
  }

  if (!open) {
    return (
      <button className="activity-note-btn" onClick={() => setOpen(true)}>
        <BookOpen size={11} /> Add note
      </button>
    );
  }

  return (
    <div className="activity-note-form">
      <textarea
        className="activity-note-textarea"
        placeholder={`Improve trigger logic for '${templateId}'…`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={2}
        autoFocus
      />
      <div className="activity-note-actions">
        <button className="activity-note-save" onClick={submit} disabled={saving || !text.trim()}>
          {saving ? 'Saving…' : 'Save to skill'}
        </button>
        <button className="activity-note-cancel" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  );
}

export function ActivityLog({
  entries,
  skillNotes,
  onJumpTo,
  onAddNote,
}: {
  entries: ActivityEntry[];
  skillNotes: SkillNote[];
  onJumpTo?: (time: number) => void;
  onAddNote?: (graphicId: string, templateId: string, trigger: string, note: string) => Promise<void>;
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
        {skillNotes.length > 0 && (
          <span className="activity-log-count" style={{ background: '#a78bfa22', color: '#a78bfa' }}>
            <BookOpen size={11} /> {skillNotes.length} notes
          </span>
        )}
        {open ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>

      {open && (
        <div className="activity-log-body">
          {entries.length === 0 && (
            <p className="activity-log-empty">No activity yet. Transcribe or Auto Produce to get started.</p>
          )}
          {entries.map((entry, idx) => {
            const meta = EVENT_META[entry.event] ?? fallbackMeta(entry.event);
            const isGraphicPlaced = entry.event === 'graphic_placed';
            const entryNotes = isGraphicPlaced && entry.graphic_id
              ? skillNotes.filter((n) => n.graphic_id === entry.graphic_id)
              : [];

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
                  {isGraphicPlaced && (entry.caption_text || entry.matched_text) && (
                    <div className="activity-trigger-block">
                      {entry.trigger_rule && (
                        <span className="activity-trigger-rule">rule: {entry.trigger_rule.replace(/_/g, ' ')}</span>
                      )}
                      {entry.matched_text && (
                        <p className="activity-trigger-match">matched: <strong>&ldquo;{entry.matched_text}&rdquo;</strong></p>
                      )}
                      {entry.caption_text && (
                        <p className="activity-trigger-caption">&ldquo;{entry.caption_text}&rdquo;</p>
                      )}
                    </div>
                  )}
                  {entryNotes.map((n, ni) => (
                    <div key={ni} className="activity-skill-note">
                      <BookOpen size={11} />
                      <span><strong>Skill note:</strong> {n.note}</span>
                      <span className="activity-ts">{n.ts.slice(0, 10)}</span>
                    </div>
                  ))}
                  {isGraphicPlaced && onAddNote && entry.graphic_id && (
                    <NoteForm
                      graphicId={entry.graphic_id}
                      templateId={entry.template_id ?? ''}
                      trigger={entry.search_query ?? entry.template_id ?? ''}
                      onSave={(note) => onAddNote(
                        entry.graphic_id!,
                        entry.template_id ?? '',
                        entry.search_query ?? entry.template_id ?? '',
                        note,
                      )}
                    />
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

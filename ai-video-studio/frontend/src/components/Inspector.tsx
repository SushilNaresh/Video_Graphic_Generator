import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import type { CaptionStyle, GraphicTemplateId, MotionGraphicItem, ProjectState, RenderProgress, StockMediaItem, TrackId } from '../types';
import { ExportPanel } from './ExportPanel';

const DEFAULT_STYLE: CaptionStyle = {
  font_family: 'Inter', font_size: 42, font_weight: '800', uppercase: true,
  text_color: '#FFFFFF', active_word_color: '#38BDF8', past_word_color: '#B0B0B0',
  has_highlight: true, has_keyword_emphasis: true, has_shadow: true
};

const TEMPLATES: { id: GraphicTemplateId; label: string; track: TrackId; defaultDuration: number }[] = [
  { id: 'contextual_broll',       label: 'B-Roll Cutaway',         track: 'V3', defaultDuration: 1.0 },
  { id: 'split_screen_vertical',  label: '50/50 Split Screen',     track: 'V3', defaultDuration: 1.0 },
  { id: 'article_reconstruction', label: 'Article / Report',       track: 'V4', defaultDuration: 6.0 },
  { id: 'digital_highlighter',    label: 'Journal Highlighter',    track: 'V4', defaultDuration: 5.0 },
  { id: 'dimension_callout',      label: 'Dimension Callout',      track: 'V5', defaultDuration: 2.5 },
  { id: 'stat_counter',           label: 'Stat Counter',           track: 'V5', defaultDuration: 3.0 },
  { id: 'kinetic_typography',     label: 'Kinetic Typography',     track: 'V5', defaultDuration: 2.0 },
  { id: 'medical_endcard',        label: 'Medical End Card',       track: 'V5', defaultDuration: 3.0 },
  { id: 'source_citation',        label: 'Source Citation',        track: 'V5', defaultDuration: 2.5 },
  { id: 'thematic_canvas',        label: 'Thematic Dark Canvas',   track: 'V3', defaultDuration: 4.0 },
  { id: 'jargon_translation',     label: 'Jargon Translation',     track: 'V4', defaultDuration: 3.5 },
];

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

export function Inspector({
  project, selectedGraphic, currentTime,
  onProjectChange, onGraphicChange, onGraphicDelete, onGraphicAdd, onStatus,
  renderProgress, onRender, downloadUrl
}: {
  project: ProjectState | null;
  selectedGraphic: MotionGraphicItem | null;
  currentTime: number;
  onProjectChange: (p: ProjectState) => void;
  onGraphicChange: (g: MotionGraphicItem) => void;
  onGraphicDelete: (id: string) => void;
  onGraphicAdd: (payload: object) => void;
  onStatus: (s: string) => void;
  renderProgress: RenderProgress | null;
  onRender: () => void;
  downloadUrl: string | null;
}) {
  const [tab, setTab] = useState<'subtitles' | 'graphics' | 'ai' | 'export'>('subtitles');
  const [stockQuery, setStockQuery] = useState('medical research report');
  const [stockResults, setStockResults] = useState<StockMediaItem[]>([]);
  const [credits, setCredits] = useState('Checking credits...');
  const [showAddPanel, setShowAddPanel] = useState(false);
  const [newTemplate, setNewTemplate] = useState<GraphicTemplateId>('contextual_broll');
  const [newTitle, setNewTitle] = useState('');

  useEffect(() => {
    api.getTwelveLabsCredits()
      .then((r) => setCredits(r.configured ? `${r.remaining_minutes.toFixed(0)} min remaining` : 'No key configured'))
      .catch(() => setCredits('Credits unavailable'));
  }, []);

  if (!project) {
    return <aside className="inspector panel"><h3>Inspector</h3><p>Load a project to edit settings.</p></aside>;
  }

  const style = project.settings?.subtitle_style ?? DEFAULT_STYLE;

  function updateStyle(patch: Partial<CaptionStyle>) {
    onProjectChange({
      ...project!,
      settings: { ...project!.settings, subtitle_style: { ...style, ...patch } },
      captions: project!.captions.map((c) => ({ ...c, style: { ...c.style, ...patch } }))
    });
  }

  async function searchStock() {
    onStatus('Searching stock media...');
    const res = await api.searchStock(stockQuery);
    setStockResults(res.results);
    onStatus(`Found ${res.results.length} results`);
  }

  async function attachStock(item: StockMediaItem) {
    if (!selectedGraphic) return;
    onStatus('Attaching stock media...');
    const res = await api.downloadStock(project.id, item);
    onGraphicChange({ ...selectedGraphic, parameters: { ...selectedGraphic.parameters, media_url: res.media_url }, title: item.title });
    onStatus('Stock media attached');
  }

  function handleAddGraphic() {
    const tmpl = TEMPLATES.find((t) => t.id === newTemplate)!;
    onGraphicAdd({
      template_id: newTemplate,
      title: newTitle || tmpl.label,
      start: parseFloat(currentTime.toFixed(2)),
      end: parseFloat((currentTime + tmpl.defaultDuration).toFixed(2)),
      track: tmpl.track,
    });
    setShowAddPanel(false);
    setNewTitle('');
  }

  return (
    <aside className="inspector panel">
      <div className="tab-row">
        {(['subtitles', 'graphics', 'ai', 'export'] as const).map((t) => (
          <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {tab === 'subtitles' && (
        <div className="stack">
          <h3>Subtitles</h3>
          <Field label="Font family">
            <select value={style.font_family} onChange={(e) => updateStyle({ font_family: e.target.value })}>
              <option>Inter</option><option>Playfair Display</option><option>JetBrains Mono</option><option>Montserrat</option>
            </select>
          </Field>
          <Field label={`Font size ${style.font_size}px`}>
            <input type="range" min="16" max="64" value={style.font_size} onChange={(e) => updateStyle({ font_size: Number(e.target.value) })} />
          </Field>
          <Field label="Weight">
            <select value={style.font_weight} onChange={(e) => updateStyle({ font_weight: e.target.value })}>
              <option value="400">Normal</option><option value="600">Medium</option><option value="800">Bold</option><option value="900">Extra Bold</option>
            </select>
          </Field>
          <Field label="Text color"><input type="color" value={style.text_color} onChange={(e) => updateStyle({ text_color: e.target.value })} /></Field>
          <Field label="Active word"><input type="color" value={style.active_word_color} onChange={(e) => updateStyle({ active_word_color: e.target.value })} /></Field>
          <Field label="Past word"><input type="color" value={style.past_word_color} onChange={(e) => updateStyle({ past_word_color: e.target.value })} /></Field>
          <label className="toggle"><input type="checkbox" checked={style.uppercase} onChange={(e) => updateStyle({ uppercase: e.target.checked })} /> Uppercase</label>
          <label className="toggle"><input type="checkbox" checked={style.has_highlight} onChange={(e) => updateStyle({ has_highlight: e.target.checked })} /> Active word color</label>
          <label className="toggle"><input type="checkbox" checked={style.has_keyword_emphasis} onChange={(e) => updateStyle({ has_keyword_emphasis: e.target.checked })} /> Keyword highlights</label>
          <label className="toggle"><input type="checkbox" checked={style.has_shadow} onChange={(e) => updateStyle({ has_shadow: e.target.checked })} /> Letter shadow</label>
        </div>
      )}

      {tab === 'graphics' && (
        <div className="stack">
          <div className="graphics-header">
            <h3>Graphics</h3>
            <button className="add-graphic-btn" onClick={() => setShowAddPanel((v) => !v)}>
              <Plus size={14} /> Add
            </button>
          </div>

          {showAddPanel && (
            <div className="add-graphic-panel">
              <p className="eyebrow">New Graphic at {currentTime.toFixed(2)}s</p>
              <Field label="Template">
                <select value={newTemplate} onChange={(e) => setNewTemplate(e.target.value as GraphicTemplateId)}>
                  {TEMPLATES.map((t) => <option key={t.id} value={t.id}>{t.label} ({t.track})</option>)}
                </select>
              </Field>
              <Field label="Title (optional)">
                <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder={TEMPLATES.find((t) => t.id === newTemplate)?.label} />
              </Field>
              <div className="add-graphic-actions">
                <button className="primary-btn" onClick={handleAddGraphic}><Plus size={14} /> Place on Timeline</button>
                <button className="secondary-btn" onClick={() => setShowAddPanel(false)}>Cancel</button>
              </div>
            </div>
          )}

          {selectedGraphic ? (
            <>
              <div className="selected-graphic-header">
                <span className="graphic-template-badge">{selectedGraphic.template_id}</span>
                <button className="delete-graphic-btn" onClick={() => onGraphicDelete(selectedGraphic.id)} title="Delete graphic">
                  <Trash2 size={13} />
                </button>
              </div>
              <Field label="Title"><input value={selectedGraphic.title} onChange={(e) => onGraphicChange({ ...selectedGraphic, title: e.target.value })} /></Field>
              <Field label="Track">
                <select value={selectedGraphic.track} onChange={(e) => onGraphicChange({ ...selectedGraphic, track: e.target.value as TrackId })}>
                  {(['V5','V4','V3','V2','V1'] as TrackId[]).map((t) => <option key={t}>{t}</option>)}
                </select>
              </Field>
              <Field label="Start"><input type="number" step="0.1" value={selectedGraphic.start} onChange={(e) => onGraphicChange({ ...selectedGraphic, start: Number(e.target.value) })} /></Field>
              <Field label="End"><input type="number" step="0.1" value={selectedGraphic.end} onChange={(e) => onGraphicChange({ ...selectedGraphic, end: Number(e.target.value) })} /></Field>
              <Field label={`Scale ${(selectedGraphic.scale ?? 1).toFixed(2)}x`}>
                <input type="range" min="0.5" max="1.5" step="0.01" value={selectedGraphic.scale ?? 1} onChange={(e) => onGraphicChange({ ...selectedGraphic, scale: Number(e.target.value) })} />
              </Field>
              <div className="stock-search">
                <input value={stockQuery} onChange={(e) => setStockQuery(e.target.value)} placeholder="Search stock media" />
                <button className="secondary-btn" onClick={searchStock}>Search</button>
              </div>
              <div className="stock-grid">
                {stockResults.map((item) => (
                  <button key={item.id} onClick={() => attachStock(item)}>
                    <img src={api.assetUrl(item.thumb_url)} alt={item.title} />
                    <span>{item.title}</span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <p className="muted">Select a timeline graphic to edit, or click Add to place a new one at the playhead.</p>
          )}
        </div>
      )}

      {tab === 'ai' && (
        <div className="stack">
          <h3>Twelve Labs</h3>
          <p className="muted">{credits}</p>
          <Field label="API Key">
            <input type="password" placeholder="Paste Twelve Labs key" onBlur={async (e) => {
              if (!e.target.value) return;
              const r = await api.setTwelveLabsKey(e.target.value);
              setCredits(`Configured: ${r.masked}`);
            }} />
          </Field>
          <p className="muted">Local semantic engine active until Twelve Labs key is configured.</p>
        </div>
      )}

      {tab === 'export' && (
        <div className="stack">
          <ExportPanel project={project} renderProgress={renderProgress} onRender={onRender} downloadUrl={downloadUrl} />
          <div className="export-divider" />
          <h3>Settings</h3>
          <Field label="Aspect ratio">
            <select value={project.settings.aspect_ratio} onChange={(e) => onProjectChange({ ...project, settings: { ...project.settings, aspect_ratio: e.target.value as ProjectState['settings']['aspect_ratio'] } })}>
              <option value="9:16">9:16 Vertical</option><option value="16:9">16:9 Landscape</option><option value="1:1">1:1 Square</option>
            </select>
          </Field>
          <Field label="FPS"><input type="number" value={project.settings.fps} onChange={(e) => onProjectChange({ ...project, settings: { ...project.settings, fps: Number(e.target.value) } })} /></Field>
          <Field label="Preset"><input value={project.settings.export_preset} onChange={(e) => onProjectChange({ ...project, settings: { ...project.settings, export_preset: e.target.value } })} /></Field>
        </div>
      )}
    </aside>
  );
}

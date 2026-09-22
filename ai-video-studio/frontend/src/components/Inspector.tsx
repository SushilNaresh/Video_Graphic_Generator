import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api/client';
import type { CaptionStyle, MotionGraphicItem, ProjectState, RenderProgress, StockMediaItem } from '../types';
import { ExportPanel } from './ExportPanel';

const DEFAULT_STYLE: CaptionStyle = {
  font_family: 'Inter',
  font_size: 42,
  font_weight: '800',
  uppercase: true,
  text_color: '#FFFFFF',
  active_word_color: '#38BDF8',
  past_word_color: '#B0B0B0',
  has_highlight: true,
  has_keyword_emphasis: true,
  has_shadow: true
};

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

export function Inspector({
  project,
  selectedGraphic,
  onProjectChange,
  onGraphicChange,
  onStatus,
  renderProgress,
  onRender,
  downloadUrl
}: {
  project: ProjectState | null;
  selectedGraphic: MotionGraphicItem | null;
  onProjectChange: (project: ProjectState) => void;
  onGraphicChange: (graphic: MotionGraphicItem) => void;
  onStatus: (status: string) => void;
  renderProgress: RenderProgress | null;
  onRender: () => void;
  downloadUrl: string | null;
}) {
  const [tab, setTab] = useState<'subtitles' | 'graphics' | 'export' | 'ai'>('subtitles');
  const [stockQuery, setStockQuery] = useState('medical research report');
  const [stockResults, setStockResults] = useState<StockMediaItem[]>([]);
  const [credits, setCredits] = useState<string>('Checking credits...');

  useEffect(() => {
    api.getTwelveLabsCredits()
      .then((next) => setCredits(next.configured ? `${next.remaining_minutes.toFixed(0)} min remaining` : 'No key configured'))
      .catch(() => setCredits('Credits unavailable'));
  }, []);

  if (!project) {
    return <aside className="inspector panel"><h3>Inspector</h3><p>Load a project to edit settings.</p></aside>;
  }

  const style = project.settings?.subtitle_style ?? DEFAULT_STYLE;

  function updateStyle(patch: Partial<CaptionStyle>) {
    const nextStyle = { ...style, ...patch };
    onProjectChange({
      ...project,
      settings: { ...project.settings, subtitle_style: nextStyle },
      captions: project.captions.map((caption) => ({ ...caption, style: { ...caption.style, ...patch } }))
    });
  }

  async function searchStock() {
    onStatus('Searching stock media...');
    const response = await api.searchStock(stockQuery);
    setStockResults(response.results);
    onStatus(`Found ${response.results.length} local stock placeholders`);
  }

  async function attachStock(item: StockMediaItem) {
    if (!selectedGraphic) return;
    onStatus('Attaching stock media...');
    const response = await api.downloadStock(project.id, item);
    onGraphicChange({
      ...selectedGraphic,
      parameters: { ...selectedGraphic.parameters, media_url: response.media_url, search_query: stockQuery },
      title: item.title
    });
    onStatus('Stock media attached');
  }

  return (
    <aside className="inspector panel">
      <div className="tab-row">
        {(['subtitles', 'graphics', 'ai', 'export'] as const).map((item) => (
          <button key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{item}</button>
        ))}
      </div>

      {tab === 'subtitles' && (
        <div className="stack">
          <h3>Subtitles</h3>
          <Field label="Font family">
            <select value={style.font_family} onChange={(event) => updateStyle({ font_family: event.target.value })}>
              <option>Inter</option><option>Playfair Display</option><option>JetBrains Mono</option><option>Montserrat</option>
            </select>
          </Field>
          <Field label={`Font size ${style.font_size}px`}>
            <input type="range" min="16" max="64" value={style.font_size} onChange={(event) => updateStyle({ font_size: Number(event.target.value) })} />
          </Field>
          <Field label="Weight">
            <select value={style.font_weight} onChange={(event) => updateStyle({ font_weight: event.target.value })}>
              <option value="400">Normal</option><option value="600">Medium</option><option value="800">Bold</option><option value="900">Extra Bold</option>
            </select>
          </Field>
          <Field label="Text color"><input type="color" value={style.text_color} onChange={(event) => updateStyle({ text_color: event.target.value })} /></Field>
          <Field label="Active word"><input type="color" value={style.active_word_color} onChange={(event) => updateStyle({ active_word_color: event.target.value })} /></Field>
          <Field label="Past word"><input type="color" value={style.past_word_color} onChange={(event) => updateStyle({ past_word_color: event.target.value })} /></Field>
          <label className="toggle"><input type="checkbox" checked={style.uppercase} onChange={(event) => updateStyle({ uppercase: event.target.checked })} /> Uppercase</label>
          <label className="toggle"><input type="checkbox" checked={style.has_highlight} onChange={(event) => updateStyle({ has_highlight: event.target.checked })} /> Active word color</label>
          <label className="toggle"><input type="checkbox" checked={style.has_keyword_emphasis} onChange={(event) => updateStyle({ has_keyword_emphasis: event.target.checked })} /> Keyword highlights</label>
          <label className="toggle"><input type="checkbox" checked={style.has_shadow} onChange={(event) => updateStyle({ has_shadow: event.target.checked })} /> Letter shadow</label>
        </div>
      )}

      {tab === 'graphics' && (
        <div className="stack">
          <h3>Graphics</h3>
          {selectedGraphic ? (
            <>
              <Field label="Title"><input value={selectedGraphic.title} onChange={(event) => onGraphicChange({ ...selectedGraphic, title: event.target.value })} /></Field>
              <Field label="Template"><input value={selectedGraphic.template_id} disabled /></Field>
              <Field label="Start"><input type="number" step="0.1" value={selectedGraphic.start} onChange={(event) => onGraphicChange({ ...selectedGraphic, start: Number(event.target.value) })} /></Field>
              <Field label="End"><input type="number" step="0.1" value={selectedGraphic.end} onChange={(event) => onGraphicChange({ ...selectedGraphic, end: Number(event.target.value) })} /></Field>
              <Field label="Scale"><input type="range" min="0.5" max="1.5" step="0.01" value={selectedGraphic.scale} onChange={(event) => onGraphicChange({ ...selectedGraphic, scale: Number(event.target.value) })} /></Field>
              <div className="stock-search">
                <input value={stockQuery} onChange={(event) => setStockQuery(event.target.value)} placeholder="Search stock media" />
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
          ) : <p>Select a timeline graphic to edit its controls.</p>}
        </div>
      )}

      {tab === 'ai' && (
        <div className="stack">
          <h3>Twelve Labs</h3>
          <p className="muted">{credits}</p>
          <Field label="API Key">
            <input type="password" placeholder="Paste Twelve Labs key" onBlur={async (event) => {
              if (!event.target.value) return;
              const response = await api.setTwelveLabsKey(event.target.value);
              setCredits(`Configured: ${response.masked}`);
            }} />
          </Field>
          <p className="muted">The scaffold uses local semantic generation until you wire a remote Twelve Labs client.</p>
        </div>
      )}

      {tab === 'export' && (
        <div className="stack">
          <ExportPanel
            project={project}
            renderProgress={renderProgress}
            onRender={onRender}
            downloadUrl={downloadUrl}
          />
          <div className="export-divider" />
          <h3>Settings</h3>
          <Field label="Aspect ratio">
            <select value={project.settings.aspect_ratio} onChange={(event) => onProjectChange({ ...project, settings: { ...project.settings, aspect_ratio: event.target.value as ProjectState['settings']['aspect_ratio'] } })}>
              <option value="9:16">9:16 Vertical</option><option value="16:9">16:9 Landscape</option><option value="1:1">1:1 Square</option>
            </select>
          </Field>
          <Field label="FPS"><input type="number" value={project.settings.fps} onChange={(event) => onProjectChange({ ...project, settings: { ...project.settings, fps: Number(event.target.value) } })} /></Field>
          <Field label="Preset"><input value={project.settings.export_preset} onChange={(event) => onProjectChange({ ...project, settings: { ...project.settings, export_preset: event.target.value } })} /></Field>
        </div>
      )}
    </aside>
  );
}

import { api } from '../api/client';
import type { MotionGraphicItem, ProjectState } from '../types';

function isActive(start: number, end: number, time: number) {
  return time >= start && time <= end;
}

function getParam(graphic: MotionGraphicItem, key: string, fallback = '') {
  const value = graphic.parameters?.[key];
  return typeof value === 'string' ? value : fallback;
}

function ActiveCaption({ project, currentTime }: { project: ProjectState; currentTime: number }) {
  const caption = project.captions?.find((item) => isActive(item.start, item.end, currentTime));
  if (!caption) return null;
  const style = caption.style ?? project.settings.subtitle_style;
  const words = caption.words?.length ? caption.words : caption.text.split(' ').map((word) => ({ text: word, start: caption.start, end: caption.end, confidence: 1 }));
  return (
    <div
      className={`caption-overlay ${style.has_shadow ? 'shadowed' : ''}`}
      style={{ fontFamily: style.font_family, fontSize: style.font_size, fontWeight: style.font_weight }}
    >
      {words.map((word, index) => {
        const active = style.has_highlight && isActive(word.start, word.end, currentTime);
        const past = word.end < currentTime;
        const color = active ? style.active_word_color : past ? style.past_word_color : style.text_color;
        return (
          <span key={`${word.text}-${index}`} style={{ color }}>
            {style.uppercase ? word.text.toUpperCase() : word.text}{' '}
          </span>
        );
      })}
    </div>
  );
}

function ArticleCard({ graphic }: { graphic: MotionGraphicItem }) {
  const mediaUrl = getParam(graphic, 'media_url');
  return (
    <div className="article-card">
      <div className="article-masthead">{getParam(graphic, 'publisher', 'Clinical Archive')}</div>
      <h2>{getParam(graphic, 'headline', graphic.title)}</h2>
      <p>{getParam(graphic, 'paragraph', 'Evidence card reconstructed from the script and timeline context.')}</p>
      {mediaUrl && <img src={api.assetUrl(mediaUrl)} alt="article figure" />}
      <div className="highlight-sweep" />
    </div>
  );
}

function EndCard({ graphic }: { graphic: MotionGraphicItem }) {
  return (
    <div className="medical-endcard">
      <div className="doctor-avatar">✓</div>
      <h2>{getParam(graphic, 'doctor_name', 'Dr. Studio')}</h2>
      <p>{getParam(graphic, 'tagline', 'Evidence-first explainers')}</p>
      <strong>{getParam(graphic, 'handle', '@aivideostudio')}</strong>
      <button>{getParam(graphic, 'cta', 'Follow for more')}</button>
    </div>
  );
}

function GraphicLayer({
  graphic,
  selected,
  onSelect
}: {
  graphic: MotionGraphicItem;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const template = graphic.template_id;
  const mediaUrl = getParam(graphic, 'media_url');
  return (
    <button
      className={`graphic-layer ${selected ? 'selected' : ''} template-${template}`}
      style={{ transform: `translate(-50%, -50%) scale(${graphic.scale ?? 1})`, left: `${(graphic.pos_x ?? 0.5) * 100}%`, top: `${(graphic.pos_y ?? 0.5) * 100}%` }}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(graphic.id);
      }}
    >
      {template === 'article_reconstruction' || template === 'digital_highlighter' ? <ArticleCard graphic={graphic} /> : null}
      {template === 'medical_endcard' ? <EndCard graphic={graphic} /> : null}
      {template === 'dimension_callout' ? (
        <div className="dimension-callout"><span>{getParam(graphic, 'value', graphic.title)}</span><small>{getParam(graphic, 'label', 'Dimension')}</small></div>
      ) : null}
      {(template === 'contextual_broll' || template === 'youtube_insert' || template === 'split_screen_vertical') && (
        <div className="broll-card">
          {mediaUrl ? <img src={api.assetUrl(mediaUrl)} alt={graphic.title} /> : <div className="broll-placeholder">{graphic.title}</div>}
        </div>
      )}
    </button>
  );
}

export function CanvasOverlay({
  project,
  currentTime,
  selectedGraphicId,
  onSelectGraphic
}: {
  project: ProjectState | null;
  currentTime: number;
  selectedGraphicId: string | null;
  onSelectGraphic: (id: string | null) => void;
}) {
  if (!project) return null;
  const activeGraphics = project.graphics?.filter((graphic) => isActive(graphic.start, graphic.end, currentTime)) ?? [];
  return (
    <div className="canvas-overlay" onClick={() => onSelectGraphic(null)}>
      {activeGraphics.map((graphic) => (
        <GraphicLayer
          key={graphic.id}
          graphic={graphic}
          selected={graphic.id === selectedGraphicId}
          onSelect={onSelectGraphic}
        />
      ))}
      <ActiveCaption project={project} currentTime={currentTime} />
    </div>
  );
}

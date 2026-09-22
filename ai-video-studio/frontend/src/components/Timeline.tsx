import type { MouseEvent } from 'react';
import type { MotionGraphicItem, ProjectState, TrackId } from '../types';

const TRACKS: TrackId[] = ['V5', 'V4', 'V3', 'V2', 'V1', 'A1', 'A2'];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function Timeline({
  project,
  currentTime,
  selectedGraphicId,
  onSeek,
  onSelectGraphic,
  onProjectChange
}: {
  project: ProjectState | null;
  currentTime: number;
  selectedGraphicId: string | null;
  onSeek: (time: number) => void;
  onSelectGraphic: (id: string | null) => void;
  onProjectChange: (project: ProjectState) => void;
}) {
  const duration = Math.max(10, project?.duration_seconds ?? 10, ...(project?.graphics ?? []).map((graphic) => graphic.end));

  function seekFromEvent(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = clamp((event.clientX - rect.left) / rect.width, 0, 1);
    onSeek(ratio * duration);
  }

  function moveGraphic(graphic: MotionGraphicItem, delta: number) {
    if (!project) return;
    const span = graphic.end - graphic.start;
    const start = clamp(graphic.start + delta, 0, Math.max(0, duration - span));
    const updated = { ...graphic, start, end: start + span };
    onProjectChange({ ...project, graphics: project.graphics.map((item) => (item.id === graphic.id ? updated : item)) });
  }

  return (
    <section className="timeline-card">
      <div className="timeline-ruler" onClick={seekFromEvent}>
        <div className="playhead" style={{ left: `${(currentTime / duration) * 100}%` }} />
        {Array.from({ length: 9 }).map((_, index) => (
          <span key={index} style={{ left: `${(index / 8) * 100}%` }}>{((duration * index) / 8).toFixed(0)}s</span>
        ))}
      </div>
      <div className="tracks">
        {TRACKS.map((track) => (
          <div key={track} className="track-row">
            <div className="track-label">{track}</div>
            <div className="track-lane" onClick={seekFromEvent}>
              {track === 'V1' && project?.source_media_path && <div className="clip speaker" style={{ left: 0, width: `${Math.min(100, ((project.duration_seconds || duration) / duration) * 100)}%` }}>Speaker Video</div>}
              {track === 'V2' && project?.captions?.map((caption) => (
                <div key={caption.id} className="clip caption" style={{ left: `${(caption.start / duration) * 100}%`, width: `${((caption.end - caption.start) / duration) * 100}%` }}>{caption.text}</div>
              ))}
              {project?.graphics?.filter((graphic) => graphic.track === track).map((graphic) => (
                <button
                  key={graphic.id}
                  className={`clip graphic ${graphic.id === selectedGraphicId ? 'selected' : ''}`}
                  style={{ left: `${(graphic.start / duration) * 100}%`, width: `${Math.max(1.2, ((graphic.end - graphic.start) / duration) * 100)}%` }}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelectGraphic(graphic.id);
                    onSeek(graphic.start);
                  }}
                  onDoubleClick={(event) => {
                    event.stopPropagation();
                    moveGraphic(graphic, 0.25);
                  }}
                  title="Double-click to nudge 0.25s"
                >
                  {graphic.title}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

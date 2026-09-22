import { Maximize2, Pause, Play, RotateCcw, Volume2 } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { api } from '../api/client';
import type { ProjectState } from '../types';
import { CanvasOverlay } from './CanvasOverlay';

export function VideoViewer({
  project,
  currentTime,
  playing,
  selectedGraphicId,
  onTimeUpdate,
  onPlayingChange,
  onSelectGraphic
}: {
  project: ProjectState | null;
  currentTime: number;
  playing: boolean;
  selectedGraphicId: string | null;
  onTimeUpdate: (time: number) => void;
  onPlayingChange: (playing: boolean) => void;
  onSelectGraphic: (id: string | null) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const aspectRatio = project?.settings?.aspect_ratio ?? '9:16';
  const hasVideo = Boolean(project?.source_media_path);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || Math.abs(video.currentTime - currentTime) < 0.25) return;
    video.currentTime = currentTime;
  }, [currentTime]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (playing) {
      video.play().catch(() => onPlayingChange(false));
    } else {
      video.pause();
    }
  }, [playing, onPlayingChange]);

  return (
    <section className="viewer-card">
      <div className={`video-frame aspect-${aspectRatio.replace(':', '-')}`}>
        {project && hasVideo ? (
          <video
            ref={videoRef}
            src={api.sourceVideoUrl(project.id)}
            onTimeUpdate={(event) => onTimeUpdate(event.currentTarget.currentTime)}
            onPlay={() => onPlayingChange(true)}
            onPause={() => onPlayingChange(false)}
            playsInline
          />
        ) : (
          <div className="video-empty">
            <strong>No source video yet</strong>
            <span>Drop footage to begin building the timeline.</span>
          </div>
        )}
        <CanvasOverlay
          project={project}
          currentTime={currentTime}
          selectedGraphicId={selectedGraphicId}
          onSelectGraphic={onSelectGraphic}
        />
      </div>
      <div className="transport-bar">
        <button onClick={() => onTimeUpdate(0)}><RotateCcw size={16} /></button>
        <button className="play-btn" onClick={() => onPlayingChange(!playing)}>{playing ? <Pause size={18} /> : <Play size={18} />}</button>
        <span>{currentTime.toFixed(2)} / {(project?.duration_seconds ?? 0).toFixed(2)}s</span>
        <Volume2 size={16} />
        <Maximize2 size={16} />
      </div>
    </section>
  );
}

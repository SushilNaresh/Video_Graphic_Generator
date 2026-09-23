export type AspectRatio = '9:16' | '16:9' | '1:1';
export type TrackId = 'V5' | 'V4' | 'V3' | 'V2' | 'V1' | 'A1' | 'A2';

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

export interface SkillNote {
  ts: string;
  graphic_id: string;
  template_id: string;
  trigger: string;
  note: string;
  author: string;
}

export type GraphicTemplateId =
  | 'split_screen_vertical'
  | 'article_reconstruction'
  | 'digital_highlighter'
  | 'contextual_broll'
  | 'youtube_insert'
  | 'split_silhouette_walking'
  | 'split_silhouette_falling'
  | 'kinetic_3d_block'
  | 'editorial_dual_font'
  | 'kinetic_typography'
  | 'silhouette_curve'
  | 'stat_counter'
  | 'thematic_canvas'
  | 'jargon_translation'
  | 'metaphor_sequence'
  | 'dimension_callout'
  | 'source_citation'
  | 'sticker_cutout'
  | 'medical_endcard';

export interface WordTiming {
  text: string;
  start: number;
  end: number;
  confidence: number;
}

export interface CaptionStyle {
  font_family: string;
  font_size: number;
  font_weight: string;
  uppercase: boolean;
  text_color: string;
  active_word_color: string;
  past_word_color: string;
  has_highlight: boolean;
  has_keyword_emphasis: boolean;
  has_shadow: boolean;
}

export interface CaptionItem {
  id: string;
  start: number;
  end: number;
  text: string;
  words: WordTiming[];
  style: CaptionStyle;
}

export interface MotionGraphicItem {
  id: string;
  start: number;
  end: number;
  template_id: GraphicTemplateId;
  title: string;
  parameters: Record<string, unknown>;
  pos_x: number;
  pos_y: number;
  scale: number;
  track: TrackId;
  locked: boolean;
}

export interface ProjectSettings {
  aspect_ratio: AspectRatio;
  export_preset: string;
  fps: number;
  width: number;
  height: number;
  subtitle_style: CaptionStyle;
}

export interface ProjectState {
  id: string;
  name: string;
  source_media_path?: string | null;
  proxy_media_path?: string | null;
  duration_seconds: number;
  captions: CaptionItem[];
  graphics: MotionGraphicItem[];
  settings: ProjectSettings;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  duration_seconds: number;
  has_source_video: boolean;
  updated_at: string;
}

export interface UploadResponse {
  id: string;
  project_id: string;
  filename: string;
  bytes_written: number;
  duration_seconds: number;
  project: ProjectState;
}

export interface StockMediaItem {
  id: string;
  provider: string;
  media_type: 'image' | 'video';
  title: string;
  thumb_url: string;
  download_url: string;
  width: number;
  height: number;
  duration?: number | null;
  license: string;
}

export interface StockSearchResponse {
  query: string;
  results: StockMediaItem[];
}

export interface TaskStatus {
  task_id: string;
  status: 'queued' | 'running' | 'ready' | 'failed';
  progress: number;
  message: string;
  graphics: MotionGraphicItem[];
}

export interface RenderProgress {
  render_id?: string | null;
  status: 'idle' | 'queued' | 'running' | 'ready' | 'failed';
  progress: number;
  message: string;
}

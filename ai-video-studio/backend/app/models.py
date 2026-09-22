from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AspectRatio = Literal["9:16", "16:9", "1:1"]
TrackId = Literal["V5", "V4", "V3", "V2", "V1", "A1", "A2"]
GraphicTemplateId = Literal[
    "split_screen_vertical",
    "article_reconstruction",
    "digital_highlighter",
    "contextual_broll",
    "youtube_insert",
    "split_silhouette_walking",
    "split_silhouette_falling",
    "kinetic_3d_block",
    "editorial_dual_font",
    "kinetic_typography",
    "silhouette_curve",
    "stat_counter",
    "thematic_canvas",
    "jargon_translation",
    "metaphor_sequence",
    "dimension_callout",
    "source_citation",
    "sticker_cutout",
    "medical_endcard",
]


class WordTiming(BaseModel):
    text: str
    start: float
    end: float
    confidence: float = 1.0


class CaptionStyle(BaseModel):
    font_family: str = "Inter"
    font_size: int = 42
    font_weight: str = "800"
    uppercase: bool = True
    text_color: str = "#FFFFFF"
    active_word_color: str = "#38BDF8"
    past_word_color: str = "#B0B0B0"
    has_highlight: bool = True
    has_keyword_emphasis: bool = True
    has_shadow: bool = True


class CaptionItem(BaseModel):
    id: str
    start: float
    end: float
    text: str
    words: list[WordTiming] = Field(default_factory=list)
    style: CaptionStyle = Field(default_factory=CaptionStyle)


class MotionGraphicItem(BaseModel):
    id: str
    start: float
    end: float
    template_id: GraphicTemplateId
    title: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    pos_x: float = 0.5
    pos_y: float = 0.5
    scale: float = 1.0
    track: TrackId = "V3"
    locked: bool = False


class ProjectSettings(BaseModel):
    aspect_ratio: AspectRatio = "9:16"
    export_preset: str = "1080p_h264"
    fps: int = 30
    width: int = 1080
    height: int = 1920
    subtitle_style: CaptionStyle = Field(default_factory=CaptionStyle)


class ProjectState(BaseModel):
    id: str
    name: str
    source_media_path: str | None = None
    proxy_media_path: str | None = None
    duration_seconds: float = 0.0
    captions: list[CaptionItem] = Field(default_factory=list)
    graphics: list[MotionGraphicItem] = Field(default_factory=list)
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ProjectSummary(BaseModel):
    id: str
    name: str
    duration_seconds: float
    has_source_video: bool
    updated_at: str


class UploadResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    bytes_written: int
    duration_seconds: float
    project: ProjectState


class StockMediaItem(BaseModel):
    id: str
    provider: str
    media_type: Literal["image", "video"]
    title: str
    thumb_url: str
    download_url: str
    width: int = 1080
    height: int = 1920
    duration: float | None = None
    license: str = "Preview / provider terms"


class StockSearchResponse(BaseModel):
    query: str
    results: list[StockMediaItem]


class StockDownloadRequest(BaseModel):
    project_id: str
    item: StockMediaItem


class StockDownloadResponse(BaseModel):
    media_url: str
    filename: str


class TwelveLabsKeyRequest(BaseModel):
    api_key: str


class TwelveLabsCredits(BaseModel):
    configured: bool
    consumed_minutes: float
    remaining_minutes: float
    expires_at: str | None = None


class TaskStatus(BaseModel):
    task_id: str
    status: Literal["queued", "running", "ready", "failed"]
    progress: float
    message: str = ""
    graphics: list[MotionGraphicItem] = Field(default_factory=list)


class RenderResponse(BaseModel):
    render_id: str
    status: Literal["queued", "running", "ready", "failed"]
    output_url: str | None = None


class RenderProgress(BaseModel):
    render_id: str | None = None
    status: Literal["idle", "queued", "running", "ready", "failed"] = "idle"
    progress: float = 0.0
    message: str = ""

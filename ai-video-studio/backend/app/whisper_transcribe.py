from __future__ import annotations

import uuid
from pathlib import Path

from .models import CaptionItem, WordTiming

_model = None
WHISPER_MODEL = "base"   # tiny | base | small | medium — trade speed vs accuracy


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def _segments_to_captions(segments) -> list[CaptionItem]:
    captions: list[CaptionItem] = []
    for seg in segments:
        words: list[WordTiming] = []
        raw_words = seg.words or []
        if raw_words:
            for w in raw_words:
                words.append(WordTiming(
                    text=w.word.strip(),
                    start=round(w.start, 3),
                    end=round(w.end, 3),
                    confidence=round(w.probability, 3),
                ))
        else:
            # No word-level data — distribute evenly across segment
            tokens = seg.text.strip().split()
            duration = max(0.01, seg.end - seg.start)
            step = duration / max(1, len(tokens))
            for idx, token in enumerate(tokens):
                ws = round(seg.start + idx * step, 3)
                words.append(WordTiming(
                    text=token,
                    start=ws,
                    end=round(min(seg.end, ws + step * 0.9), 3),
                    confidence=1.0,
                ))

        captions.append(CaptionItem(
            id=f"cap_{uuid.uuid4().hex[:8]}",
            start=round(seg.start, 3),
            end=round(seg.end, 3),
            text=seg.text.strip(),
            words=words,
        ))
    return captions


def transcribe(video_path: Path) -> list[CaptionItem]:
    """
    Run faster-whisper on the video file directly (no WAV extraction needed).
    Returns word-timed CaptionItems.
    Raises on failure — caller should catch and fall back to synthetic_transcript.
    """
    model = _get_model()
    segments, _info = model.transcribe(
        str(video_path),
        word_timestamps=True,
        language=None,   # auto-detect
        vad_filter=True, # skip silent sections for speed
    )
    # segments is a generator — consume it fully before returning
    return _segments_to_captions(list(segments))

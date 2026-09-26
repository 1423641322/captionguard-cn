from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import RawSegment, RawWord


@dataclass(slots=True)
class EngineResult:
    segments: list[RawSegment]
    language: str | None
    language_probability: float | None
    duration: float


class TranscriptionEngine(Protocol):
    def transcribe(
        self, audio_path: Path, *, language: str | None, hotwords: str | None
    ) -> EngineResult: ...


class FasterWhisperEngine:
    def __init__(self, model_size: str = "small") -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                'faster-whisper is not installed. Run: pip install -e ".[asr]"'
            ) from exc

        self._model = WhisperModel(model_size, device="auto", compute_type="auto")

    def transcribe(
        self, audio_path: Path, *, language: str | None, hotwords: str | None
    ) -> EngineResult:
        segments, info = self._model.transcribe(
            str(audio_path),
            language=language,
            hotwords=hotwords or None,
            vad_filter=True,
            word_timestamps=True,
            beam_size=5,
        )
        raw_segments: list[RawSegment] = []
        for segment in segments:
            words = [
                RawWord(
                    text=word.word,
                    start=float(word.start),
                    end=float(word.end),
                    probability=float(word.probability),
                )
                for word in (segment.words or [])
            ]
            raw_segments.append(
                RawSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    text=segment.text,
                    words=words,
                )
            )
        return EngineResult(
            segments=raw_segments,
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
            duration=float(getattr(info, "duration", 0.0)),
        )


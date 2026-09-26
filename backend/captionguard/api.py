from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .engine import FasterWhisperEngine
from .models import HealthResponse, TranscriptionResponse
from .pipeline import build_subtitles
from .srt import render_srt

MAX_UPLOAD_BYTES = int(os.getenv("CAPTIONGUARD_MAX_UPLOAD_BYTES", str(2 * 1024**3)))
ALLOWED_MODEL_SIZES = {"tiny", "base", "small", "medium", "large-v3", "turbo"}

app = FastAPI(title="CaptionGuard CN", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache(maxsize=3)
def _get_engine(model_size: str) -> FasterWhisperEngine:
    return FasterWhisperEngine(model_size=model_size)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(version=__version__)


def _parse_glossary(value: str) -> Mapping[str, str]:
    if not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="glossary_json is not valid JSON") from exc
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in parsed.items()
    ):
        raise HTTPException(status_code=422, detail="glossary_json must be a string map")
    return parsed


@app.post("/v1/transcriptions", response_model=TranscriptionResponse)
async def transcribe(
    file: Annotated[UploadFile, File()],
    language: Annotated[str, Form()] = "auto",
    model_size: Annotated[str, Form()] = "small",
    max_chars: Annotated[int, Form(ge=4, le=80)] = 20,
    confidence_threshold: Annotated[float, Form(ge=0.0, le=1.0)] = 0.72,
    glossary_json: Annotated[str, Form()] = "{}",
) -> TranscriptionResponse:
    if model_size not in ALLOWED_MODEL_SIZES:
        raise HTTPException(status_code=422, detail="Unsupported model_size")
    glossary = _parse_glossary(glossary_json)

    suffix = Path(file.filename or "audio.wav").suffix[:10] or ".wav"
    temp_path: Path | None = None
    total_bytes = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Audio file is too large")
                temp_file.write(chunk)

        try:
            engine = _get_engine(model_size)
            result = engine.transcribe(
                temp_path,
                language=None if language == "auto" else language,
                hotwords=", ".join(glossary.values()),
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        subtitles = build_subtitles(
            result.segments,
            glossary=glossary,
            max_chars=max_chars,
            confidence_threshold=confidence_threshold,
        )
        return TranscriptionResponse(
            language=result.language,
            language_probability=result.language_probability,
            duration=result.duration,
            segments=subtitles,
            review_count=sum(segment.needs_review for segment in subtitles),
            srt=render_srt(subtitles),
        )
    finally:
        await file.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def run() -> None:
    uvicorn.run("captionguard.api:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()


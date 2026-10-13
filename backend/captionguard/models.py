from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class RawWord(BaseModel):
    text: str
    start: float
    end: float
    probability: float | None = None


class RawSegment(BaseModel):
    start: float
    end: float
    text: str
    words: list[RawWord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time_range(self) -> RawSegment:
        if self.start < 0 or self.end < self.start:
            raise ValueError("Invalid segment time range")
        return self


class SubtitleSegment(BaseModel):
    index: int
    start: float
    end: float
    text: str
    confidence: float | None = None
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)


class TranscriptionResponse(BaseModel):
    language: str | None = None
    language_probability: float | None = None
    duration: float
    segments: list[SubtitleSegment]
    review_count: int
    srt: str


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "captionguard-cn"
    version: str


class LanguageOption(BaseModel):
    code: str
    name: str


class LanguageOptionsResponse(BaseModel):
    languages: list[LanguageOption]


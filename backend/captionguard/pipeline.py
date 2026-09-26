from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .models import RawSegment, SubtitleSegment

_BREAK_AFTER = re.compile(r"(?<=[。！？!?；;，,、])")
_SPACE_RUN = re.compile(r"\s+")


def apply_glossary(text: str, glossary: Mapping[str, str]) -> str:
    """Apply terms in one pass so replacements are never replaced again."""
    sources = [source for source in sorted(glossary, key=len, reverse=True) if source]
    if not sources:
        return text
    pattern = re.compile("|".join(re.escape(source) for source in sources))
    return pattern.sub(lambda match: glossary[match.group(0)], text)


def normalize_text(text: str) -> str:
    text = _SPACE_RUN.sub(" ", text).strip()
    text = re.sub(r"\s+([，。！？、；：,.!?;:])", r"\1", text)
    return text


def split_text(text: str, max_chars: int) -> list[str]:
    """Split Chinese-first subtitle text while preferring punctuation boundaries."""
    text = normalize_text(text)
    if not text:
        return []
    if max_chars < 4:
        raise ValueError("max_chars must be at least 4")
    if len(text) <= max_chars:
        return [text]

    clauses = [part for part in _BREAK_AFTER.split(text) if part]
    pieces: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current:
            pieces.append(current.strip())
            current = ""

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        if len(current) + len(clause) <= max_chars:
            current += clause
            continue
        flush()
        while len(clause) > max_chars:
            boundary = _best_boundary(clause, max_chars)
            pieces.append(clause[:boundary].strip())
            clause = clause[boundary:].strip()
        current = clause
    flush()
    return [piece for piece in pieces if piece]


def _best_boundary(text: str, max_chars: int) -> int:
    window = text[: max_chars + 1]
    for marker in (" ", "，", ",", "、", "；", ";"):
        position = window.rfind(marker)
        if position >= max_chars // 2:
            return position + (0 if marker == " " else 1)
    return max_chars


def segment_confidence(segment: RawSegment) -> float | None:
    probabilities = [
        word.probability for word in segment.words if word.probability is not None
    ]
    if not probabilities:
        return None
    return sum(probabilities) / len(probabilities)


def build_subtitles(
    raw_segments: Sequence[RawSegment],
    *,
    glossary: Mapping[str, str] | None = None,
    max_chars: int = 20,
    confidence_threshold: float = 0.72,
    minimum_duration: float = 0.45,
) -> list[SubtitleSegment]:
    glossary = glossary or {}
    subtitles: list[SubtitleSegment] = []

    for raw in raw_segments:
        text = apply_glossary(normalize_text(raw.text), glossary)
        pieces = split_text(text, max_chars)
        if not pieces:
            continue

        total_weight = sum(max(len(piece), 1) for piece in pieces)
        duration = max(raw.end - raw.start, 0.001)
        cursor = raw.start
        confidence = segment_confidence(raw)

        for piece_index, piece in enumerate(pieces):
            if piece_index == len(pieces) - 1:
                piece_end = raw.end
            else:
                piece_end = cursor + duration * (len(piece) / total_weight)

            reasons: list[str] = []
            if confidence is not None and confidence < confidence_threshold:
                reasons.append("low_confidence")
            if piece_end - cursor < minimum_duration:
                reasons.append("too_short")
            if len(piece) == 1:
                reasons.append("single_character")

            subtitles.append(
                SubtitleSegment(
                    index=len(subtitles) + 1,
                    start=round(cursor, 3),
                    end=round(piece_end, 3),
                    text=piece,
                    confidence=round(confidence, 4) if confidence is not None else None,
                    needs_review=bool(reasons),
                    review_reasons=reasons,
                )
            )
            cursor = piece_end

    return subtitles


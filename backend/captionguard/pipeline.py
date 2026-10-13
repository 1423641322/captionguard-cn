from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .models import RawSegment, SubtitleSegment

_CJK_BREAK_AFTER = re.compile(r"(?<=[。！？!?；;，,、])")
_SPACED_BREAK_AFTER = re.compile(r"(?<=[。！？.!?；;：:])\s*")
_SPACE_RUN = re.compile(r"\s+")
_CJK_CHARACTER = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
_LATIN_CHARACTER = re.compile(r"[A-Za-z]")
_CJK_LANGUAGES = {"zh", "yue", "ja"}


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


def recommended_max_chars(language: str | None, text: str = "") -> int:
    if language == "zh-en":
        return 32
    if language in _CJK_LANGUAGES:
        return 20
    if language == "ko":
        return 30
    if language is None and _CJK_CHARACTER.search(text):
        return 20
    return 42


def _uses_spaced_layout(text: str, language: str | None) -> bool:
    if language == "zh-en":
        return True
    if language is None:
        return bool(_LATIN_CHARACTER.search(text) and " " in text)
    if language not in _CJK_LANGUAGES:
        return True
    return bool(_LATIN_CHARACTER.search(text) and " " in text)


def split_text(text: str, max_chars: int = 0, *, language: str | None = None) -> list[str]:
    """Split subtitles using CJK or space-delimited language conventions."""
    text = normalize_text(text)
    if not text:
        return []
    if max_chars == 0:
        max_chars = recommended_max_chars(language, text)
    elif max_chars < 4:
        raise ValueError("max_chars must be at least 4")
    if len(text) <= max_chars:
        return [text]

    spaced_layout = _uses_spaced_layout(text, language)
    break_pattern = _SPACED_BREAK_AFTER if spaced_layout else _CJK_BREAK_AFTER
    clauses = [part for part in break_pattern.split(text) if part]
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
        separator = " " if spaced_layout and current else ""
        candidate = current + separator + clause
        if len(candidate) <= max_chars:
            current = candidate
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
    max_chars: int = 0,
    language: str | None = None,
    confidence_threshold: float = 0.72,
    minimum_duration: float = 0.45,
) -> list[SubtitleSegment]:
    glossary = glossary or {}
    subtitles: list[SubtitleSegment] = []

    for raw in raw_segments:
        text = apply_glossary(normalize_text(raw.text), glossary)
        pieces = split_text(text, max_chars, language=language)
        if not pieces:
            continue

        total_weight = sum(_text_weight(piece) for piece in pieces)
        duration = max(raw.end - raw.start, 0.001)
        cursor = raw.start
        confidence = segment_confidence(raw)

        for piece_index, piece in enumerate(pieces):
            if piece_index == len(pieces) - 1:
                piece_end = raw.end
            else:
                piece_end = cursor + duration * (_text_weight(piece) / total_weight)

            reasons: list[str] = []
            if confidence is not None and confidence < confidence_threshold:
                reasons.append("low_confidence")
            if piece_end - cursor < minimum_duration:
                reasons.append("too_short")
            if _text_weight(piece) == 1:
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


def _text_weight(text: str) -> int:
    return max(len(_SPACE_RUN.sub("", text)), 1)


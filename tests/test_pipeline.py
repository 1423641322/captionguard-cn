import pytest
from captionguard.models import RawSegment, RawWord
from captionguard.pipeline import (
    apply_glossary,
    build_subtitles,
    recommended_max_chars,
    split_text,
)


def test_glossary_uses_longest_key_first() -> None:
    assert apply_glossary("Open AI 模型", {"Open": "开放", "Open AI": "OpenAI"}) == "OpenAI 模型"


def test_split_text_prefers_chinese_punctuation() -> None:
    text = "这是第一句话，这是第二句话。最后一句。"
    assert split_text(text, 10) == ["这是第一句话，", "这是第二句话。", "最后一句。"]


def test_split_text_preserves_english_word_spacing() -> None:
    text = "CaptionGuard creates accurate captions. English spacing stays readable."
    pieces = split_text(text, 42, language="en")
    assert pieces == ["CaptionGuard creates accurate captions.", "English spacing stays readable."]
    assert all(not piece.startswith(" ") and not piece.endswith(" ") for piece in pieces)


def test_automatic_caption_length_is_language_aware() -> None:
    assert recommended_max_chars("zh") == 20
    assert recommended_max_chars("zh-en") == 32
    assert recommended_max_chars("en") == 42


def test_build_subtitles_marks_low_confidence() -> None:
    raw = RawSegment(
        start=0,
        end=2,
        text="欢迎使用 Caption Guard",
        words=[RawWord(text="欢迎", start=0, end=0.5, probability=0.5)],
    )
    subtitles = build_subtitles(
        [raw], glossary={"Caption Guard": "CaptionGuard"}, max_chars=30
    )
    assert subtitles[0].text == "欢迎使用 CaptionGuard"
    assert subtitles[0].needs_review is True
    assert "low_confidence" in subtitles[0].review_reasons


def test_split_text_rejects_too_small_limit() -> None:
    with pytest.raises(ValueError):
        split_text("字幕", 3)


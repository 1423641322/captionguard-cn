from captionguard.models import SubtitleSegment
from captionguard.srt import format_timestamp, render_srt


def test_format_timestamp_rounds_milliseconds() -> None:
    assert format_timestamp(3661.2346) == "01:01:01,235"


def test_render_srt() -> None:
    result = render_srt(
        [
            SubtitleSegment(index=99, start=0, end=1.5, text="你好"),
            SubtitleSegment(index=100, start=1.5, end=3, text="世界"),
        ]
    )
    assert result == (
        "1\n00:00:00,000 --> 00:00:01,500\n你好\n\n"
        "2\n00:00:01,500 --> 00:00:03,000\n世界\n"
    )


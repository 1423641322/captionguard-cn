from captionguard import api
from captionguard.engine import EngineResult
from captionguard.models import RawSegment, RawWord
from fastapi.testclient import TestClient

MISHEARD = "\u666e\u5229\u7c73\u5c14"
CORRECT = "Premiere"


class FakeEngine:
    def transcribe(
        self,
        audio_path,
        *,
        language,
        hotwords,
        multilingual=False,
        initial_prompt=None,
        language_detection_segments=1,
    ):
        assert audio_path.exists()
        assert language is None
        assert hotwords == CORRECT
        assert multilingual is True
        assert initial_prompt is None
        assert language_detection_segments == 5
        return EngineResult(
            segments=[
                RawSegment(
                    start=0,
                    end=1.5,
                    text=MISHEARD,
                    words=[
                        RawWord(
                            text=MISHEARD,
                            start=0,
                            end=1.5,
                            probability=0.91,
                        )
                    ],
                )
            ],
            language="zh",
            language_probability=0.98,
            duration=1.5,
        )


def test_health() -> None:
    response = TestClient(api.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_all_whisper_languages_are_available() -> None:
    response = TestClient(api.app).get("/v1/languages")
    assert response.status_code == 200
    languages = response.json()["languages"]
    assert len(languages) == 100
    assert {item["code"] for item in languages} >= {"zh", "en", "yue", "fr", "ar"}


def test_transcription_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(api, "_get_engine", lambda model_size: FakeEngine())
    response = TestClient(api.app).post(
        "/v1/transcriptions",
        files={"file": ("sample.wav", b"RIFF fake wave", "audio/wav")},
        data={
            "language": "auto",
            "model_size": "small",
            "glossary_json": '{"\\u666e\\u5229\\u7c73\\u5c14":"Premiere"}',
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["segments"][0]["text"] == CORRECT
    assert "00:00:00,000 --> 00:00:01,500" in payload["srt"]


def test_invalid_glossary_is_rejected_before_model_load(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "_get_engine",
        lambda model_size: (_ for _ in ()).throw(AssertionError("must not load model")),
    )
    response = TestClient(api.app).post(
        "/v1/transcriptions",
        files={"file": ("sample.wav", b"fake", "audio/wav")},
        data={"glossary_json": "[]"},
    )
    assert response.status_code == 422


def test_invalid_language_is_rejected_before_model_load(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "_get_engine",
        lambda model_size: (_ for _ in ()).throw(AssertionError("must not load model")),
    )
    response = TestClient(api.app).post(
        "/v1/transcriptions",
        files={"file": ("sample.wav", b"fake", "audio/wav")},
        data={"language": "not-a-language"},
    )
    assert response.status_code == 422


def test_chinese_english_mode_enables_segment_language_detection(monkeypatch) -> None:
    class MixedEngine:
        def transcribe(
            self,
            audio_path,
            *,
            language,
            hotwords,
            multilingual=False,
            initial_prompt=None,
            language_detection_segments=1,
        ):
            assert language is None
            assert multilingual is True
            assert initial_prompt == "中文 English"
            assert language_detection_segments == 5
            return EngineResult(
                segments=[RawSegment(start=0, end=1, text="欢迎 to CaptionGuard")],
                language="zh",
                language_probability=0.8,
                duration=1,
            )

    monkeypatch.setattr(api, "_get_engine", lambda model_size: MixedEngine())
    response = TestClient(api.app).post(
        "/v1/transcriptions",
        files={"file": ("mixed.wav", b"fake", "audio/wav")},
        data={"language": "zh-en"},
    )
    assert response.status_code == 200
    assert response.json()["segments"][0]["text"] == "欢迎 to CaptionGuard"

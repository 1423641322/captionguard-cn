from captionguard import api
from captionguard.engine import EngineResult
from captionguard.models import RawSegment, RawWord
from fastapi.testclient import TestClient

MISHEARD = "\u666e\u5229\u7c73\u5c14"
CORRECT = "Premiere"


class FakeEngine:
    def transcribe(self, audio_path, *, language, hotwords):
        assert audio_path.exists()
        assert language is None
        assert hotwords == CORRECT
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

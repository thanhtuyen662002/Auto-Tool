from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from app.modules.tts.providers.google_cloud_tts_provider import GoogleCloudTTSProvider
from app.modules.tts.providers.base import TTSProviderError
from app.modules.tts.tts_schema import TTSResult, TTSSettings


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_google_cloud_tts_provider_synthesizes_mp3(tmp_path, monkeypatch):
    def fake_urlopen(request, timeout):
        assert "text:synthesize" in request.full_url
        assert "key=" not in request.full_url
        assert request.headers["X-goog-api-key"] == "test-key"
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["voice"]["name"] == "vi-VN-Wavenet-A"
        return FakeResponse({"audioContent": base64.b64encode(b"mp3-bytes").decode("ascii")})

    def fake_success(self, output_path: Path, warnings=None) -> TTSResult:
        return TTSResult(
            provider="google_cloud_tts",
            output_path=str(output_path),
            duration=1.2,
            format="mp3",
            success=True,
            warnings=warnings or [],
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(GoogleCloudTTSProvider, "_success", fake_success)

    result = GoogleCloudTTSProvider().generate(
        "Xin chao",
        str(tmp_path / "voice.wav"),
        TTSSettings(provider="google_cloud_tts", voice="vi-VN-Wavenet-A", api_key="test-key"),
    )

    assert result.output_path.endswith(".mp3")
    assert Path(result.output_path).read_bytes() == b"mp3-bytes"


def test_google_cloud_tts_lists_voices(monkeypatch):
    def fake_urlopen(request, timeout):
        assert "voices" in request.full_url
        assert "languageCode=vi-VN" in request.full_url
        assert "key=" not in request.full_url
        assert request.headers["X-goog-api-key"] == "test-key"
        return FakeResponse(
            {
                "voices": [
                    {
                        "name": "vi-VN-Wavenet-A",
                        "languageCodes": ["vi-VN"],
                        "ssmlGender": "FEMALE",
                        "naturalSampleRateHertz": 24000,
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    voices = GoogleCloudTTSProvider().list_voices(api_key="test-key", language_code="vi-VN")

    assert voices[0].name == "vi-VN-Wavenet-A"
    assert voices[0].language_codes == ["vi-VN"]


def test_google_cloud_tts_lists_voices_with_access_token(monkeypatch):
    def fake_urlopen(request, timeout):
        assert "voices" in request.full_url
        assert request.headers["Authorization"] == "Bearer access-token"
        assert "X-goog-api-key" not in request.headers
        return FakeResponse({"voices": [{"name": "vi-VN-Standard-A", "languageCodes": ["vi-VN"]}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    voices = GoogleCloudTTSProvider().list_voices(access_token="access-token", language_code="vi-VN")

    assert voices[0].name == "vi-VN-Standard-A"


def test_google_cloud_tts_reports_invalid_api_key_clearly(monkeypatch):
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(
                json.dumps(
                    {
                        "error": {
                            "code": 400,
                            "message": "API key not valid. Please pass a valid API key.",
                            "status": "INVALID_ARGUMENT",
                        }
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(TTSProviderError, match="Google Cloud TTS API rejected the key"):
        GoogleCloudTTSProvider().list_voices(api_key="invalid-key", language_code="vi-VN")

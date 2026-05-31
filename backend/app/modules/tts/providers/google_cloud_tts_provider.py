from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from pathlib import Path
from typing import Any

from app.modules.tts.providers.base import BaseTTSProvider, TTSProviderError
from app.modules.tts.tts_schema import TTSResult, TTSSettings, TTSVoiceInfo


GOOGLE_TTS_BASE_URL = "https://texttospeech.googleapis.com/v1"
GOOGLE_TTS_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class GoogleCloudTTSProvider(BaseTTSProvider):
    id = "google_cloud_tts"
    name = "Google Cloud TTS"
    online = True
    recommended = True
    requires_api_key = True
    output_format = "mp3"

    def generate(self, text: str, output_path: str, settings: TTSSettings) -> TTSResult:
        if not text.strip():
            raise TTSProviderError("Google Cloud TTS received empty text.")

        headers = _auth_headers(
            access_token=settings.access_token,
            credentials_json_path=settings.credentials_json_path,
            api_key=settings.api_key,
        )

        extension = "wav" if settings.output_format == "wav" else "mp3"
        target = self._target_path(output_path, extension)
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": _language_code(settings),
                "name": settings.voice or "vi-VN-Wavenet-A",
            },
            "audioConfig": {
                "audioEncoding": "LINEAR16" if extension == "wav" else "MP3",
                "speakingRate": _speaking_rate(settings.rate),
                "pitch": _pitch(settings.pitch),
                "volumeGainDb": _volume_gain_db(settings.volume),
            },
        }

        response = _post_json(f"{GOOGLE_TTS_BASE_URL}/text:synthesize", headers, payload)
        audio_content = response.get("audioContent")
        if not isinstance(audio_content, str) or not audio_content:
            raise TTSProviderError("Google Cloud TTS response did not contain audioContent.")

        try:
            target.write_bytes(base64.b64decode(audio_content))
        except Exception as exc:
            raise TTSProviderError(f"Could not decode Google Cloud TTS audioContent: {exc}") from exc

        return self._success(target)

    def list_voices(
        self,
        api_key: str | None = None,
        language_code: str = "vi-VN",
        credentials_json_path: str | None = None,
        access_token: str | None = None,
    ) -> list[TTSVoiceInfo]:
        headers = _auth_headers(
            access_token=access_token,
            credentials_json_path=credentials_json_path,
            api_key=api_key,
        )
        params = {"languageCode": language_code} if language_code else {}
        response = _get_json(f"{GOOGLE_TTS_BASE_URL}/voices", headers, params)
        voices = response.get("voices")
        if not isinstance(voices, list):
            raise TTSProviderError("Google Cloud TTS voices response was invalid.")

        return [
            TTSVoiceInfo(
                name=str(item.get("name") or ""),
                language_codes=[str(value) for value in item.get("languageCodes", [])],
                ssml_gender=str(item.get("ssmlGender") or ""),
                natural_sample_rate_hertz=int(item.get("naturalSampleRateHertz") or 0),
            )
            for item in voices
            if item.get("name")
        ]


def list_google_cloud_voices(
    api_key: str | None = None,
    language_code: str = "vi-VN",
    credentials_json_path: str | None = None,
    access_token: str | None = None,
) -> list[TTSVoiceInfo]:
    return GoogleCloudTTSProvider().list_voices(
        api_key=api_key,
        language_code=language_code,
        credentials_json_path=credentials_json_path,
        access_token=access_token,
    )


def _language_code(settings: TTSSettings) -> str:
    voice = (settings.voice or "").strip()
    if voice.count("-") >= 2:
        return "-".join(voice.split("-")[:2])
    language = (settings.language or "vi").strip()
    if language.lower() == "vi":
        return "vi-VN"
    return language


def _speaking_rate(value: str) -> float:
    raw = (value or "").strip()
    if raw.endswith("%"):
        try:
            return max(0.25, min(4.0, 1.0 + float(raw.rstrip("%")) / 100.0))
        except ValueError:
            return 1.0
    try:
        parsed = float(raw)
    except ValueError:
        return 1.0
    return max(0.25, min(4.0, parsed))


def _pitch(value: str) -> float:
    raw = (value or "").strip().lower().replace("st", "").replace("hz", "")
    try:
        return max(-20.0, min(20.0, float(raw)))
    except ValueError:
        return 0.0


def _volume_gain_db(value: str) -> float:
    raw = (value or "").strip().lower().replace("db", "").replace("%", "")
    try:
        parsed = float(raw)
    except ValueError:
        return 0.0
    if "%" in (value or ""):
        parsed = parsed / 10.0
    return max(-96.0, min(16.0, parsed))


def _auth_headers(
    *,
    access_token: str | None = None,
    credentials_json_path: str | None = None,
    api_key: str | None = None,
) -> dict[str, str]:
    token = _access_token(access_token, credentials_json_path)
    if token:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    key = _api_key(api_key)
    if key:
        return {"X-goog-api-key": key, "Accept": "application/json"}

    raise TTSProviderError(
        "Google Cloud TTS credentials are missing. Use a service account JSON path "
        "(GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_TTS_CREDENTIALS_JSON_PATH), "
        "an OAuth access token (GOOGLE_TTS_ACCESS_TOKEN), or a Google Cloud API key if your project allows it."
    )


def _access_token(access_token: str | None, credentials_json_path: str | None) -> str:
    direct_token = (access_token or os.getenv("GOOGLE_TTS_ACCESS_TOKEN") or "").strip()
    if direct_token:
        return direct_token

    path = (
        (credentials_json_path or "").strip()
        or os.getenv("GOOGLE_TTS_CREDENTIALS_JSON_PATH", "").strip()
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    )

    if not path:
        return ""

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:
        raise TTSProviderError("google-auth is not installed. Run `py -m pip install -r requirements.txt`.") from exc

    credential_path = Path(path).expanduser()
    if not credential_path.exists():
        raise TTSProviderError(f"Google Cloud service account JSON file does not exist: {credential_path}")

    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(credential_path),
            scopes=[GOOGLE_TTS_SCOPE],
        )
        credentials.refresh(Request())
    except Exception as exc:
        raise TTSProviderError(f"Could not load Google Cloud service account credentials: {exc}") from exc

    token = getattr(credentials, "token", None)
    if not token:
        raise TTSProviderError("Google Cloud service account did not return an access token.")
    return str(token)


def _api_key(api_key: str | None) -> str:
    return (
        (api_key or "").strip()
        or os.getenv("GOOGLE_TTS_API_KEY", "").strip()
        or os.getenv("GOOGLE_CLOUD_TTS_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
    )


def _get_json(url: str, headers: dict[str, str], params: dict[str, str] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    full_url = f"{url}?{query}" if query else url
    request = urllib.request.Request(full_url, headers=headers)
    return _read_json_response(request)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {
        **headers,
        "Content-Type": "application/json; charset=utf-8",
    }
    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method="POST",
    )
    return _read_json_response(request)


def _read_json_response(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise TTSProviderError(_google_api_error(exc.code, details)) from exc
    except urllib.error.URLError as exc:
        raise TTSProviderError(f"Google Cloud TTS request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise TTSProviderError(f"Google Cloud TTS returned invalid JSON: {exc}") from exc


def _short_error(value: str, limit: int = 500) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."


def _google_api_error(status_code: int, details: str) -> str:
    message = _extract_google_error_message(details)
    if status_code == HTTPStatus.BAD_REQUEST and "API key not valid" in message:
        return (
            "Google Cloud TTS API rejected the key: API key not valid. "
            "Cloud Text-to-Speech REST normally requires OAuth credentials. "
            "Use a service account JSON path or OAuth access token, and make sure Cloud Text-to-Speech API is enabled."
        )
    if status_code == HTTPStatus.FORBIDDEN:
        return (
            f"Google Cloud TTS API permission error: {message}. "
            "Check that billing is enabled, Cloud Text-to-Speech API is enabled, "
            "and the service account has permission to call texttospeech.googleapis.com."
        )
    return f"Google Cloud TTS API error {status_code}: {message}"


def _extract_google_error_message(details: str) -> str:
    try:
        payload = json.loads(details)
    except json.JSONDecodeError:
        return _short_error(details)

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        errors = error.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict) and isinstance(item.get("message"), str):
                    return item["message"].strip()

    return _short_error(details)

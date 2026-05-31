from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from json import JSONDecodeError
from typing import Any

from app.utils.env_loader import load_local_env


class ScriptGenerationError(RuntimeError):
    """Raised when Gemini cannot produce a valid script JSON payload."""


class GeminiAdapter:
    def __init__(
        self,
        api_key: str | None,
        model_name: str,
        timeout_seconds: float = 30.0,
        api_keys: list[str] | None = None,
        start_index: int = 0,
    ) -> None:
        load_local_env()
        self.api_keys = self._normalize_api_keys(api_keys=api_keys, api_key=api_key)
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.start_index = start_index

    def generate_json(self, prompt: str) -> dict:
        if not self.api_keys:
            raise ScriptGenerationError(
                "No Gemini API key configured. Add keys in the UI or set GEMINI_API_KEY/GEMINI_API_KEYS."
            )

        errors: list[str] = []
        for key_index, api_key in self._rotated_keys():
            try:
                response = self._request_generate_content(prompt, api_key, key_index)
                text = self._extract_text(response)
                return self._parse_json_text(text)
            except ScriptGenerationError as exc:
                errors.append(str(exc))

        raise ScriptGenerationError("All Gemini API keys failed: " + " | ".join(errors))

    def _request_generate_content(self, prompt: str, api_key: str, key_index: int) -> dict[str, Any]:
        model_path = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"{urllib.parse.quote(model_path, safe='/')}:generateContent"
            f"?key={urllib.parse.quote(api_key)}"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.9,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="replace")
                last_error = ScriptGenerationError(f"Gemini key #{key_index} HTTP {exc.code}: {details}")
                if exc.code < 500 and exc.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, JSONDecodeError) as exc:
                last_error = ScriptGenerationError(f"Gemini key #{key_index} request error: {exc}")

            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))

        raise ScriptGenerationError(f"Gemini key #{key_index} request failed: {last_error}") from last_error

    def _rotated_keys(self) -> list[tuple[int, str]]:
        total = len(self.api_keys)
        if total == 0:
            return []
        start = self.start_index % total
        ordered_indexes = list(range(start, total)) + list(range(0, start))
        return [(index + 1, self.api_keys[index]) for index in ordered_indexes]

    @staticmethod
    def _normalize_api_keys(api_keys: list[str] | None, api_key: str | None) -> list[str]:
        candidates: list[str] = []
        if api_keys:
            candidates.extend(api_keys)
        if api_key:
            candidates.append(api_key)
        env_many = os.getenv("GEMINI_API_KEYS")
        if env_many:
            candidates.extend(part for part in env_many.replace(";", "\n").replace(",", "\n").splitlines())
        env_one = os.getenv("GEMINI_API_KEY")
        if env_one:
            candidates.append(env_one)

        seen: set[str] = set()
        normalized: list[str] = []
        for candidate in candidates:
            key = candidate.strip()
            if not key or key in seen:
                continue
            normalized.append(key)
            seen.add(key)
        return normalized

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        try:
            parts = response["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ScriptGenerationError(f"Gemini response has no text candidate: {response}") from exc

        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        text = "\n".join(part for part in text_parts if part).strip()
        if not text:
            raise ScriptGenerationError(f"Gemini returned an empty text response: {response}")
        return text

    def _parse_json_text(self, text: str) -> dict:
        cleaned = self._strip_markdown_fence(text)
        try:
            parsed = json.loads(cleaned)
        except JSONDecodeError:
            extracted = self._extract_json_object(cleaned)
            try:
                parsed = json.loads(extracted)
            except JSONDecodeError as exc:
                raise ScriptGenerationError(f"Gemini response is not valid JSON: {text}") from exc

        if not isinstance(parsed, dict):
            raise ScriptGenerationError("Gemini JSON response must be an object.")
        return parsed

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_json_object(text: str) -> str:
        start = text.find("{")
        if start < 0:
            raise ScriptGenerationError("No JSON object found in Gemini response.")

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]

        raise ScriptGenerationError("JSON object in Gemini response is incomplete.")

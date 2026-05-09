"""Gemini provider adapter (US-#221).

Wraps `google.generativeai` so the router only sees the normalized
provider exceptions. Per-process model cache keyed by model id — the
SDK initializes lazily so we don't pay it on import.
"""

from __future__ import annotations

import asyncio
import re
import time

import google.generativeai as genai

import config

from .base import (
    AiResult,
    ProviderFatalError,
    ProviderRateLimit,
    ProviderTransientError,
)


_models: dict[str, "genai.GenerativeModel"] = {}
_configured = False


def _get_model(model: str) -> "genai.GenerativeModel":
    global _configured
    if not _configured:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _configured = True
    if model not in _models:
        _models[model] = genai.GenerativeModel(model)
    return _models[model]


def _parse_retry_after(error_str: str) -> int:
    """Best-effort extraction of `retry_delay { seconds: N }` from Gemini 429 prose."""
    match = re.search(r"retry.*?(\d+)", error_str)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return 60


class GeminiProvider:
    """`AiProvider` impl backed by Google's `google-generativeai` SDK."""

    name = "gemini"

    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        timeout_s: float = 30.0,
    ) -> AiResult:
        if not config.GEMINI_API_KEY:
            raise ProviderFatalError(self.name, model, "GEMINI_API_KEY not set")

        m = _get_model(model)
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(m.generate_content, prompt),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTransientError(self.name, model, "timeout") from exc
        except Exception as exc:  # noqa: BLE001 — translate at adapter edge
            error_str = str(exc)
            if "429" in error_str or "quota" in error_str.lower():
                retry_after = _parse_retry_after(error_str)
                raise ProviderRateLimit(self.name, model, retry_after) from exc
            # Auth + bad-request prose Gemini raises is varied; the safe
            # default for an *unknown* exception class is "transient" —
            # prevents one weird error from killing the whole chain.
            # Programmer errors (e.g. missing API key) are caught above.
            raise ProviderTransientError(self.name, model, error_str[:200]) from exc

        text = (getattr(response, "text", "") or "").strip()
        usage = getattr(response, "usage_metadata", None)
        prompt_tok = getattr(usage, "prompt_token_count", None) if usage else None
        completion_tok = (
            getattr(usage, "candidates_token_count", None) if usage else None
        )
        return AiResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=int((time.monotonic() - t0) * 1000),
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
        )

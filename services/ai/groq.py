"""Groq provider adapter (US-#221).

Talks to Groq via its OpenAI-compatible endpoint
(`https://api.groq.com/openai/v1`) using the `openai` Python SDK. This
lets us add Cerebras / OpenRouter / paid Gemini-via-OpenRouter behind
the same client class later — one adapter class for N providers.

Free-tier headroom we're targeting (per Groq's published limits):
  * llama-3.3-70b-versatile  — 30 RPM, 1,000 RPD  (premium tier model)
  * llama-3.1-8b-instant     — 30 RPM, 14,400 RPD (cheap tier model)
  * gemma2-9b-it             — 30 RPM, 14,400 RPD (cheap fallback)
"""

from __future__ import annotations

import asyncio
import time

import config

from .base import (
    AiResult,
    ProviderFatalError,
    ProviderRateLimit,
    ProviderTransientError,
)


_client = None


def _get_client():
    """Lazy-init the AsyncOpenAI client pointed at Groq.

    Keeping the import lazy means non-AI code paths don't pull `openai`
    just to import `services.ai`, and tests with a fake provider don't
    need a real key on disk.
    """
    global _client
    if _client is None:
        from openai import AsyncOpenAI  # local import: optional dep

        if not config.GROQ_API_KEY:
            raise ProviderFatalError("groq", "?", "GROQ_API_KEY not set")
        _client = AsyncOpenAI(
            api_key=config.GROQ_API_KEY,
            base_url=config.GROQ_BASE_URL,
        )
    return _client


class GroqProvider:
    """`AiProvider` impl backed by Groq's OpenAI-compatible API."""

    name = "groq"

    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        timeout_s: float = 30.0,
    ) -> AiResult:
        client = _get_client()  # raises ProviderFatalError if no key
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    # Default 0 temperature — the IELTS use cases (vocab,
                    # quiz, grading) all want deterministic output. The
                    # Gemini wrapper had no temperature override either,
                    # so this matches behaviour.
                    temperature=0.0,
                ),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderTransientError(self.name, model, "timeout") from exc
        except Exception as exc:  # noqa: BLE001 — translate at adapter edge
            # OpenAI SDK exceptions: APIStatusError carries .status_code.
            # We avoid a hard import dependency on the exception class
            # so this adapter can be unit-tested without `openai` installed.
            status = getattr(exc, "status_code", None) or getattr(
                exc, "http_status", None,
            )
            if status == 429:
                retry_after = _retry_after_from_exception(exc)
                raise ProviderRateLimit(
                    self.name, model, retry_after,
                ) from exc
            if status in (401, 403):
                raise ProviderFatalError(
                    self.name, model, f"auth_error_{status}",
                ) from exc
            if status == 400:
                raise ProviderFatalError(
                    self.name, model, "bad_request",
                ) from exc
            # Everything else (5xx, connection errors, unknown) → transient.
            raise ProviderTransientError(
                self.name, model, str(exc)[:200],
            ) from exc

        choice = response.choices[0] if response.choices else None
        text = (choice.message.content if choice else "") or ""
        text = text.strip()
        usage = getattr(response, "usage", None)
        prompt_tok = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tok = (
            getattr(usage, "completion_tokens", None) if usage else None
        )
        return AiResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=int((time.monotonic() - t0) * 1000),
            prompt_tokens=prompt_tok,
            completion_tokens=completion_tok,
        )


def _retry_after_from_exception(exc: Exception) -> int:
    """Best-effort extraction of `Retry-After` from OpenAI SDK errors."""
    headers = getattr(exc, "response", None)
    if headers is not None:
        try:
            value = headers.headers.get("retry-after") or headers.headers.get(
                "Retry-After",
            )
            if value:
                return int(float(value))
        except (AttributeError, TypeError, ValueError):
            pass
    return 60

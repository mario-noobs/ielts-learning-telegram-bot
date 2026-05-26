"""Multi-provider router + orchestrator (US-#221).

Public API mirrors the legacy `services.ai_service` shape so callers
don't break:

    text = await router.generate(prompt, plan="personal_pro", quality="premium")
    obj  = await router.generate_json(prompt, plan="free", quality="cheap")

Resolution flow:
  1. Each hop in a plan's chain may carry an optional `tier` tag. A
     hop with `tier="premium"` is only walked when the caller asks
     for `quality="premium"`. Untagged hops (default) are walked at
     both quality levels. This is what implements "one knob per tier"
     (PO direction): Pro chain tags 70B as premium so a Pro user's
     `quality="cheap"` call (vocab/quiz/listening) skips it and goes
     to 8B, while their `quality="premium"` call (writing/coaching/
     paraphrase) starts on 70B. Free chain has NO premium hops, so
     both quality levels walk the same hops in order — Free is
     locked to cheap regardless of `quality=`.
  2. Walk the eligible hops in order. On `ProviderRateLimit` /
     `ProviderTransientError` → fall forward. On `ProviderFatalError`
     → bubble immediately (programmer / config bug, not a vendor
     hiccup).
  3. Every chain exhausted → raise `RouterAllProvidersFailed`. The
     legacy `services.ai_service` facade re-raises that as
     `RateLimitError` for backwards compat with existing 429 handling.
"""

from __future__ import annotations

import json
import logging
from typing import Literal, Optional

from services.ai import config as routing_config
from services.ai.base import (
    AiProvider,
    AiResult,
    ProviderFatalError,
    ProviderRateLimit,
    ProviderTransientError,
)
from services.ai.gemini import GeminiProvider
from services.ai.groq import GroqProvider

logger = logging.getLogger(__name__)


Quality = Literal["cheap", "premium"]


_PROVIDERS: dict[str, AiProvider] = {
    "gemini": GeminiProvider(),
    "groq": GroqProvider(),
}


class RouterAllProvidersFailed(Exception):
    """Every hop in the chain failed. Caller should surface a 503."""

    def __init__(self, plan: str, attempts: list[str]) -> None:
        self.plan = plan
        self.attempts = attempts
        super().__init__(
            f"All providers failed for plan={plan}; tried {attempts}"
        )


def _get_provider(name: str) -> AiProvider:
    if name not in _PROVIDERS:
        raise ProviderFatalError(name, "?", f"unknown provider {name!r}")
    return _PROVIDERS[name]


def _is_missing_config(exc: ProviderFatalError) -> bool:
    return "not set" in exc.cause.lower()


def register_provider(name: str, provider: AiProvider) -> None:
    """Test seam — `tests/fakes/fake_provider.py` registers a stub here.

    Production code should never call this. The router otherwise has
    no DI hook; tests would have to monkey-patch `_PROVIDERS` directly,
    which is brittle.
    """
    _PROVIDERS[name] = provider


def _eligible_hops(chain: list[dict], quality: Quality) -> list[int]:
    """Indexes (in chain order) the router will try for this `quality`.

    Hops carry an optional `tier` field:
      * Untagged / `tier == "cheap"` → eligible at both quality levels.
      * `tier == "premium"`         → only eligible when quality=premium.

    Defensive: if `quality="cheap"` would result in zero eligible hops
    (e.g. an admin tagged every hop premium), fall back to walking the
    full chain — better to serve from a premium-tagged hop than to
    return 503 to a cheap caller.
    """
    indexes = [
        i for i, hop in enumerate(chain)
        if not (quality == "cheap" and hop.get("tier") == "premium")
    ]
    if not indexes:
        return list(range(len(chain)))
    return indexes


async def _walk_chain(
    prompt: str,
    chain: list[dict],
    eligible: list[int],
    plan: str,
) -> AiResult:
    attempts: list[str] = []
    for i in eligible:
        hop = chain[i]
        provider_name = hop.get("provider", "")
        model = hop.get("model", "")
        if not provider_name or not model:
            logger.warning("ai.router: malformed hop %r in chain — skipping", hop)
            continue
        attempts.append(f"{provider_name}/{model}")
        try:
            provider = _get_provider(provider_name)
            result = await provider.generate(prompt, model=model)
            logger.info(
                "ai.router served plan=%s hop=%d provider=%s model=%s latency=%dms",
                plan, i, provider_name, model, result.latency_ms,
            )
            return result
        except ProviderFatalError as exc:
            if _is_missing_config(exc):
                logger.warning(
                    "ai.router missing config plan=%s hop=%d provider=%s model=%s: %s",
                    plan, i, provider_name, model, exc.cause,
                )
                continue
            # Auth / bad request — bubble. Falling forward would mask a bug.
            logger.error(
                "ai.router fatal plan=%s hop=%d provider=%s model=%s: %s",
                plan, i, provider_name, model, exc.cause,
            )
            raise
        except (ProviderRateLimit, ProviderTransientError) as exc:
            logger.warning(
                "ai.router fall-forward plan=%s hop=%d provider=%s model=%s: %s",
                plan, i, provider_name, model, exc,
            )
            continue

    raise RouterAllProvidersFailed(plan, attempts)


async def generate(
    prompt: str,
    *,
    plan: Optional[str] = None,
    quality: Quality = "cheap",
) -> str:
    """Send `prompt` and return the text. Walks the plan's chain on failure."""
    chain = routing_config.get_chain(plan)
    if not chain:
        raise RouterAllProvidersFailed(plan or "free", [])
    eligible = _eligible_hops(chain, quality)
    result = await _walk_chain(prompt, chain, eligible, plan or "free")
    return result.text


async def generate_json(
    prompt: str,
    *,
    plan: Optional[str] = None,
    quality: Quality = "cheap",
):
    """`generate` + JSON parsing. Strips ```json fences first.

    Re-uses the same fence-stripping the legacy `ai_service.generate_json`
    had — Llama and Gemini both wrap JSON in code fences sometimes.
    """
    text = await generate(prompt, plan=plan, quality=quality)
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)

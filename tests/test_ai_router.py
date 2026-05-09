"""Multi-provider AI router tests (US-#221).

Covers AC17 router scenarios. Uses ``FakeProvider`` so the suite runs
without GROQ_API_KEY / GEMINI_API_KEY env. Patches the routing-config
loader to return a deterministic chain instead of hitting Postgres.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.ai import router
from services.ai.base import (
    ProviderFatalError,
    ProviderRateLimit,
    ProviderTransientError,
)
from tests.fakes.fake_provider import FakeProvider


@pytest.fixture
def fake_groq():
    return FakeProvider(name="groq")


@pytest.fixture
def fake_gemini():
    return FakeProvider(name="gemini")


@pytest.fixture(autouse=True)
def _swap_providers(fake_groq, fake_gemini):
    """Replace the real groq + gemini singletons in the router for every test."""
    router.register_provider("groq", fake_groq)
    router.register_provider("gemini", fake_gemini)
    yield
    # Re-register the real providers so other test files aren't poisoned.
    from services.ai.gemini import GeminiProvider
    from services.ai.groq import GroqProvider
    router.register_provider("groq", GroqProvider())
    router.register_provider("gemini", GeminiProvider())


def _stub_chain(chain: list[dict]):
    """Patch get_chain so the router sees the chain we want, regardless of plan."""
    return patch(
        "services.ai.router.routing_config.get_chain", return_value=chain,
    )


@pytest.mark.asyncio
async def test_premium_starts_at_first_hop(fake_groq):
    """Quality=premium → chain index 0 (the premium model)."""
    fake_groq.behaviours = {
        "llama-3.3-70b-versatile": "premium-result",
        "llama-3.1-8b-instant": "cheap-result",
    }
    chain = [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
    ]
    with _stub_chain(chain):
        text = await router.generate("p", plan="personal_pro", quality="premium")
    assert text == "premium-result"
    # Only the premium hop was hit — no fall-forward.
    assert [c[0] for c in fake_groq.calls] == ["llama-3.3-70b-versatile"]


@pytest.mark.asyncio
async def test_cheap_skips_premium_hop(fake_groq):
    """Quality=cheap → chain index 1 (skips the expensive model entirely)."""
    fake_groq.behaviours = {
        "llama-3.3-70b-versatile": "should-not-call",
        "llama-3.1-8b-instant": "cheap-result",
    }
    chain = [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
    ]
    with _stub_chain(chain):
        text = await router.generate("p", plan="free", quality="cheap")
    assert text == "cheap-result"
    assert [c[0] for c in fake_groq.calls] == ["llama-3.1-8b-instant"]


@pytest.mark.asyncio
async def test_fallback_on_rate_limit(fake_groq, fake_gemini):
    """Premium hop returns 429 → router falls forward to next hop."""
    fake_groq.behaviours = {
        "llama-3.3-70b-versatile": ProviderRateLimit(
            "groq", "llama-3.3-70b-versatile", 5,
        ),
        "llama-3.1-8b-instant": "fallback-served",
    }
    chain = [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ]
    with _stub_chain(chain):
        text = await router.generate("p", plan="personal_pro", quality="premium")
    assert text == "fallback-served"
    # Both Groq hops attempted; Gemini never reached.
    assert [c[0] for c in fake_groq.calls] == [
        "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
    ]
    assert fake_gemini.calls == []


@pytest.mark.asyncio
async def test_fatal_error_bubbles(fake_groq, fake_gemini):
    """Programmer/config error must NOT be swallowed by fallback."""
    fake_groq.behaviours = {
        "llama-3.3-70b-versatile": ProviderFatalError(
            "groq", "llama-3.3-70b-versatile", "GROQ_API_KEY not set",
        ),
    }
    chain = [
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ]
    with _stub_chain(chain), pytest.raises(ProviderFatalError):
        await router.generate("p", plan="personal_pro", quality="premium")
    # Gemini fallback NOT attempted — fatal must bubble immediately.
    assert fake_gemini.calls == []


@pytest.mark.asyncio
async def test_all_providers_failed_raises(fake_groq, fake_gemini):
    """Whole chain exhausted via transient/rate-limit → RouterAllProvidersFailed."""
    fake_groq.behaviours = {
        "llama-3.1-8b-instant": ProviderTransientError(
            "groq", "llama-3.1-8b-instant", "5xx",
        ),
        "gemma2-9b-it": ProviderRateLimit("groq", "gemma2-9b-it", 60),
    }
    fake_gemini.behaviours = {
        "gemini-2.5-flash-lite": ProviderRateLimit(
            "gemini", "gemini-2.5-flash-lite", 60,
        ),
    }
    chain = [
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "groq", "model": "gemma2-9b-it"},
        {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    ]
    with _stub_chain(chain), pytest.raises(router.RouterAllProvidersFailed) as exc:
        await router.generate("p", plan="free", quality="cheap")
    assert exc.value.attempts == [
        # cheap starts at hop 1 (index 1) for a 3-hop chain
        "groq/gemma2-9b-it",
        "gemini/gemini-2.5-flash-lite",
    ]


@pytest.mark.asyncio
async def test_facade_translates_router_exhaustion_to_rate_limit_error(fake_groq):
    """services.ai_service preserves backwards-compat RateLimitError contract."""
    from services.ai_service import RateLimitError, generate

    fake_groq.behaviours = {
        "llama-3.1-8b-instant": ProviderRateLimit(
            "groq", "llama-3.1-8b-instant", 60,
        ),
    }
    chain = [
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
    ]
    with _stub_chain(chain), pytest.raises(RateLimitError):
        await generate("p", plan="free", quality="cheap")

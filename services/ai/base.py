"""Provider Protocol + shared types (US-#221).

Each provider adapter raises one of three normalized exceptions so the
router can decide whether to fall forward (rate-limit / transient) or
bubble up immediately (fatal — auth, malformed prompt, programmer
error). Provider-specific errors get translated at the adapter edge —
nothing outside the adapter should `except google.api_core...`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class AiResult:
    """Result of a single successful provider call.

    `provider` + `model` are echoed back so the orchestrator can log
    *which* hop served the request — load-bearing for the AC12 telemetry
    and the admin dashboard's "served by" view.
    """

    text: str
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


class ProviderRateLimit(Exception):
    """Provider returned 429 / over-quota. Router falls forward."""

    def __init__(self, provider: str, model: str, retry_after: int = 0) -> None:
        self.provider = provider
        self.model = model
        self.retry_after = retry_after
        super().__init__(
            f"{provider}/{model}: rate-limited (retry after {retry_after}s)"
        )


class ProviderTransientError(Exception):
    """Provider returned 5xx / timeout / connection error. Router falls forward."""

    def __init__(self, provider: str, model: str, cause: str) -> None:
        self.provider = provider
        self.model = model
        self.cause = cause
        super().__init__(f"{provider}/{model}: transient — {cause}")


class ProviderFatalError(Exception):
    """Auth, malformed prompt, content filter, etc. Router bubbles."""

    def __init__(self, provider: str, model: str, cause: str) -> None:
        self.provider = provider
        self.model = model
        self.cause = cause
        super().__init__(f"{provider}/{model}: fatal — {cause}")


class AiProvider(Protocol):
    """All providers (Gemini, Groq, future Cerebras) share this surface."""

    name: str  # "gemini" | "groq" | "cerebras"

    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        timeout_s: float = 30.0,
    ) -> AiResult:
        """Send `prompt`, return the text + per-call metadata.

        Raises one of `ProviderRateLimit`, `ProviderTransientError`,
        `ProviderFatalError`. Never raises a provider-native exception.
        """
        ...

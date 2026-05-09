"""Test seam — registered into the router via `register_provider()`.

Provides deterministic responses keyed by model id and exposes a call
log so tests can assert which hops were tried in what order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Union

from services.ai.base import (
    AiResult,
    ProviderFatalError,
    ProviderRateLimit,
    ProviderTransientError,
)


# A "behaviour" is either a string (success — returns it as the AI text)
# or an exception type/instance (raised when this model is called).
ModelBehaviour = Union[str, Exception]


@dataclass
class FakeProvider:
    """`AiProvider` impl that returns canned responses or raises on demand.

    Usage in tests:

        fake = FakeProvider(
            name="groq",
            behaviours={
                "llama-3.3-70b-versatile": ProviderRateLimit("groq", "...", 5),
                "llama-3.1-8b-instant": "{\"score\": 7}",
            },
        )
        register_provider("groq", fake)

    `calls` records every (model, prompt) tuple the router invoked, so
    fallback behaviour is observable.
    """

    name: str = "fake"
    behaviours: dict[str, ModelBehaviour] = field(default_factory=dict)
    default: Optional[ModelBehaviour] = "ok"
    calls: list[tuple[str, str]] = field(default_factory=list)
    latency_ms: int = 5

    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        timeout_s: float = 30.0,
    ) -> AiResult:
        self.calls.append((model, prompt))
        behaviour: ModelBehaviour
        if model in self.behaviours:
            behaviour = self.behaviours[model]
        elif self.default is not None:
            behaviour = self.default
        else:
            raise ProviderFatalError(self.name, model, "no behaviour configured")

        if isinstance(behaviour, Exception):
            raise behaviour
        if isinstance(behaviour, type) and issubclass(behaviour, Exception):
            # Class given without instance args — instantiate with sensible default.
            raise behaviour(self.name, model, "fake-error")
        if callable(behaviour):
            text = behaviour(prompt)
        else:
            text = str(behaviour)
        return AiResult(
            text=text,
            provider=self.name,
            model=model,
            latency_ms=self.latency_ms,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(text.split()),
        )


__all__ = [
    "FakeProvider",
    "ProviderFatalError",
    "ProviderRateLimit",
    "ProviderTransientError",
]

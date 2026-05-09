"""Multi-provider AI router (US-#221).

The package replaces the single-provider Gemini wrapper at
``services.ai_service`` with an orchestrator that walks a chain of
``(provider, model)`` hops resolved per user plan.

Public surface — most callers should keep using ``services.ai_service``,
which now delegates here. Direct imports from this package are reserved
for the router/admin code:

    from services.ai.base import AiResult, ProviderRateLimit
    from services.ai.router import generate, generate_json
"""

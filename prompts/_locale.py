"""Locale-aware prompt template resolver (US-M7.4, #129).

The resolver lets services pick the right template for a locale without
sprinkling `if locale == 'vi'` branches throughout the codebase. By
convention:

    prompts/writing_score_prompt.py         → default / EN
    prompts/writing_score_prompt_vi.py      → VN sibling

Both modules expose the same set of module-level constants (typically
`PROMPT_NAME = "…"`), so `get_prompt(module, "PROMPT_NAME", locale)`
works for either locale.

If no sibling exists for the requested locale, the resolver falls back
to the default module and logs a warning — the AI will still generate
output, just in the default locale's style. This keeps the rollout
incremental: a prompt that hasn't been translated yet doesn't break
anything, it just doesn't change.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "vi")


def _sibling_module_name(base: str, locale: str) -> str:
    if locale == DEFAULT_LOCALE:
        return f"prompts.{base}"
    return f"prompts.{base}_{locale}"


def get_prompt(module: str, name: str, locale: str = DEFAULT_LOCALE) -> str:
    """Return the prompt constant for a (module, name, locale) triple.

    Example:
        tmpl = get_prompt("writing_score_prompt", "IELTS_SCORING_PROMPT", "vi")
    """
    if locale not in SUPPORTED_LOCALES:
        logger.warning("prompts: unsupported locale %r, falling back to %s",
                       locale, DEFAULT_LOCALE)
        locale = DEFAULT_LOCALE

    primary = _sibling_module_name(module, locale)
    try:
        mod = importlib.import_module(primary)
    except ModuleNotFoundError:
        if locale == DEFAULT_LOCALE:
            raise
        logger.info("prompts: no %s sibling for %s; falling back to %s",
                    locale, module, DEFAULT_LOCALE)
        mod = importlib.import_module(_sibling_module_name(module, DEFAULT_LOCALE))

    try:
        return getattr(mod, name)
    except AttributeError as exc:
        raise AttributeError(
            f"prompt constant {name!r} missing from {mod.__name__}"
        ) from exc


def has_sibling(module: str, locale: str) -> bool:
    """True if `prompts/{module}_{locale}.py` exists."""
    if locale == DEFAULT_LOCALE:
        return True
    try:
        importlib.import_module(_sibling_module_name(module, locale))
        return True
    except ModuleNotFoundError:
        return False


__all__ = ["DEFAULT_LOCALE", "SUPPORTED_LOCALES", "get_prompt", "has_sibling"]

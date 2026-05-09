"""Legacy AI facade — delegates to ``services.ai.router`` (US-#221).

History: this module used to be a single-provider Gemini wrapper. It
now keeps the same public surface (high-level helpers like
``generate_vocabulary``, ``enrich_word``, ``score_essay``) but routes
every request through the multi-provider chain in ``services.ai``.

Why keep the facade:
  * 12+ call sites (vocab, quiz, writing, listening, reading, coaching,
    plan, weakness, word, progress, plus bot handlers) import from here.
    Changing them all in one PR multiplies blast radius.
  * The high-level helpers (``generate_quiz``, ``evaluate_paraphrase``)
    encode prompt-template lookup. That's not router-layer concern.
  * ``RateLimitError`` is part of the API error contract — every caller
    knows how to surface it. Translating it from the new
    ``RouterAllProvidersFailed`` keeps that contract intact.

What changed:
  * No more direct ``google.generativeai`` import (that lives in
    ``services.ai.gemini``).
  * No more ``GeminiGate``: the router walks a chain, so an RPM cap on
    one provider just falls forward instead of blocking.
  * New optional kwarg ``quality='cheap'|'premium'`` and ``plan=...``
    on ``generate`` / ``generate_json``. Default ``cheap`` so existing
    callers don't pay the premium chain budget.
"""

from __future__ import annotations

import logging
from typing import Optional

from services.ai import router as _router
from services.ai.router import RouterAllProvidersFailed

logger = logging.getLogger(__name__)


# Backwards-compat exception. The router raises
# ``RouterAllProvidersFailed`` when every hop is exhausted; we re-export
# ``RateLimitError`` so existing 429-handling code paths keep working.
class RateLimitError(Exception):
    """Raised when every provider in the chain returned 429 / unavailable.

    Kept for backwards compat with ``services.ai_service.RateLimitError``
    references in routes + bot handlers.
    """

    def __init__(self, limit_type: str = "all_providers", retry_after: int = 60) -> None:
        self.limit_type = limit_type
        self.retry_after = retry_after
        super().__init__(
            f"Rate limited: {limit_type}. Retry after {retry_after}s"
        )


class BackgroundDisabled(RuntimeError):
    """Legacy export — no longer raised by the router. Kept so the bot's
    ``except BackgroundDisabled`` paths don't break on import."""


# ─── Core delegation ───────────────────────────────────────────────────


async def generate(
    prompt: str,
    max_retries: int = 2,  # accepted for backwards compat; router does its own
    priority: str = "foreground",  # legacy hint, ignored by router
    *,
    plan: Optional[str] = None,
    quality: str = "cheap",
) -> str:
    """Send a prompt to the router. Returns the response text.

    Args:
        prompt: prompt text.
        plan: caller's plan id (e.g. ``personal_pro``). Defaults to ``free``
            chain when None.
        quality: ``"cheap"`` (default) or ``"premium"`` — premium starts
            at chain hop 0 (typically Llama 3.3 70B); cheap starts at
            hop 1 (typically Llama 3.1 8B).
        max_retries / priority: legacy kwargs, accepted but unused.
    """
    try:
        return await _router.generate(prompt, plan=plan, quality=quality)
    except RouterAllProvidersFailed as exc:
        logger.error("ai.router exhausted: plan=%s attempts=%s", exc.plan, exc.attempts)
        raise RateLimitError("all_providers", 60) from exc


async def generate_json(
    prompt: str,
    max_retries: int = 3,  # accepted for backwards compat
    priority: str = "foreground",  # legacy hint
    *,
    plan: Optional[str] = None,
    quality: str = "cheap",
):
    """``generate`` + JSON parse. See ``generate`` for kwargs."""
    try:
        return await _router.generate_json(prompt, plan=plan, quality=quality)
    except RouterAllProvidersFailed as exc:
        logger.error("ai.router exhausted: plan=%s attempts=%s", exc.plan, exc.attempts)
        raise RateLimitError("all_providers", 60) from exc


# ─── Vocabulary ────────────────────────────────────────────────────────


async def generate_vocabulary(
    count: int, band: float, topic: str, exclude_words: list = None,
    *, plan: Optional[str] = None,
) -> list[dict]:
    from prompts.vocab_prompt import GENERATE_VOCABULARY

    exclude_clause = ""
    if exclude_words:
        exclude_clause = (
            f"\nDo NOT include these words (already learned): "
            f"{', '.join(exclude_words[:100])}"
        )
    prompt = GENERATE_VOCABULARY.format(
        count=count, band=band, topic=topic, exclude_clause=exclude_clause,
    )
    return await generate_json(prompt, plan=plan, quality="cheap")


async def enrich_word(
    word: str, band: float, priority: str = "foreground",
    *, plan: Optional[str] = None,
) -> dict:
    from prompts.word_enrichment_prompt import ENRICH_WORD
    prompt = ENRICH_WORD.format(word=word, band=band)
    return await generate_json(prompt, priority=priority, plan=plan, quality="cheap")


async def generate_band_example(
    word: str, part_of_speech: str, definition_en: str, band: float,
    priority: str = "foreground",
    *, plan: Optional[str] = None,
) -> dict:
    from prompts.word_enrichment_prompt import ENRICH_WORD_EXAMPLE
    prompt = ENRICH_WORD_EXAMPLE.format(
        word=word, part_of_speech=part_of_speech,
        definition_en=definition_en, band=band,
    )
    return await generate_json(prompt, priority=priority, plan=plan, quality="cheap")


async def explain_word(word: str, band: float, *, plan: Optional[str] = None) -> str:
    from prompts.vocab_prompt import EXPLAIN_WORD
    prompt = EXPLAIN_WORD.format(word=word, band=band)
    return await generate(prompt, plan=plan, quality="cheap")


# ─── Quiz ──────────────────────────────────────────────────────────────


async def generate_quiz(
    word: str, definition: str, quiz_type: str,
    *, plan: Optional[str] = None,
) -> dict:
    from prompts.quiz_prompt import (
        GENERATE_FILL_BLANK,
        GENERATE_MULTIPLE_CHOICE,
        GENERATE_PARAPHRASE,
        GENERATE_SYNONYM_ANTONYM,
    )

    prompt_map = {
        "multiple_choice": GENERATE_MULTIPLE_CHOICE,
        "fill_blank": GENERATE_FILL_BLANK,
        "synonym_antonym": GENERATE_SYNONYM_ANTONYM,
        "paraphrase": GENERATE_PARAPHRASE,
    }
    template = prompt_map[quiz_type]
    prompt = template.format(
        word=word, definition=definition,
        first_letter=word[0].upper() if word else "?",
    )
    result = await generate_json(prompt, plan=plan, quality="cheap")
    result["type"] = quiz_type
    result["word"] = word
    return result


async def generate_quiz_batch(
    words: list[dict], types: list[str],
    *, plan: Optional[str] = None,
) -> list[dict]:
    from prompts.quiz_prompt import GENERATE_QUIZ_BATCH

    words_list = "\n".join(
        f'{i+1}. "{w["word"]}" = "{w.get("definition", "")}"'
        for i, w in enumerate(words)
    )
    types_list = ", ".join(types)
    prompt = GENERATE_QUIZ_BATCH.format(
        words_list=words_list, types_list=types_list, count=len(words),
    )
    results = await generate_json(prompt, plan=plan, quality="cheap")
    for i, result in enumerate(results):
        if i < len(types):
            result["type"] = types[i]
        if i < len(words):
            result["word"] = words[i]["word"]
            if "word_id" in words[i]:
                result["word_id"] = words[i]["word_id"]
    return results


async def generate_challenge(
    count: int, band: float, topic: str,
    *, plan: Optional[str] = None,
) -> list:
    from prompts.quiz_prompt import GENERATE_CHALLENGE
    prompt = GENERATE_CHALLENGE.format(count=count, band=band, topic=topic)
    return await generate_json(prompt, plan=plan, quality="cheap")


async def evaluate_paraphrase(
    original: str, word: str, student_answer: str, sample_answer: str,
    *, plan: Optional[str] = None,
) -> dict:
    """Premium call site: scoring a free-form paraphrase needs reasoning."""
    from prompts.quiz_prompt import EVALUATE_PARAPHRASE
    prompt = EVALUATE_PARAPHRASE.format(
        original=original, word=word,
        student_answer=student_answer, sample_answer=sample_answer,
    )
    return await generate_json(prompt, plan=plan, quality="premium")


# ─── Writing ───────────────────────────────────────────────────────────


async def get_writing_feedback(
    text: str, band: float, *, plan: Optional[str] = None,
) -> str:
    """Premium call site: writing feedback drives Pro's value prop."""
    from prompts.writing_prompt import WRITING_FEEDBACK, WRITING_FEEDBACK_SHORT
    template = WRITING_FEEDBACK if len(text) > 100 else WRITING_FEEDBACK_SHORT
    prompt = template.format(text=text, band=band)
    return await generate(prompt, plan=plan, quality="premium")


# ─── Translation ───────────────────────────────────────────────────────


async def translate_text(
    text: str, band: float, *, plan: Optional[str] = None,
) -> str:
    from prompts.translate_prompt import (
        DETECT_LANGUAGE,
        TRANSLATE_EN_TO_VI,
        TRANSLATE_VI_TO_EN,
    )

    lang_prompt = DETECT_LANGUAGE.format(text=text)
    lang = (await generate(lang_prompt, plan=plan, quality="cheap")).strip().lower()

    if lang == "vi":
        prompt = TRANSLATE_VI_TO_EN.format(text=text, band=band)
    else:
        prompt = TRANSLATE_EN_TO_VI.format(text=text, band=band)
    return await generate(prompt, plan=plan, quality="cheap")

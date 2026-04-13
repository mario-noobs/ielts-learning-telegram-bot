import asyncio
import logging

import config
from services import ai_service, firebase_service
from services.ai_service import RateLimitError, BackgroundDisabled

logger = logging.getLogger(__name__)


def normalize_word(raw: str) -> str:
    """Lowercase and strip whitespace."""
    return raw.strip().lower()


def band_tier(band: float) -> str:
    """Map band score to tier bucket.

    5.0-5.5 -> '5', 6.0-6.5 -> '6', 7.0-7.5 -> '7', 8.0+ -> '8'.
    """
    if band >= 8.0:
        return "8"
    elif band >= 7.0:
        return "7"
    elif band >= 6.0:
        return "6"
    else:
        return "5"


async def get_enriched_word(word: str, band: float,
                           priority: str = "foreground") -> dict:
    """Look up or generate enriched word data.

    Flow:
    1. Normalize word, compute band tier.
    2. Check Firestore cache.
    3a. Cache miss: full Gemini call, save to cache, return.
    3b. Cache hit but missing band tier example: lightweight Gemini call,
        update cache with new example, return.
    3c. Full cache hit: return cached data as-is.

    Args:
        word: The word to enrich.
        band: IELTS band score for example generation.
        priority: "foreground" or "background" — passed to ai_service
            to control Gemini rate-gate behavior.
    """
    normalized = normalize_word(word)
    tier = band_tier(band)

    cached = firebase_service.get_enriched_word_doc(normalized)

    if cached is None:
        logger.info("Word cache MISS: %s (band %s, priority %s)", normalized, tier, priority)
        # Cache miss — full enrichment
        result = await ai_service.enrich_word(normalized, band, priority=priority)

        # Structure into cache schema
        data = {
            "word": result.get("word", normalized),
            "ipa": result.get("ipa", ""),
            "syllable_stress": result.get("syllable_stress", ""),
            "part_of_speech": result.get("part_of_speech", ""),
            "definition_en": result.get("definition_en", ""),
            "definition_vi": result.get("definition_vi", ""),
            "word_family": result.get("word_family", []),
            "collocations": result.get("collocations", []),
            "examples_by_band": {
                tier: {
                    "en": result.get("example_en", ""),
                    "vi": result.get("example_vi", ""),
                }
            },
            "ielts_tip": result.get("ielts_tip", ""),
        }

        firebase_service.set_enriched_word_doc(normalized, data)
        logger.info(f"Cached new enriched word: {normalized} (band {tier})")
        return data

    # Cache hit — check if this band tier has an example
    examples = cached.get("examples_by_band", {})

    if tier in examples:
        # Full hit — return as-is
        logger.info("Word cache HIT: %s (band %s)", normalized, tier)
        return cached

    logger.info("Word cache PARTIAL HIT: %s (missing band %s)", normalized, tier)
    # Partial hit — generate example for this band tier
    example = await ai_service.generate_band_example(
        word=normalized,
        part_of_speech=cached.get("part_of_speech", ""),
        definition_en=cached.get("definition_en", ""),
        band=band,
        priority=priority,
    )

    firebase_service.update_enriched_word_example(normalized, tier, example)
    cached.setdefault("examples_by_band", {})[tier] = example
    logger.info(f"Added band {tier} example for cached word: {normalized}")
    return cached


def persist_generated_words(words: list[dict], band: float) -> None:
    """Save freshly-generated vocab words to the enriched_words cache.

    Called synchronously after generate_vocabulary returns, so a subsequent
    /word <term> for any of these is a cache hit (0 Gemini calls).
    Per-word write errors are logged and swallowed — never blocks the
    user-facing daily post.
    """
    tier = band_tier(band)
    persisted = 0
    total = len(words)

    for w in words:
        try:
            normalized = normalize_word(w.get("word", ""))
            if not normalized:
                logger.debug("Skipping word with empty name")
                continue

            if not w.get("ipa") and not w.get("definition_en"):
                logger.debug("Skipping word '%s': missing ipa and definition_en", normalized)
                continue

            data = {
                "word": normalized,
                "ipa": w.get("ipa", ""),
                "syllable_stress": w.get("syllable_stress", ""),
                "part_of_speech": w.get("part_of_speech", ""),
                "definition_en": w.get("definition_en", ""),
                "definition_vi": w.get("definition_vi", ""),
                "word_family": w.get("word_family", []),
                "collocations": w.get("collocations", []),
                "examples_by_band": {
                    tier: {
                        "en": w.get("example_en", ""),
                        "vi": w.get("example_vi", ""),
                    }
                },
                "ielts_tip": w.get("ielts_tip", ""),
            }

            firebase_service.set_enriched_word_doc(normalized, data)
            persisted += 1
        except Exception:
            logger.exception("Failed to persist word '%s' to enrichment cache", w.get("word", ""))

    logger.info("Persisted %d/%d generated words to enrichment cache", persisted, total)


# Kept for potential future use — no active callers after GH#6.
async def enrich_words_background(words: list[dict], band: float) -> None:
    """Background-enrich a batch of words into the enriched_words cache.

    - Skips words already cached (cheap Firestore read).
    - Stops on RateLimitError to preserve daily Gemini quota.
    - Logs and continues on per-word errors (non-rate-limit).
    """
    word_strings = [w.get("word", "").strip().lower() for w in words if w.get("word")]
    if not word_strings:
        return

    # Batch pre-filter: check which words already exist in cache
    uncached = []
    for ws in word_strings:
        doc = firebase_service.get_enriched_word_doc(ws)
        if doc is None:
            uncached.append(ws)

    if not uncached:
        logger.info("All %d words already cached, skipping enrichment", len(word_strings))
        return

    logger.info("Background enrichment: %d/%d words need caching", len(uncached), len(word_strings))

    for i, w in enumerate(uncached):
        try:
            await get_enriched_word(w, band, priority="background")
            logger.info("Enriched word %d/%d: %s", i + 1, len(uncached), w)
        except RateLimitError:
            logger.warning(
                "RateLimitError during background enrichment at word %d/%d (%s). Stopping batch.",
                i + 1, len(uncached), w,
            )
            break
        except BackgroundDisabled as e:
            logger.info("Background enrichment skipped: %s", e)
            break
        except Exception:
            logger.error("Failed to enrich word '%s', continuing", w, exc_info=True)

        if i < len(uncached) - 1:
            await asyncio.sleep(config.GEMINI_BACKGROUND_SLEEP)

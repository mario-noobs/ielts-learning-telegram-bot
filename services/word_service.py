import asyncio
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

import config
from services import ai_service, firebase_service
from services.ai_service import BackgroundDisabled, RateLimitError
from services.db import get_sync_session
from services.db.models import VocabularyMaster

logger = logging.getLogger(__name__)


# US-#231 — manual mastery override.
#
# Each tier maps to an SRS interval target (days) + reps count. Manual
# override re-initialises SRS state so the user's quiz history continues
# from the chosen tier. Choosing a tier whose interval is *higher* than
# the current state preserves the current state — we never roll back
# real quiz progress just because the user clicked a chip. Choosing
# *lower* (e.g. user explicitly resets a Mastered word to Weak) does
# apply, since that's an intentional act.
StrengthLiteral = Literal["Weak", "Learning", "Good", "Mastered"]

STRENGTH_TARGETS: dict[StrengthLiteral, dict] = {
    "Weak":     {"srs_interval": 1,  "srs_reps": 0},
    "Learning": {"srs_interval": 5,  "srs_reps": 1},
    "Good":     {"srs_interval": 14, "srs_reps": 3},
    "Mastered": {"srs_interval": 30, "srs_reps": 5},
}

MASTER_WORD_STATUSES = ("active", "candidate")
_BACKFILL_IN_FLIGHT: set[str] = set()
DETAIL_REQUIRED_FIELDS = (
    "ipa",
    "part_of_speech",
    "definition_en",
    "definition_vi",
    "collocations",
    "word_family",
    "ielts_tip",
)

# Order used to compare "is the chosen tier higher than current?"
_STRENGTH_RANK: dict[str, int] = {
    "New": 0, "Weak": 1, "Learning": 2, "Good": 3, "Mastered": 4,
}


def _current_strength(word_data: dict) -> str:
    """Mirror of services.srs_service.get_word_strength — kept here to
    avoid a circular import if srs_service ever depends on word_service."""
    reps = int(word_data.get("srs_reps") or 0)
    interval = int(word_data.get("srs_interval") or 1)
    if reps == 0:
        return "New"
    if interval <= 1:
        return "Weak"
    if interval <= 7:
        return "Learning"
    if interval <= 30:
        return "Good"
    return "Mastered"


def set_word_strength_manual(
    telegram_id: int, word_id: str, target: StrengthLiteral,
) -> dict:
    """Apply a manual strength override (US-#231).

    Returns the updated word dict. Raises ``ValueError`` if the word
    doesn't exist for this user.

    Behaviour:
      - target=Weak/Learning/Good: only writes when the new tier is
        ≥ current tier (no accidental regression of quiz progress).
        Exception: target=Weak overrides regardless — user explicitly
        wants to reset.
      - target=Mastered: writes if current tier < Mastered. If user
        already reached Mastered through quizzing (e.g. interval=60d),
        we keep the larger interval — clicking Mastered is a no-op.
      - Always updates ``srs_next_review`` to ``now + interval days``
        so the SRS engine schedules the word correctly going forward.
    """
    word = firebase_service.get_word_by_id(telegram_id, word_id)
    if not word:
        raise ValueError(f"Word {word_id} not found for user {telegram_id}")

    current = _current_strength(word)
    target_rank = _STRENGTH_RANK[target]
    current_rank = _STRENGTH_RANK[current]

    # The "don't roll back" rule: only Weak target is allowed to lower
    # the rank. Other downward transitions are no-ops.
    if target_rank < current_rank and target != "Weak":
        return word

    targets = STRENGTH_TARGETS[target]
    now = datetime.now(timezone.utc)
    next_review = now + timedelta(days=targets["srs_interval"])

    update = {
        "srs_interval": targets["srs_interval"],
        "srs_reps": targets["srs_reps"],
        "srs_next_review": next_review,
    }
    firebase_service.update_word_srs(telegram_id, word_id, update)
    return {**word, **update}


def _fetch_image_url_sync(word: str) -> str | None:
    key = getattr(config, "UNSPLASH_ACCESS_KEY", None)
    if not key:
        return None
    try:
        params = urllib.parse.urlencode({"query": word, "per_page": 1})
        req = urllib.request.Request(
            f"https://api.unsplash.com/search/photos?{params}",
            headers={"Authorization": f"Client-ID {key}"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        results = data.get("results", [])
        if results:
            return results[0]["urls"]["regular"]
    except Exception:
        logger.debug("Unsplash fetch failed for %s", word)
    return None


async def _fetch_image_url(word: str) -> str | None:
    return await asyncio.to_thread(_fetch_image_url_sync, word)


def _fetch_synonyms_antonyms_sync(word: str) -> tuple[list[str], list[str], str]:
    try:
        req = urllib.request.Request(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(word)}",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read())
                synonyms: list[str] = []
                antonyms: list[str] = []
                for entry in data:
                    for meaning in entry.get("meanings", []):
                        synonyms.extend(meaning.get("synonyms", []))
                        antonyms.extend(meaning.get("antonyms", []))
                        for defn in meaning.get("definitions", []):
                            synonyms.extend(defn.get("synonyms", []))
                            antonyms.extend(defn.get("antonyms", []))
                seen_s: set[str] = set()
                seen_a: set[str] = set()
                synonyms = [s for s in synonyms if s and not (s.lower() in seen_s or seen_s.add(s.lower()))][:8]
                antonyms = [a for a in antonyms if a and not (a.lower() in seen_a or seen_a.add(a.lower()))][:8]
                return synonyms, antonyms, "freedict"
    except Exception:
        logger.debug("Free Dictionary API failed for %s", word)
    return [], [], "gemini"


async def _fetch_synonyms_antonyms(word: str) -> tuple[list[str], list[str], str]:
    synonyms, antonyms, source = await asyncio.to_thread(_fetch_synonyms_antonyms_sync, word)
    if source == "freedict" or synonyms or antonyms:
        return synonyms, antonyms, source
    try:
        result = await ai_service.generate_json(
            f'Return synonyms and antonyms for the English word "{word}". '
            'JSON only: {{"synonyms": ["word1","word2"], "antonyms": ["word3","word4"]}}. '
            'Max 5 each. Only common IELTS-relevant words.'
        )
        return (
            result.get("synonyms", [])[:5],
            result.get("antonyms", [])[:5],
            "gemini",
        )
    except Exception:
        logger.debug("Gemini synonyms fallback failed for %s", word)
    return [], [], "gemini"


async def _backfill_missing_metadata(word: str, cached: dict) -> None:
    try:
        if cached.get("source") == "vocabulary_master":
            try:
                await asyncio.to_thread(
                    firebase_service.set_enriched_word_doc, word, cached,
                )
            except Exception:
                logger.debug("master detail cache write failed for %s", word)

        if cached.get("synonyms") is None:
            try:
                syns, ants, source = await _fetch_synonyms_antonyms(word)
                await asyncio.to_thread(
                    firebase_service.update_enriched_word_synonyms_antonyms,
                    word, syns, ants, source,
                )
            except Exception:
                logger.debug("synonyms/antonyms backfill failed for %s", word)

        if cached.get("image_url") is None and getattr(config, "UNSPLASH_ACCESS_KEY", ""):
            try:
                url = await _fetch_image_url(word)
                if url:
                    await asyncio.to_thread(
                        firebase_service.update_enriched_word_image_url, word, url,
                    )
            except Exception:
                logger.debug("image_url backfill failed for %s", word)
    finally:
        _BACKFILL_IN_FLIGHT.discard(word)


def _needs_metadata_backfill(data: dict) -> bool:
    return data.get("synonyms") is None or (
        data.get("image_url") is None and bool(getattr(config, "UNSPLASH_ACCESS_KEY", ""))
    )


def _schedule_metadata_backfill(word: str, data: dict) -> None:
    if not _needs_metadata_backfill(data) or word in _BACKFILL_IN_FLIGHT:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _BACKFILL_IN_FLIGHT.add(word)
    task = loop.create_task(_backfill_missing_metadata(word, dict(data)))
    task.add_done_callback(lambda _: _BACKFILL_IN_FLIGHT.discard(word))


def _apply_metadata_backfill_result(
    cached: dict, syns: list[str], ants: list[str], source: str,
) -> None:
    cached["synonyms"] = {"words": syns, "source": source}
    cached["antonyms"] = {"words": ants, "source": source}


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


def _master_word_to_enriched(row: VocabularyMaster, tier: str) -> dict:
    examples = {}
    if row.example_en or row.example_vi:
        examples[tier] = {
            "en": row.example_en or "",
            "vi": row.example_vi or "",
        }
    return {
        "word": row.word,
        "ipa": row.ipa or "",
        "syllable_stress": "",
        "part_of_speech": row.part_of_speech or "",
        "definition_en": row.definition_en or "",
        "definition_vi": row.definition_vi or "",
        "word_family": row.word_family or [],
        "collocations": row.collocations or [],
        "examples_by_band": examples,
        "ielts_tip": "",
        "synonyms": {"words": row.synonyms or [], "source": row.source},
        "antonyms": {"words": row.antonyms or [], "source": row.source},
        "image_url": None,
        "source": "vocabulary_master",
    }


def get_master_word_detail(word: str, band: float) -> dict | None:
    normalized = normalize_word(word)
    if not normalized:
        return None
    try:
        with get_sync_session() as session:
            row = session.execute(
                select(VocabularyMaster).where(
                    VocabularyMaster.normalized_word == normalized,
                    VocabularyMaster.status.in_(MASTER_WORD_STATUSES),
                )
            ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        logger.warning("vocab master detail lookup failed for %s: %s", normalized, exc)
        return None
    if row is None:
        return None
    return _master_word_to_enriched(row, band_tier(band))


async def get_word_detail_fast(word: str, band: float) -> dict | None:
    """Return detail without blocking on AI, dictionary, or image providers."""
    normalized = normalize_word(word)
    if not normalized:
        return None

    cached = await asyncio.to_thread(
        firebase_service.get_enriched_word_doc, normalized,
    )
    if cached is not None:
        logger.info("Word detail fast cache HIT: %s", normalized)
        _schedule_metadata_backfill(normalized, cached)
        return cached

    master = await asyncio.to_thread(get_master_word_detail, normalized, band)
    if master is not None:
        logger.info("Word detail master HIT: %s", normalized)
        _schedule_metadata_backfill(normalized, master)
        return master

    logger.info("Word detail fast MISS: %s", normalized)
    return None


def is_word_detail_complete(data: dict, band: float) -> bool:
    tier = band_tier(band)
    examples = data.get("examples_by_band") or {}
    if tier not in examples:
        return False
    for field in DETAIL_REQUIRED_FIELDS:
        if not data.get(field):
            return False
    if data.get("synonyms") is None or data.get("antonyms") is None:
        return False
    if getattr(config, "UNSPLASH_ACCESS_KEY", "") and data.get("image_url") is None:
        return False
    return True


async def get_complete_word_detail(word: str, band: float) -> dict:
    normalized = normalize_word(word)
    fast = await get_word_detail_fast(normalized, band)
    if fast is not None and is_word_detail_complete(fast, band):
        return fast
    if fast is not None:
        logger.info("Word detail incomplete; enriching with AI: %s", normalized)
    return await get_enriched_word(normalized, band, force_ai=fast is not None)


async def get_enriched_word(word: str, band: float,
                           priority: str = "foreground",
                           block_backfill: bool = True,
                           force_ai: bool = False) -> dict:
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

    if cached is None or force_ai:
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
        cached = data

    else:
        # Cache hit — check if this band tier has an example
        examples = cached.get("examples_by_band", {})

        if tier not in examples:
            logger.info("Word cache PARTIAL HIT: %s (missing band %s)", normalized, tier)
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
        else:
            logger.info("Word cache HIT: %s (band %s)", normalized, tier)

    if not block_backfill:
        _schedule_metadata_backfill(normalized, cached)
        return cached

    if cached.get("synonyms") is None:
        try:
            syns, ants, source = await _fetch_synonyms_antonyms(normalized)
            await asyncio.to_thread(
                firebase_service.update_enriched_word_synonyms_antonyms,
                normalized, syns, ants, source,
            )
            _apply_metadata_backfill_result(cached, syns, ants, source)
        except Exception:
            logger.debug("synonyms/antonyms backfill failed for %s", normalized)

    if cached.get("image_url") is None and getattr(config, "UNSPLASH_ACCESS_KEY", ""):
        try:
            url = await _fetch_image_url(normalized)
            if url:
                await asyncio.to_thread(
                    firebase_service.update_enriched_word_image_url, normalized, url,
                )
                cached["image_url"] = url
        except Exception:
            logger.debug("image_url backfill failed for %s", normalized)

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

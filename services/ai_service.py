import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import google.generativeai as genai

import config

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _model = genai.GenerativeModel(config.GEMINI_MODEL)
    return _model


class RateLimitError(Exception):
    """Raised when Gemini API returns 429 rate limit."""
    def __init__(self, limit_type: str, retry_after: int = 0):
        self.limit_type = limit_type
        self.retry_after = retry_after
        super().__init__(f"Rate limited: {limit_type}. Retry after {retry_after}s")


class BackgroundDisabled(RuntimeError):
    """Raised when the background circuit breaker is active."""
    pass


def _utc_today():
    """Return today's date in UTC."""
    return datetime.now(timezone.utc).date()


def _next_midnight_utc_monotonic() -> float:
    """Return a monotonic timestamp for the next midnight UTC."""
    utc_now = datetime.now(timezone.utc)
    tomorrow = (utc_now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = (tomorrow - utc_now).total_seconds()
    return time.monotonic() + delta


class GeminiGate:
    """Process-wide sliding-window rate gate for Gemini API calls.

    Foreground calls pass through immediately (up to the absolute RPM limit).
    Background calls are throttled to a lower ceiling, reserving headroom
    for foreground traffic.
    """

    def __init__(self, background_rpm: int) -> None:
        self._background_rpm = background_rpm
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()
        self._backoff_until: float = 0.0
        # Daily-spend tracking
        self._daily_count: int = 0
        self._daily_date = None  # UTC date of last reset
        # RPD circuit breaker
        self._background_disabled_until: float = 0.0
        self._daily_cap_warned: bool = False

    def _purge(self, now: float) -> None:
        """Remove timestamps older than 60 seconds."""
        cutoff = now - 60.0
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def _reset_daily_if_needed(self) -> None:
        """Reset daily counter if the UTC date has changed. Must be called under lock."""
        today = _utc_today()
        if self._daily_date != today:
            if self._daily_date is not None:
                logger.info("GeminiGate: new UTC day — daily counter reset (was %d)", self._daily_count)
            self._daily_count = 0
            self._daily_date = today
            self._daily_cap_warned = False
            self._background_disabled_until = 0.0

    async def acquire(self, priority: str = "foreground") -> None:
        """Wait until a call slot is available.

        Args:
            priority: "foreground" or "background".
                - foreground: raises RateLimitError if under 429 backoff.
                - background: waits if recent background calls >= background_rpm
                  ceiling, or sleeps through 429 backoff. Raises BackgroundDisabled
                  if the RPD circuit breaker is active or daily cap is reached.
        """
        if priority == "foreground":
            async with self._lock:
                self._reset_daily_if_needed()
                now = time.monotonic()
                if self._backoff_until > now:
                    remaining = int(self._backoff_until - now) + 1
                    raise RateLimitError("RPM (requests per minute)", remaining)
            return

        # Background path: wait until we have budget
        while True:
            async with self._lock:
                self._reset_daily_if_needed()
                now = time.monotonic()

                # RPD circuit breaker
                if now < self._background_disabled_until:
                    raise BackgroundDisabled("RPD circuit breaker active until next UTC midnight")

                # Daily background cap
                if self._daily_count >= config.GEMINI_DAILY_BACKGROUND_CAP:
                    if not self._daily_cap_warned:
                        logger.warning(
                            "GeminiGate: daily background cap reached (%d/%d) — refusing background acquire",
                            self._daily_count, config.GEMINI_DAILY_QUOTA,
                        )
                        self._daily_cap_warned = True
                    raise BackgroundDisabled(
                        f"Daily background cap reached ({self._daily_count}/{config.GEMINI_DAILY_QUOTA})"
                    )

                # Respect 429 backoff
                if self._backoff_until > now:
                    sleep_time = min(self._backoff_until - now, 1.0)
                else:
                    self._purge(now)
                    if len(self._timestamps) < self._background_rpm:
                        # Slot available — record and return
                        self._timestamps.append(now)
                        self._daily_count += 1
                        return
                    # Window full — sleep until oldest entry expires
                    sleep_time = min(
                        self._timestamps[0] + 60.0 - now,
                        1.0,
                    )

            await asyncio.sleep(sleep_time)

    def record_call(self) -> None:
        """Record a Gemini call timestamp (for foreground calls).

        Also increments the daily counter. Background calls record their
        timestamp inside acquire(), but both paths increment _daily_count.
        """
        self._timestamps.append(time.monotonic())
        self._daily_count += 1

    def status(self) -> str:
        """Return a short snapshot for troubleshooting logs."""
        bg_disabled = self._background_disabled_until > time.monotonic()
        return (
            f"daily={self._daily_count}/{config.GEMINI_DAILY_QUOTA} "
            f"rpm={len(self._timestamps)} bg_disabled={bg_disabled}"
        )

    def notify_429(self, retry_after: int, limit_type: str = "unknown") -> None:
        """Signal that Gemini returned 429. Sets a backoff deadline.

        For RPD limits, also engages the background circuit breaker until
        next UTC midnight. For RPM/TPM/other, only sets the short backoff.
        """
        now = time.monotonic()
        if "RPD" in limit_type:
            self._backoff_until = now + retry_after
            self._background_disabled_until = _next_midnight_utc_monotonic()
            secs_until_midnight = int(self._background_disabled_until - now)
            logger.warning(
                "GeminiGate: RPD circuit breaker tripped — background disabled until midnight UTC (%ds from now)",
                secs_until_midnight,
            )
        else:
            self._backoff_until = now + retry_after
            logger.warning("GeminiGate: 429 backoff set for %ds (limit_type=%s)", retry_after, limit_type)


_gate = GeminiGate(background_rpm=config.GEMINI_BACKGROUND_RPM)


def _parse_rate_limit(error_str: str) -> tuple[str, int]:
    """Parse 429 error to extract which limit was hit and retry delay."""
    limit_type = "unknown"
    retry_after = 60

    if "PerMinute" in error_str or "RPM" in error_str:
        limit_type = "RPM (requests per minute)"
    elif "PerDay" in error_str or "RPD" in error_str:
        limit_type = "RPD (requests per day)"
    elif "token" in error_str.lower() or "TPM" in error_str:
        limit_type = "TPM (tokens per minute)"

    # Extract retry_delay seconds
    import re
    match = re.search(r'retry.*?(\d+)', error_str)
    if match:
        retry_after = int(match.group(1))

    return limit_type, retry_after


async def generate(prompt: str, max_retries: int = 2,
                   priority: str = "foreground") -> str:
    """Send a prompt to Gemini and return the text response.

    Args:
        prompt: The prompt text to send.
        max_retries: Number of retries on non-429 errors.
        priority: "foreground" or "background". Background calls are
            throttled by the process-wide GeminiGate.

    On 429 rate limit: raises RateLimitError immediately (no retry).
    On other errors: retries up to max_retries.
    """
    await _gate.acquire(priority)
    logger.info("Gemini call [%s] %s prompt_len=%d", priority, _gate.status(), len(prompt))

    for attempt in range(max_retries):
        try:
            model = _get_model()
            response = await asyncio.to_thread(
                model.generate_content, prompt
            )
            if priority == "foreground":
                _gate.record_call()
            return response.text.strip()
        except Exception as e:
            error_str = str(e)

            # 429 rate limit — don't retry, fail fast
            if "429" in error_str or "quota" in error_str.lower():
                limit_type, retry_after = _parse_rate_limit(error_str)
                logger.error("Gemini 429: %s retry_after=%ds %s", limit_type, retry_after, _gate.status())
                logger.error("Gemini 429 full error: %s", error_str[:800])
                _gate.notify_429(retry_after, limit_type)
                raise RateLimitError(limit_type, retry_after)

            logger.warning(f"Gemini API attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(config.GEMINI_RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"Gemini API failed after {max_retries} attempts")
                raise


async def generate_json(prompt: str, max_retries: int = 3,
                        priority: str = "foreground"):
    """Send a prompt and parse the response as JSON."""
    text = await generate(prompt, max_retries, priority=priority)
    # Clean markdown code blocks if present
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


# ─── Vocabulary ────────────────────────────────────────────────────

async def generate_vocabulary(count: int, band: float, topic: str,
                              exclude_words: list = None) -> list[dict]:
    from prompts.vocab_prompt import GENERATE_VOCABULARY

    exclude_clause = ""
    if exclude_words:
        exclude_clause = f"\nDo NOT include these words (already learned): {', '.join(exclude_words[:100])}"

    prompt = GENERATE_VOCABULARY.format(
        count=count, band=band, topic=topic, exclude_clause=exclude_clause
    )
    return await generate_json(prompt)


async def enrich_word(word: str, band: float,
                      priority: str = "foreground") -> dict:
    """Generate full word enrichment data via Gemini. Returns parsed JSON dict."""
    from prompts.word_enrichment_prompt import ENRICH_WORD
    prompt = ENRICH_WORD.format(word=word, band=band)
    return await generate_json(prompt, priority=priority)


async def generate_band_example(word: str, part_of_speech: str,
                                definition_en: str, band: float,
                                priority: str = "foreground") -> dict:
    """Generate a band-specific example sentence via Gemini. Returns parsed JSON dict."""
    from prompts.word_enrichment_prompt import ENRICH_WORD_EXAMPLE
    prompt = ENRICH_WORD_EXAMPLE.format(
        word=word, part_of_speech=part_of_speech,
        definition_en=definition_en, band=band
    )
    return await generate_json(prompt, priority=priority)


async def explain_word(word: str, band: float) -> str:
    from prompts.vocab_prompt import EXPLAIN_WORD

    prompt = EXPLAIN_WORD.format(word=word, band=band)
    return await generate(prompt)


# ─── Quiz ──────────────────────────────────────────────────────────

async def generate_quiz(word: str, definition: str,
                        quiz_type: str) -> dict:
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
        first_letter=word[0].upper() if word else "?"
    )
    result = await generate_json(prompt)
    result["type"] = quiz_type
    result["word"] = word
    return result


async def generate_quiz_batch(words: list[dict],
                              types: list[str]) -> list[dict]:
    """Generate multiple quiz questions in a single AI call.

    Args:
        words: List of dicts with 'word' and 'definition' keys
        types: List of quiz types, one per word (same length as words)
    Returns:
        List of question dicts
    """
    from prompts.quiz_prompt import GENERATE_QUIZ_BATCH

    words_list = "\n".join(
        f'{i+1}. "{w["word"]}" = "{w.get("definition", "")}"'
        for i, w in enumerate(words)
    )
    types_list = ", ".join(types)

    prompt = GENERATE_QUIZ_BATCH.format(
        words_list=words_list,
        types_list=types_list,
        count=len(words),
    )
    results = await generate_json(prompt)

    # Tag each result with its type and word_id
    for i, result in enumerate(results):
        if i < len(types):
            result["type"] = types[i]
        if i < len(words):
            result["word"] = words[i]["word"]
            if "word_id" in words[i]:
                result["word_id"] = words[i]["word_id"]
    return results


async def generate_challenge(count: int, band: float, topic: str) -> list:
    from prompts.quiz_prompt import GENERATE_CHALLENGE

    prompt = GENERATE_CHALLENGE.format(count=count, band=band, topic=topic)
    return await generate_json(prompt)


async def evaluate_paraphrase(original: str, word: str,
                               student_answer: str,
                               sample_answer: str) -> dict:
    from prompts.quiz_prompt import EVALUATE_PARAPHRASE

    prompt = EVALUATE_PARAPHRASE.format(
        original=original, word=word,
        student_answer=student_answer, sample_answer=sample_answer
    )
    return await generate_json(prompt)


# ─── Writing ───────────────────────────────────────────────────────

async def get_writing_feedback(text: str, band: float) -> str:
    from prompts.writing_prompt import WRITING_FEEDBACK, WRITING_FEEDBACK_SHORT

    template = WRITING_FEEDBACK if len(text) > 100 else WRITING_FEEDBACK_SHORT
    prompt = template.format(text=text, band=band)
    return await generate(prompt)


# ─── Translation ───────────────────────────────────────────────────

async def translate_text(text: str, band: float) -> str:
    from prompts.translate_prompt import DETECT_LANGUAGE, TRANSLATE_EN_TO_VI, TRANSLATE_VI_TO_EN

    # Detect language
    lang_prompt = DETECT_LANGUAGE.format(text=text)
    lang = (await generate(lang_prompt)).strip().lower()

    if lang == "vi":
        prompt = TRANSLATE_VI_TO_EN.format(text=text, band=band)
    else:
        prompt = TRANSLATE_EN_TO_VI.format(text=text, band=band)

    return await generate(prompt)

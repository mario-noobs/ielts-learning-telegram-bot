import json
import asyncio
import logging
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


async def generate(prompt: str, max_retries: int = 2) -> str:
    """Send a prompt to Gemini and return the text response.

    On 429 rate limit: raises RateLimitError immediately (no retry).
    On other errors: retries up to max_retries.
    """
    for attempt in range(max_retries):
        try:
            model = _get_model()
            response = await asyncio.to_thread(
                model.generate_content, prompt
            )
            return response.text.strip()
        except Exception as e:
            error_str = str(e)

            # 429 rate limit — don't retry, fail fast
            if "429" in error_str or "quota" in error_str.lower():
                limit_type, retry_after = _parse_rate_limit(error_str)
                logger.error(f"Gemini 429 rate limit hit: {limit_type}, retry after {retry_after}s")
                raise RateLimitError(limit_type, retry_after)

            logger.warning(f"Gemini API attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(config.GEMINI_RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"Gemini API failed after {max_retries} attempts")
                raise


async def generate_json(prompt: str, max_retries: int = 3):
    """Send a prompt and parse the response as JSON."""
    text = await generate(prompt, max_retries)
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


async def explain_word(word: str, band: float) -> str:
    from prompts.vocab_prompt import EXPLAIN_WORD

    prompt = EXPLAIN_WORD.format(word=word, band=band)
    return await generate(prompt)


# ─── Quiz ──────────────────────────────────────────────────────────

async def generate_quiz(word: str, definition: str,
                        quiz_type: str) -> dict:
    from prompts.quiz_prompt import (
        GENERATE_MULTIPLE_CHOICE, GENERATE_FILL_BLANK,
        GENERATE_SYNONYM_ANTONYM, GENERATE_PARAPHRASE
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
    from prompts.translate_prompt import (
        TRANSLATE_VI_TO_EN, TRANSLATE_EN_TO_VI, DETECT_LANGUAGE
    )

    # Detect language
    lang_prompt = DETECT_LANGUAGE.format(text=text)
    lang = (await generate(lang_prompt)).strip().lower()

    if lang == "vi":
        prompt = TRANSLATE_VI_TO_EN.format(text=text, band=band)
    else:
        prompt = TRANSLATE_EN_TO_VI.format(text=text, band=band)

    return await generate(prompt)

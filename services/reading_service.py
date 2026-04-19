"""Reading Lab — passage loader, AI question generation, grading.

Passages live in ``content/reading/passages/*.md`` as markdown files with
YAML frontmatter (see ``content/reading/README.md``). They are loaded
once at import time into an in-memory index.

Question generation (US-M9.3, #137) calls Gemini to produce exactly 13
IELTS-authentic questions per passage:

    4 × gap-fill, 4 × T/F/NG, 3 × matching-headings, 2 × mcq

Results are schema-validated (grounding spans, distribution, required
fields) and cached in Firestore under ``reading_questions/{passage_id}``
so the AI cost is one-time per passage. A deterministic stub is kept as
a fallback for environments without AI access (tests, seed scripts).

Grading is deterministic per question type:
    • gap-fill: case-insensitive whitespace-trimmed string match
    • tfng:     enum match (TRUE / FALSE / NOT_GIVEN, with synonyms)
    • mcq / matching-headings: option id match

Band mapping uses an approximate IELTS Academic Reading raw-to-band
table scaled for a 13-question set.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover — requirements.txt pins pyyaml
    raise RuntimeError("reading_service requires PyYAML") from exc

logger = logging.getLogger(__name__)

PASSAGES_DIR = Path(__file__).resolve().parent.parent / "content" / "reading" / "passages"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

# ─── Passage index ───────────────────────────────────────────────────

_PASSAGE_INDEX: dict[str, dict[str, Any]] = {}


def _load_passages() -> dict[str, dict[str, Any]]:
    if not PASSAGES_DIR.is_dir():
        logger.warning("reading: passages dir not found at %s", PASSAGES_DIR)
        return {}

    index: dict[str, dict[str, Any]] = {}
    for path in sorted(PASSAGES_DIR.glob("p*.md")):
        if path.name == "_template.md":
            continue
        raw = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(raw)
        if not m:
            logger.warning("reading: skipping malformed passage %s", path.name)
            continue
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            logger.warning("reading: skipping %s — bad YAML: %s", path.name, exc)
            continue
        meta["body"] = m.group(2).strip()
        index[meta["id"]] = meta

    logger.info("reading: loaded %d passages from %s", len(index), PASSAGES_DIR)
    return index


def _ensure_loaded() -> dict[str, dict[str, Any]]:
    global _PASSAGE_INDEX
    if not _PASSAGE_INDEX:
        _PASSAGE_INDEX = _load_passages()
    return _PASSAGE_INDEX


def reload_index() -> int:
    global _PASSAGE_INDEX
    _PASSAGE_INDEX = _load_passages()
    return len(_PASSAGE_INDEX)


def list_summaries(
    band: Optional[float] = None,
    topic: Optional[str] = None,
) -> list[dict[str, Any]]:
    index = _ensure_loaded()
    out = []
    for p in index.values():
        if band is not None and p.get("band") != band:
            continue
        if topic is not None and p.get("topic") != topic:
            continue
        out.append({
            "id": p["id"],
            "title": p.get("title", ""),
            "topic": p.get("topic", ""),
            "band": p.get("band"),
            "word_count": p.get("word_count", 0),
            "attribution": p.get("attribution", ""),
            "ai_assisted": bool(p.get("ai_assisted", False)),
        })
    out.sort(key=lambda x: x["id"])
    return out


def get_passage(passage_id: str) -> Optional[dict[str, Any]]:
    return _ensure_loaded().get(passage_id)


# ─── Question generation ─────────────────────────────────────────────

QUESTION_COUNT = 13
DISTRIBUTION = {
    "gap-fill": 4,
    "tfng": 4,
    "matching-headings": 3,
    "mcq": 2,
}
ALLOWED_TYPES = set(DISTRIBUTION.keys())
TFNG_VALUES = {"TRUE", "FALSE", "NOT_GIVEN"}


class QuestionGenerationError(Exception):
    """Raised when AI-generated questions fail schema validation."""


def _validate_question(q: Any, body: str) -> list[str]:
    """Return a list of error strings (empty list = valid)."""
    errors: list[str] = []
    if not isinstance(q, dict):
        return ["question is not a dict"]
    for key in ("id", "type", "stem", "answer", "passage_span", "explanation"):
        if key not in q:
            errors.append(f"missing key '{key}'")
    if errors:
        return errors

    if q["type"] not in ALLOWED_TYPES:
        errors.append(f"type '{q['type']}' not in {sorted(ALLOWED_TYPES)}")

    span = q.get("passage_span") or {}
    if not isinstance(span, dict) or "start" not in span or "end" not in span:
        errors.append("passage_span must have start and end")
    else:
        try:
            start, end = int(span["start"]), int(span["end"])
        except (TypeError, ValueError):
            errors.append("passage_span offsets must be integers")
        else:
            if not (0 <= start < end <= len(body)):
                errors.append(
                    f"passage_span out of range: start={start}, end={end}, body_len={len(body)}"
                )

    if q["type"] in ("mcq", "matching-headings"):
        options = q.get("options")
        if not isinstance(options, list) or len(options) != 4:
            errors.append("mcq/matching-headings must have exactly 4 options")
        else:
            ids = [o.get("id") for o in options if isinstance(o, dict)]
            if q.get("answer") not in ids:
                errors.append(f"answer '{q.get('answer')}' does not match any option id")

    if q["type"] == "tfng":
        if q.get("answer") not in TFNG_VALUES:
            errors.append(f"tfng answer must be one of {sorted(TFNG_VALUES)}")

    if q["type"] == "gap-fill":
        ans = q.get("answer", "")
        if not isinstance(ans, str) or not ans.strip():
            errors.append("gap-fill answer must be a non-empty string")

    return errors


def validate_question_set(questions: list[dict], body: str) -> None:
    """Raise QuestionGenerationError if the set violates the schema."""
    if len(questions) != QUESTION_COUNT:
        raise QuestionGenerationError(
            f"expected {QUESTION_COUNT} questions, got {len(questions)}"
        )

    type_counts: dict[str, int] = {}
    all_errors: list[str] = []
    for idx, q in enumerate(questions, 1):
        errs = _validate_question(q, body)
        if errs:
            all_errors.extend(f"q{idx}: {e}" for e in errs)
            continue
        type_counts[q["type"]] = type_counts.get(q["type"], 0) + 1

    for qtype, expected in DISTRIBUTION.items():
        if type_counts.get(qtype, 0) != expected:
            all_errors.append(
                f"distribution: expected {expected} {qtype}, got {type_counts.get(qtype, 0)}"
            )

    if all_errors:
        raise QuestionGenerationError("; ".join(all_errors))


def _split_for_client(questions: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (client_view, answer_key).

    Client view omits answer, passage_span, and explanation — those stay
    on the server until the session is submitted.
    """
    client: list[dict] = []
    key: list[dict] = []
    for q in questions:
        client_item: dict[str, Any] = {
            "id": q["id"],
            "type": q["type"],
            "stem": q["stem"],
        }
        if q["type"] in ("mcq", "matching-headings"):
            client_item["options"] = q["options"]
        client.append(client_item)
        key.append({
            "id": q["id"],
            "type": q["type"],
            "answer": q["answer"],
            "explanation": q.get("explanation", ""),
            "passage_span": q.get("passage_span"),
        })
    return client, key


async def generate_question_set_ai(passage: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Call Gemini to generate 13 questions, validate, split for client/server."""
    from prompts.reading_questions_prompt import GENERATE_READING_QUESTIONS
    from services import ai_service

    body = passage.get("body", "")
    prompt = GENERATE_READING_QUESTIONS.format(
        title=passage.get("title", ""),
        band=passage.get("band", 6.0),
        body=body,
    )
    payload = await ai_service.generate_json(prompt)
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list):
        raise QuestionGenerationError("response missing 'questions' list")
    validate_question_set(questions, body)
    return _split_for_client(questions)


# ─── Deterministic fallback stub ─────────────────────────────────────
#
# Used when AI is unavailable (offline tests, seed scripts, a broken
# Gemini key). Produces 5 MCQs with o1 as the correct answer — enough
# to exercise the session flow end-to-end without spending tokens.

_STUB_COUNT = 5


def generate_question_set_stub(passage: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    title = passage.get("title", "this passage")
    topic = passage.get("topic", "the subject")
    stems = [
        f'What is the main subject of "{title}"?',
        "The author's tone is best described as:",
        "Which of the following is NOT discussed?",
        "The passage is most likely aimed at:",
        "Which statement best summarises the position?",
    ]
    option_sets = [
        [topic, "an unrelated field", "a personal anecdote", "a fictional story"],
        ["informative", "sarcastic", "hostile", "mocking"],
        ["an unrelated domain", "examples from the field", "implications", "context"],
        ["a general reader", "specialists only", "young children", "no one"],
        ["worthy of attention", "unimportant", "entirely new", "without experts"],
    ]
    client, key = [], []
    for i, (stem, opts) in enumerate(zip(stems, option_sets), 1):
        qid = f"q{i}"
        options = [{"id": f"o{j+1}", "text": t} for j, t in enumerate(opts)]
        client.append({"id": qid, "type": "mcq", "stem": stem, "options": options})
        key.append({
            "id": qid, "type": "mcq", "answer": "o1",
            "explanation": "(stub) The first option is correct.",
            "passage_span": {"start": 0, "end": min(100, len(passage.get("body", "")))},
        })
    return client, key


# ─── Cache + orchestrator ────────────────────────────────────────────


async def get_or_generate_questions(
    passage: dict[str, Any],
    use_ai: bool = True,
) -> tuple[list[dict], list[dict]]:
    """Return (client_view, answer_key). Hits cache if present."""
    from services import firebase_service

    passage_id = passage["id"]
    cached = await asyncio.to_thread(
        firebase_service.get_cached_reading_questions, passage_id,
    )
    if cached:
        logger.info("reading: cache hit for passage %s", passage_id)
        return cached["questions_client"], cached["answer_key"]

    if use_ai:
        try:
            client, key = await generate_question_set_ai(passage)
            await asyncio.to_thread(
                firebase_service.save_cached_reading_questions,
                passage_id,
                {"questions_client": client, "answer_key": key},
            )
            logger.info("reading: generated + cached %d questions for %s",
                        len(client), passage_id)
            return client, key
        except Exception as exc:
            logger.warning(
                "reading: AI generation failed for %s (%s); falling back to stub",
                passage_id, exc,
            )

    return generate_question_set_stub(passage)


# ─── Grading ─────────────────────────────────────────────────────────

# 13-question raw-to-band mapping (approximated from Cambridge 40Q table
# scaled by 40/13 ≈ 3.08). Caps at 9.0, floors at 3.0.
_BAND_BY_CORRECT_13 = {
    0: 3.0, 1: 3.0, 2: 3.0, 3: 3.5, 4: 4.0, 5: 5.0, 6: 5.0,
    7: 5.5, 8: 6.0, 9: 6.5, 10: 7.0, 11: 7.5, 12: 8.5, 13: 9.0,
}
_BAND_BY_CORRECT_5 = {0: 3.0, 1: 4.0, 2: 5.0, 3: 6.0, 4: 7.0, 5: 8.0}

_TFNG_NORMALIZE = {
    "TRUE": "TRUE", "T": "TRUE", "YES": "TRUE",
    "FALSE": "FALSE", "F": "FALSE", "NO": "FALSE",
    "NOT_GIVEN": "NOT_GIVEN", "NG": "NOT_GIVEN",
    "NOT GIVEN": "NOT_GIVEN", "NOTGIVEN": "NOT_GIVEN",
}


def _normalize_gap_fill(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def _normalize_tfng(value: str) -> Optional[str]:
    if not isinstance(value, str):
        return None
    key = value.strip().upper().replace("-", "_")
    return _TFNG_NORMALIZE.get(key)


def _compare(qtype: str, user_ans: Any, correct_ans: Any) -> bool:
    if user_ans is None:
        return False
    if qtype == "gap-fill":
        return _normalize_gap_fill(user_ans) == _normalize_gap_fill(correct_ans)
    if qtype == "tfng":
        return _normalize_tfng(user_ans) == _normalize_tfng(correct_ans)
    # mcq / matching-headings: exact option-id match
    return str(user_ans).strip() == str(correct_ans).strip()


def _band_for_score(correct: int, total: int) -> float:
    if total == 13:
        return _BAND_BY_CORRECT_13.get(correct, 3.0)
    if total == 5:
        return _BAND_BY_CORRECT_5.get(correct, 3.0)
    # Linear fallback for non-standard sizes.
    return round(3.0 + (correct / max(total, 1)) * 6.0, 1)


def grade_answers(
    user_answers: dict[str, Any],
    answer_key: list[dict],
    questions: list[dict] | None = None,  # kept for legacy call-sites
) -> dict[str, Any]:
    """Score user_answers against answer_key.

    ``answer_key`` is a list of dicts with ``{id, type, answer, explanation}``.
    The ``questions`` argument is accepted for backwards compatibility with
    the US-M9.2 stub shape and ignored here.
    """
    per_question = []
    correct = 0
    for item in answer_key:
        qid = item["id"]
        qtype = item.get("type", "mcq")
        correct_ans = item.get("answer")
        given = user_answers.get(qid)
        is_correct = _compare(qtype, given, correct_ans)
        if is_correct:
            correct += 1
        per_question.append({
            "id": qid,
            "user_answer": given,
            "correct_answer": correct_ans,
            "is_correct": is_correct,
            "explanation": item.get("explanation", ""),
        })

    total = len(answer_key)
    return {
        "correct": correct,
        "total": total,
        "band": _band_for_score(correct, total),
        "per_question": per_question,
    }


__all__ = [
    "list_summaries",
    "get_passage",
    "get_or_generate_questions",
    "generate_question_set_ai",
    "generate_question_set_stub",
    "validate_question_set",
    "QuestionGenerationError",
    "grade_answers",
    "reload_index",
    "QUESTION_COUNT",
    "DISTRIBUTION",
]

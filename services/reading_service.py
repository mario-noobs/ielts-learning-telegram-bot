"""Reading Lab — passage loader, stub question generator, grader.

Passages live in ``content/reading/passages/*.md`` as markdown files with
YAML frontmatter (see ``content/reading/README.md``). They are loaded once
at import time into an in-memory index.

Questions in M9.2 are a deterministic stub so the frontend and session
flow can be built end-to-end. US-M9.3 replaces the stub with AI-generated
gap-fill / T/F/NG / matching questions.

Grading in M9.2 is a simple correct/total fraction mapped to a band.
US-M9.3 adds per-question explanations from the AI.
"""
from __future__ import annotations

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

# ─── Passage model (plain dict, kept simple for the in-memory index) ──

_PASSAGE_INDEX: dict[str, dict[str, Any]] = {}
_BANDS_ORDERED = (5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5)


def _load_passages() -> dict[str, dict[str, Any]]:
    """Read all passage markdown files into a dict keyed by id.

    Silently returns {} if the directory is missing — this keeps tests
    that do not need reading content from failing at import time.
    """
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
    """Force-reload the passage index. Returns the new count."""
    global _PASSAGE_INDEX
    _PASSAGE_INDEX = _load_passages()
    return len(_PASSAGE_INDEX)


# ─── Listing / fetching ──────────────────────────────────────────────

def list_summaries(
    band: Optional[float] = None,
    topic: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return passage summaries (no body). Filtered by band / topic."""
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
    """Return the full passage dict including body, or None if missing."""
    return _ensure_loaded().get(passage_id)


# ─── Question generation (STUB for M9.2, replaced in US-M9.3) ────────
#
# The stub produces 5 deterministic MCQ questions derived from the
# passage title + topic. Answer keys are generated alongside and stored
# in the session doc; they are NEVER returned to the client in passage
# detail — only revealed in the grading payload after submit.

_STUB_QUESTION_COUNT = 5


def generate_question_set(passage: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Return (questions_for_client, answer_key).

    Questions are shaped so the client can render them immediately; the
    answer key is a parallel list of correct option ids (stored in the
    session doc, not exposed until submit).
    """
    title = passage.get("title", "this passage")
    topic = passage.get("topic", "the subject")

    templates = [
        (
            f'What is the main subject of "{title}"?',
            ["mcq"],
            [topic, "an unrelated field", "a personal anecdote", "a fictional story"],
            0,
        ),
        (
            "According to the passage, the author's tone is best described as:",
            ["mcq"],
            ["informative", "sarcastic", "hostile", "mocking"],
            0,
        ),
        (
            "Which of the following is NOT discussed in the passage?",
            ["mcq"],
            ["a topic from another domain entirely", "examples from the field",
             "implications for readers", "context for the argument"],
            0,
        ),
        (
            "The passage is most likely aimed at:",
            ["mcq"],
            ["a general educated reader", "a specialist audience only",
             "young children", "no one in particular"],
            0,
        ),
        (
            "Which statement best summarises the passage's position?",
            ["mcq"],
            ["the topic is worth careful attention",
             "the topic is unimportant", "the topic is entirely new",
             "the topic has no experts"],
            0,
        ),
    ]

    questions = []
    answers = []
    for i, (stem, _types, options, correct_idx) in enumerate(templates[:_STUB_QUESTION_COUNT], 1):
        qid = f"q{i}"
        questions.append({
            "id": qid,
            "type": "mcq",
            "stem": stem,
            "options": [{"id": f"o{j+1}", "text": t} for j, t in enumerate(options)],
        })
        answers.append(f"o{correct_idx + 1}")

    return questions, answers


# ─── Grading ─────────────────────────────────────────────────────────
#
# Grading maps correct/total to a rough IELTS band using the Academic
# Reading raw-to-band table (approximation for a 5-question stub).

_BAND_BY_CORRECT = {0: 3.0, 1: 4.0, 2: 5.0, 3: 6.0, 4: 7.0, 5: 8.0}


def grade_answers(
    user_answers: dict[str, str],
    answer_key: list[str],
    questions: list[dict],
) -> dict[str, Any]:
    """Compare answers against the key, return a grading payload."""
    per_question = []
    correct = 0
    for q, key in zip(questions, answer_key):
        qid = q["id"]
        given = user_answers.get(qid)
        is_correct = given == key
        if is_correct:
            correct += 1
        per_question.append({
            "id": qid,
            "user_answer": given,
            "correct_answer": key,
            "is_correct": is_correct,
            "explanation": "(Explanations arrive in M9.3 alongside AI-generated questions.)",
        })

    total = len(answer_key)
    band = _BAND_BY_CORRECT.get(correct, 5.0) if total == _STUB_QUESTION_COUNT else (
        round(3.0 + (correct / max(total, 1)) * 6.0, 1)
    )

    return {
        "correct": correct,
        "total": total,
        "band": band,
        "per_question": per_question,
    }


__all__ = [
    "list_summaries",
    "get_passage",
    "generate_question_set",
    "grade_answers",
    "reload_index",
]

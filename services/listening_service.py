import difflib
import logging
import re

from services import ai_service

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"dictation", "gap_fill", "comprehension"}

_MIN_BLANKS = 3
_MAX_BLANKS = 10
_MIN_QUESTIONS = 2
_MAX_QUESTIONS = 6
_WORDS_PER_SECOND = 2.3  # average speaking rate


def _clean_str(value, default: str = "") -> str:
    return str(value or default).strip()


def _duration_estimate(text: str) -> int:
    words = len([w for w in text.split() if w.strip()])
    return max(8, int(round(words / _WORDS_PER_SECOND)))


def _normalize_dictation(raw: dict, band: float, topic: str) -> dict:
    transcript = _clean_str(raw.get("transcript"))
    return {
        "exercise_type": "dictation",
        "band": band,
        "topic": topic,
        "title": _clean_str(raw.get("title"), default="Dictation"),
        "transcript": transcript,
        "display_text": "",
        "blanks": [],
        "questions": [],
        "duration_estimate_sec": _duration_estimate(transcript),
    }


def _normalize_gap_fill(raw: dict, band: float, topic: str) -> dict:
    transcript = _clean_str(raw.get("transcript"))
    display_text = _clean_str(raw.get("display_text")) or transcript

    blanks_raw = raw.get("blanks") or []
    blanks: list[dict] = []
    for i, b in enumerate(blanks_raw):
        if not isinstance(b, dict):
            continue
        answer = _clean_str(b.get("answer"))
        if not answer:
            continue
        blanks.append({"index": i, "answer": answer.lower()})
        if len(blanks) >= _MAX_BLANKS:
            break
    for i, b in enumerate(blanks):
        b["index"] = i

    return {
        "exercise_type": "gap_fill",
        "band": band,
        "topic": topic,
        "title": _clean_str(raw.get("title"), default="Gap Fill"),
        "transcript": transcript,
        "display_text": display_text,
        "blanks": blanks,
        "questions": [],
        "duration_estimate_sec": _duration_estimate(transcript),
    }


def _normalize_question(raw: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None
    options = [_clean_str(o) for o in (raw.get("options") or []) if _clean_str(o)]
    if len(options) < 2:
        return None
    try:
        correct_index = int(raw.get("correct_index", 0))
    except (TypeError, ValueError):
        correct_index = 0
    correct_index = max(0, min(len(options) - 1, correct_index))
    return {
        "question": _clean_str(raw.get("question")),
        "options": options[:4],
        "correct_index": correct_index,
        "explanation_vi": _clean_str(raw.get("explanation_vi")),
    }


def _normalize_comprehension(raw: dict, band: float, topic: str) -> dict:
    transcript = _clean_str(raw.get("transcript"))
    questions = [
        q for q in (_normalize_question(q) for q in raw.get("questions") or [])
        if q is not None
    ][:_MAX_QUESTIONS]
    return {
        "exercise_type": "comprehension",
        "band": band,
        "topic": topic,
        "title": _clean_str(raw.get("title"), default="Comprehension"),
        "transcript": transcript,
        "display_text": "",
        "blanks": [],
        "questions": questions,
        "duration_estimate_sec": _duration_estimate(transcript),
    }


async def generate_exercise(
    exercise_type: str, band: float, topic: str
) -> dict:
    from prompts.listening_prompt import (
        COMPREHENSION_PROMPT,
        DICTATION_PROMPT,
        GAP_FILL_PROMPT,
    )

    if exercise_type not in ALLOWED_TYPES:
        raise ValueError(f"Unknown exercise_type: {exercise_type}")

    template = {
        "dictation": DICTATION_PROMPT,
        "gap_fill": GAP_FILL_PROMPT,
        "comprehension": COMPREHENSION_PROMPT,
    }[exercise_type]
    filled = template.format(band=band, topic=topic or "general")
    raw = await ai_service.generate_json(filled, priority="foreground")

    if exercise_type == "dictation":
        return _normalize_dictation(raw, band, topic)
    if exercise_type == "gap_fill":
        exercise = _normalize_gap_fill(raw, band, topic)
        if len(exercise["blanks"]) < _MIN_BLANKS:
            raise ValueError("Gap fill returned too few blanks.")
        return exercise
    exercise = _normalize_comprehension(raw, band, topic)
    if len(exercise["questions"]) < _MIN_QUESTIONS:
        raise ValueError("Comprehension returned too few questions.")
    return exercise


# ─── Scoring ──────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[A-Za-z']+")


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _TOKEN_RE.findall(text or "")]


def score_dictation(user_text: str, transcript: str) -> dict:
    """Return word-level diff + accuracy against transcript.

    diff items:
      - {"type": "correct", "text": <word>}
      - {"type": "wrong",   "text": <user_word>, "expected": <target_word>}
      - {"type": "missed",  "text": <target_word>}
      - {"type": "extra",   "text": <user_word>}
    """
    user = _tokenize(user_text)
    target = _tokenize(transcript)
    matcher = difflib.SequenceMatcher(None, user, target)

    diff: list[dict] = []
    correct = 0
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            for w in target[j1:j2]:
                diff.append({"type": "correct", "text": w})
                correct += 1
        elif op == "replace":
            span = max(i2 - i1, j2 - j1)
            for k in range(span):
                u = user[i1 + k] if i1 + k < i2 else ""
                t = target[j1 + k] if j1 + k < j2 else ""
                if u and t:
                    diff.append({"type": "wrong", "text": u, "expected": t})
                elif t:
                    diff.append({"type": "missed", "text": t})
                elif u:
                    diff.append({"type": "extra", "text": u})
        elif op == "delete":
            for w in user[i1:i2]:
                diff.append({"type": "extra", "text": w})
        elif op == "insert":
            for w in target[j1:j2]:
                diff.append({"type": "missed", "text": w})

    total = max(1, len(target))
    accuracy = correct / total
    misheard = sorted({
        item.get("expected") or item["text"]
        for item in diff
        if item["type"] in ("wrong", "missed")
    })
    return {
        "score": round(accuracy, 3),
        "diff": diff,
        "correct_count": correct,
        "total_count": len(target),
        "misheard_words": misheard,
    }


def score_gap_fill(user_answers: list[str], blanks: list[dict]) -> dict:
    per_blank: list[dict] = []
    correct = 0
    for i, blank in enumerate(blanks):
        target = _clean_str(blank.get("answer")).lower()
        raw_user = user_answers[i] if i < len(user_answers) else ""
        user = _clean_str(raw_user).lower()
        is_correct = user == target and bool(target)
        correct += int(is_correct)
        per_blank.append({
            "index": i,
            "user_answer": user,
            "correct_answer": target,
            "is_correct": is_correct,
        })
    total = max(1, len(blanks))
    return {
        "score": round(correct / total, 3),
        "per_blank": per_blank,
        "correct_count": correct,
        "total_count": len(blanks),
    }


def score_comprehension(user_indices: list[int], questions: list[dict]) -> dict:
    per_question: list[dict] = []
    correct = 0
    for i, q in enumerate(questions):
        raw_user = user_indices[i] if i < len(user_indices) else -1
        try:
            user_index = int(raw_user)
        except (TypeError, ValueError):
            user_index = -1
        correct_index = int(q.get("correct_index", 0))
        is_correct = user_index == correct_index
        correct += int(is_correct)
        per_question.append({
            "index": i,
            "user_index": user_index,
            "correct_index": correct_index,
            "is_correct": is_correct,
            "explanation_vi": q.get("explanation_vi", ""),
        })
    total = max(1, len(questions))
    return {
        "score": round(correct / total, 3),
        "per_question": per_question,
        "correct_count": correct,
        "total_count": len(questions),
    }

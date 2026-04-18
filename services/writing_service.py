import logging

from services import ai_service

logger = logging.getLogger(__name__)

_ALLOWED_ISSUE_TYPES = {"grammar", "weak_vocab", "good"}


def count_words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _round_half(value: float) -> float:
    return round(value * 2) / 2


def _clamp_score(value) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    score = max(4.0, min(9.0, score))
    return _round_half(score)


def _normalize_annotation(raw: dict) -> dict:
    issue_type = str(raw.get("issue_type", "grammar")).lower()
    if issue_type not in _ALLOWED_ISSUE_TYPES:
        issue_type = "grammar"
    try:
        paragraph_index = int(raw.get("paragraph_index", 0))
    except (TypeError, ValueError):
        paragraph_index = 0
    return {
        "paragraph_index": max(0, paragraph_index),
        "excerpt": str(raw.get("excerpt", "")).strip(),
        "issue_type": issue_type,
        "issue": str(raw.get("issue", "")).strip(),
        "suggestion": str(raw.get("suggestion", "")).strip(),
        "explanation_vi": str(raw.get("explanation_vi", "")).strip(),
    }


def normalize_feedback(raw: dict) -> dict:
    scores_raw = raw.get("scores") or {}
    scores = {
        "task_achievement": _clamp_score(scores_raw.get("task_achievement")),
        "coherence_cohesion": _clamp_score(scores_raw.get("coherence_cohesion")),
        "lexical_resource": _clamp_score(scores_raw.get("lexical_resource")),
        "grammatical_range_accuracy": _clamp_score(scores_raw.get("grammatical_range_accuracy")),
    }
    avg = sum(scores.values()) / 4.0
    overall = _round_half(raw.get("overall_band", avg))
    if overall <= 0:
        overall = _round_half(avg)

    criterion = raw.get("criterion_feedback") or {}
    criterion_feedback = {
        k: str(criterion.get(k, "")).strip()
        for k in scores
    }

    annotations = raw.get("paragraph_annotations") or []
    annotations = [_normalize_annotation(a) for a in annotations if isinstance(a, dict)]

    return {
        "overall_band": overall,
        "scores": scores,
        "criterion_feedback": criterion_feedback,
        "paragraph_annotations": annotations,
        "summary_vi": str(raw.get("summary_vi", "")).strip(),
    }


async def score_essay(text: str, task_type: str, prompt: str) -> dict:
    from prompts.writing_score_prompt import IELTS_SCORING_PROMPT

    filled = IELTS_SCORING_PROMPT.format(
        task_type=task_type, prompt=prompt or "(no prompt provided)", text=text,
    )
    raw = await ai_service.generate_json(filled, priority="foreground")
    return normalize_feedback(raw)


async def generate_task_prompt(task_type: str, band: float) -> str:
    from prompts.writing_score_prompt import TASK_PROMPT_GENERATOR

    filled = TASK_PROMPT_GENERATOR.format(task_type=task_type, band=band)
    text = await ai_service.generate(filled, priority="foreground")
    return text.strip()

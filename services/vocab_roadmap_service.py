from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from services import ai_service, firebase_service, public_vocab_pool_service
from services.srs_service import get_word_strength

MAX_RECOMMENDATIONS = 3
LOW_COVERAGE_WORDS = 20
LOW_MASTERY_RATIO = 0.5
MIN_CONSULT_WORDS = 10
MIN_CONSULT_REVIEWED_WORDS = 3
CONSULT_SAMPLE_WORD_LIMIT = 120
CONSULT_DUE_WORD_LIMIT = 50
CONSULT_DISCLAIMER = (
    "This is an AI study-readiness estimate from your app activity, "
    "not an official IELTS band score."
)
ALLOWED_ACTION_ROUTES = {
    "/learn/daily",
    "/learn/review",
    "/learn/vocab/add",
    "/learn/vocab/my-words",
    "/learn/pools",
}

logger = logging.getLogger(__name__)


class VocabConsultGenerationError(RuntimeError):
    """AI roadmap consult returned data that cannot satisfy the API schema."""


class _ConsultItem(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=420)
    evidence: str = Field(default="", max_length=240)


class _ConsultAction(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=420)
    route: str | None = Field(default=None, max_length=80)
    priority: Literal["high", "medium", "low"] = "medium"


class _AiConsultPayload(BaseModel):
    confidence: Literal["low", "medium", "high"]
    readiness_range: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=500)
    strengths: list[_ConsultItem] = Field(min_length=1, max_length=3)
    gaps: list[_ConsultItem] = Field(min_length=1, max_length=3)
    next_actions: list[_ConsultAction] = Field(min_length=1, max_length=4)


def target_difficulty_for_band(target_band: float) -> int:
    if target_band <= 5.5:
        return 1
    if target_band <= 6.0:
        return 2
    if target_band <= 7.0:
        return 3
    if target_band <= 7.5:
        return 4
    return 5


def _reason(code: str, topic: str | None = None) -> dict[str, str]:
    reason = {"code": code}
    if topic:
        reason["topic"] = topic
    return reason


def _first_intersection(left: set[str], right: set[str]) -> str | None:
    for item in sorted(left & right):
        return item
    return None


def _weak_topics_from_mastery(topic_counts: dict[str, dict[str, int]]) -> set[str]:
    weak = set()
    for topic, counts in topic_counts.items():
        total = int(counts.get("total") or 0)
        mastered = int(counts.get("mastered") or 0)
        if total > 0 and mastered / total < LOW_MASTERY_RATIO:
            weak.add(topic)
    return weak


def _low_coverage_topics(
    topic_counts: dict[str, dict[str, int]],
    preferred_topics: set[str],
) -> set[str]:
    candidates = preferred_topics or set(topic_counts)
    return {
        topic
        for topic in candidates
        if int((topic_counts.get(topic) or {}).get("total") or 0) < LOW_COVERAGE_WORDS
    }


def _weak_topics_from_due_words(due_words: list[dict]) -> set[str]:
    counts = Counter(
        str(word.get("topic") or "").strip()
        for word in due_words
        if str(word.get("topic") or "").strip()
    )
    return {topic for topic, count in counts.items() if count > 0}


def recommend_public_pools(
    user: dict,
    *,
    limit: int = MAX_RECOMMENDATIONS,
) -> dict[str, Any]:
    target_band = float(user.get("target_band") or 7.0)
    target_difficulty = target_difficulty_for_band(target_band)
    preferred_topics = {
        str(topic).strip()
        for topic in (user.get("topics") or [])
        if str(topic).strip()
    }

    pools = public_vocab_pool_service.list_public_pools()
    topic_counts = firebase_service.count_words_by_topic_with_mastery(user["id"])
    weak_due = firebase_service.get_due_words(user["id"], limit=50, status="Weak")

    weak_topics = (
        _weak_topics_from_mastery(topic_counts)
        | _weak_topics_from_due_words(weak_due)
    )
    low_coverage_topics = _low_coverage_topics(topic_counts, preferred_topics)
    has_progress = bool(topic_counts or weak_due or int(user.get("total_words") or 0) > 0)

    scored = []
    for pool in pools:
        pool_topics = set(pool.get("topics") or [])
        difficulty = pool.get("difficulty")
        reasons: list[dict[str, str]] = []
        score = 0

        if difficulty is not None:
            distance = abs(int(difficulty) - target_difficulty)
            if distance == 0:
                score += 50
                reasons.append(_reason("target_band_match"))
            elif distance == 1:
                score += 35
                reasons.append(_reason("near_target_band"))
            else:
                score -= distance * 10

        weak_topic = _first_intersection(pool_topics, weak_topics)
        if weak_topic:
            score += 30
            reasons.append(_reason("weak_topic", weak_topic))

        selected_topic = _first_intersection(pool_topics, preferred_topics)
        if selected_topic:
            score += 20
            reasons.append(_reason("selected_topic", selected_topic))

        low_coverage_topic = _first_intersection(pool_topics, low_coverage_topics)
        if low_coverage_topic:
            score += 15
            reasons.append(_reason("low_coverage", low_coverage_topic))

        if not reasons:
            if not has_progress:
                reasons.append(_reason("empty_progress_fallback"))
            else:
                reasons.append(_reason("target_band_fallback"))
            score += 5

        score += min(int(pool.get("word_count") or 0), 100) / 100
        scored.append((score, abs(int(difficulty or 5) - target_difficulty), pool["title"], pool, reasons))

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    items = [
        {**pool, "reasons": reasons}
        for _score, _distance, _title, pool, reasons in scored[:max(1, limit)]
    ]
    return {"target_difficulty": target_difficulty, "items": items}


def _reviewed_word_count(words: list[dict]) -> int:
    return sum(
        1
        for word in words
        if int(word.get("srs_reps") or 0) > 0
        or int(word.get("times_correct") or 0) > 0
        or int(word.get("times_incorrect") or 0) > 0
    )


def _strength_counts(words: list[dict]) -> dict[str, int]:
    counts = Counter(get_word_strength(word) for word in words)
    return {name: counts.get(name, 0) for name in ("New", "Weak", "Learning", "Good", "Mastered")}


def _topic_summaries(topic_counts: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    summaries = []
    for topic, counts in topic_counts.items():
        total = int(counts.get("total") or 0)
        mastered = int(counts.get("mastered") or 0)
        mastery_ratio = round(mastered / total, 2) if total else 0.0
        summaries.append({
            "topic": topic,
            "total": total,
            "mastered": mastered,
            "mastery_ratio": mastery_ratio,
        })
    return sorted(summaries, key=lambda item: (item["mastery_ratio"], -item["total"], item["topic"]))


def _due_topic_counts(due_words: list[dict]) -> dict[str, int]:
    counts = Counter(
        str(word.get("topic") or "uncategorized").strip() or "uncategorized"
        for word in due_words
    )
    return dict(counts.most_common(5))


def _missing_requirements(total_words: int, reviewed_words: int) -> list[dict[str, Any]]:
    missing = []
    if total_words < MIN_CONSULT_WORDS:
        missing.append({
            "code": "save_more_words",
            "current": total_words,
            "required": MIN_CONSULT_WORDS,
            "route": "/learn/vocab/add",
        })
    if reviewed_words < MIN_CONSULT_REVIEWED_WORDS:
        missing.append({
            "code": "review_more_words",
            "current": reviewed_words,
            "required": MIN_CONSULT_REVIEWED_WORDS,
            "route": "/learn/review",
        })
    return missing


def build_consult_context(user: dict) -> dict[str, Any]:
    """Collect a bounded evidence packet for the AI roadmap consult."""
    user_id = user["id"]
    target_band = float(user.get("target_band") or 7.0)
    words = firebase_service.get_user_vocabulary_page(
        user_id, CONSULT_SAMPLE_WORD_LIMIT, None, None, None, None,
    )
    total_words = firebase_service.count_user_vocabulary(user_id)
    topic_counts = firebase_service.count_words_by_topic_with_mastery(user_id)
    due_words = firebase_service.get_due_words(user_id, limit=CONSULT_DUE_WORD_LIMIT)
    weak_due_words = firebase_service.get_due_words(
        user_id, limit=CONSULT_DUE_WORD_LIMIT, status="Weak",
    )
    reviewed_words = _reviewed_word_count(words)
    recommendations = recommend_public_pools(user, limit=MAX_RECOMMENDATIONS)
    context = {
        "target_band": target_band,
        "target_difficulty": recommendations["target_difficulty"],
        "selected_topics": [
            str(topic).strip()
            for topic in (user.get("topics") or [])
            if str(topic).strip()
        ],
        "total_words": int(total_words or 0),
        "sampled_words": len(words),
        "reviewed_words": reviewed_words,
        "strength_counts": _strength_counts(words),
        "topic_summaries": _topic_summaries(topic_counts)[:8],
        "due_count": len(due_words),
        "weak_due_count": len(weak_due_words),
        "due_topic_counts": _due_topic_counts(due_words),
        "recommended_pools": [
            {
                "id": pool.get("id"),
                "title": pool.get("title"),
                "difficulty": pool.get("difficulty"),
                "topics": pool.get("topics") or [],
                "reasons": pool.get("reasons") or [],
            }
            for pool in recommendations["items"]
        ],
    }
    context["missing_requirements"] = _missing_requirements(
        context["total_words"], reviewed_words,
    )
    return context


def _data_used(context: dict[str, Any]) -> list[dict[str, str]]:
    topic_names = [
        item["topic"]
        for item in context.get("topic_summaries", [])[:3]
        if item.get("topic")
    ]
    pool_titles = [
        item["title"]
        for item in context.get("recommended_pools", [])[:3]
        if item.get("title")
    ]
    return [
        {"label": "Target band", "value": str(context.get("target_band", 7.0))},
        {
            "label": "My Words",
            "value": (
                f"{context.get('total_words', 0)} saved, "
                f"{context.get('reviewed_words', 0)} reviewed"
            ),
        },
        {
            "label": "Review queue",
            "value": (
                f"{context.get('due_count', 0)} due, "
                f"{context.get('weak_due_count', 0)} weak"
            ),
        },
        {"label": "Topics", "value": ", ".join(topic_names) if topic_names else "No topic data yet"},
        {"label": "Roadmap pools", "value": ", ".join(pool_titles) if pool_titles else "No pools available"},
    ]


def _insufficient_response(context: dict[str, Any]) -> dict[str, Any]:
    actions = []
    if any(item["code"] == "save_more_words" for item in context["missing_requirements"]):
        actions.append({
            "title": "Add more words to My Words",
            "detail": "Save words from daily study, public pools, or the AI add-word flow before asking for a deeper consult.",
            "route": "/learn/vocab/add",
            "priority": "high",
        })
    if any(item["code"] == "review_more_words" for item in context["missing_requirements"]):
        actions.append({
            "title": "Complete a few vocabulary reviews",
            "detail": "Review results tell the consult which words are actually weak, not just newly saved.",
            "route": "/learn/review",
            "priority": "high",
        })
    return {
        "status": "insufficient_data",
        "disclaimer": CONSULT_DISCLAIMER,
        "confidence": "low",
        "readiness_range": "",
        "summary": "There is not enough vocabulary activity yet to produce a useful AI roadmap consult.",
        "data_used": _data_used(context),
        "missing_requirements": context["missing_requirements"],
        "strengths": [],
        "gaps": [],
        "next_actions": actions,
    }


def _consult_prompt(context: dict[str, Any]) -> str:
    return (
        "You are an IELTS vocabulary coach. Use only the learner activity "
        "summary below. Do not claim this is an official IELTS score. "
        "Return JSON only with this exact shape: "
        "{"
        "\"confidence\":\"low|medium|high\","
        "\"readiness_range\":\"short non-official band readiness range like 6.0-6.5\","
        "\"summary\":\"1-2 sentences\","
        "\"strengths\":[{\"title\":\"...\",\"detail\":\"...\",\"evidence\":\"...\"}],"
        "\"gaps\":[{\"title\":\"...\",\"detail\":\"...\",\"evidence\":\"...\"}],"
        "\"next_actions\":[{\"title\":\"...\",\"detail\":\"...\",\"route\":\"/learn/review|/learn/vocab/add|/learn/vocab/my-words|/learn/pools|/learn/daily\",\"priority\":\"high|medium|low\"}]"
        "}. "
        "Base the answer on review history, My Words coverage, target band, "
        "and recommended public pools. Keep it practical and concise.\n\n"
        f"Activity summary:\n{json.dumps(context, ensure_ascii=False, default=str)}"
    )


def _sanitize_action_route(route: str | None) -> str | None:
    if route in ALLOWED_ACTION_ROUTES:
        return route
    return "/learn/review"


def _ready_response(context: dict[str, Any], raw: Any) -> dict[str, Any]:
    try:
        payload = _AiConsultPayload.model_validate(raw)
    except ValidationError as exc:
        raise VocabConsultGenerationError("Invalid vocab consult payload") from exc

    actions = [
        {**action.model_dump(), "route": _sanitize_action_route(action.route)}
        for action in payload.next_actions
    ]
    return {
        "status": "ready",
        "disclaimer": CONSULT_DISCLAIMER,
        "confidence": payload.confidence,
        "readiness_range": payload.readiness_range,
        "summary": payload.summary,
        "data_used": _data_used(context),
        "missing_requirements": [],
        "strengths": [item.model_dump() for item in payload.strengths],
        "gaps": [item.model_dump() for item in payload.gaps],
        "next_actions": actions,
    }


async def generate_vocab_consult(user: dict, *, charge_quota: bool = True) -> dict[str, Any]:
    """Return an AI roadmap consult, or deterministic next steps if data is thin."""
    context = build_consult_context(user)
    if context["missing_requirements"]:
        return _insufficient_response(context)

    if charge_quota:
        from services.admin import quota_service

        quota_service.check_and_increment(
            user_uid=str(user["id"]),
            feature="vocab_consult",
            plan=user.get("plan", "free"),
            quota_override=user.get("quota_override"),
        )

    raw = await ai_service.generate_json(
        _consult_prompt(context),
        plan=user.get("plan") or None,
        quality="premium",
    )
    try:
        return _ready_response(context, raw)
    except VocabConsultGenerationError:
        logger.warning("AI vocab consult failed schema validation: %r", raw)
        raise

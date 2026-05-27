from __future__ import annotations

from collections import Counter
from typing import Any

from services import firebase_service, public_vocab_pool_service

MAX_RECOMMENDATIONS = 3
LOW_COVERAGE_WORDS = 20
LOW_MASTERY_RATIO = 0.5


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

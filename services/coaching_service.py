"""Weekly AI coaching tips (US-5.3).

Wraps ai_service.generate_json with a tight JSON schema, a per-user/per-week
Firestore cache, and a deterministic fallback set of tips if the AI call
fails so the UI never renders empty.
"""

import logging
import re
from datetime import datetime, timezone

from services import ai_service, firebase_service

logger = logging.getLogger(__name__)

ALLOWED_SKILLS = {"vocabulary", "writing", "listening", "overall"}
ALLOWED_ROUTES = {"/review", "/vocab", "/write", "/listening"}
MAX_TIPS = 5
MIN_TIPS = 3
_SLUG_MAX_LEN = 40
# Leave room for a "-NN" suffix on the dedup path so truncation can't
# collapse a suffixed slug back onto the base and infinite-loop.
_SLUG_BASE_MAX_LEN = _SLUG_MAX_LEN - 3
_MAX_DEDUP_ATTEMPTS = 99

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def current_week_key(now: datetime | None = None) -> str:
    """Return the ISO week key (e.g. '2026-W16') in the app's local TZ sense.

    Uses UTC as a stable anchor — a user crossing into a new ISO week on
    Monday morning sees fresh tips within a few hours.
    """
    now = now or datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _slugify(value: str, default: str = "tip") -> str:
    cleaned = _SLUG_RE.sub("-", (value or "").lower()).strip("-")
    return (cleaned or default)[:_SLUG_BASE_MAX_LEN]


def _trend_summary(trend: list[dict]) -> str:
    if not trend:
        return "no data yet"
    sorted_trend = sorted(trend, key=lambda t: t.get("date", ""))
    first = sorted_trend[0]
    last = sorted_trend[-1]
    delta = (last.get("overall_band", 0) or 0) - (first.get("overall_band", 0) or 0)
    direction = "rising" if delta > 0 else "falling" if delta < 0 else "flat"
    return (
        f"{direction} (from {first.get('overall_band', 0):.1f} "
        f"on {first.get('date', '?')} to {last.get('overall_band', 0):.1f} "
        f"on {last.get('date', '?')})"
    )


def _normalize_tips(raw: dict) -> list[dict]:
    tips: list[dict] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(raw.get("tips") or []):
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill", "")).lower()
        if skill not in ALLOWED_SKILLS:
            skill = "overall"
        route = str(item.get("action_route", "")).strip()
        if route not in ALLOWED_ROUTES:
            # Fall back to a sensible per-skill default
            route = {
                "vocabulary": "/review",
                "writing": "/write",
                "listening": "/listening",
                "overall": "/review",
            }[skill]

        base_slug = _slugify(str(item.get("id") or f"{skill}-{i}"))
        slug = base_slug
        suffix = 2
        while slug in seen_ids and suffix <= _MAX_DEDUP_ATTEMPTS:
            slug = f"{base_slug}-{suffix}"[:_SLUG_MAX_LEN]
            suffix += 1
        if slug in seen_ids:
            # Last resort: append the item index so we never collide.
            slug = f"{base_slug}-i{i}"[:_SLUG_MAX_LEN]
        seen_ids.add(slug)

        tips.append({
            "id": slug,
            "skill": skill,
            "tip_en": str(item.get("tip_en") or "").strip(),
            "tip_vi": str(item.get("tip_vi") or "").strip(),
            "action_label": str(item.get("action_label") or "Mở").strip(),
            "action_route": route,
        })
        if len(tips) >= MAX_TIPS:
            break
    return tips


def _fallback_tips(snapshot: dict) -> list[dict]:
    """Deterministic tips used when the AI call fails."""
    skills = snapshot.get("skills") or {}
    target = snapshot.get("target_band", 7.0)
    gaps = [
        ("vocabulary", target - (skills.get("vocabulary") or {}).get("band", 0.0)),
        ("writing", target - (skills.get("writing") or {}).get("band", 0.0)),
        ("listening", target - (skills.get("listening") or {}).get("band", 0.0)),
    ]
    gaps.sort(key=lambda x: x[1], reverse=True)

    templates = {
        "vocabulary": {
            "tip_en": "Spend 10 minutes on SRS review — clearing due words is the fastest way to raise vocabulary band.",
            "tip_vi": "Dành 10 phút ôn thẻ SRS — đây là cách nhanh nhất nâng band Vocabulary.",
            "action_label": "Ôn từ ngay",
            "action_route": "/review",
        },
        "writing": {
            "tip_en": "Write one IELTS Task 2 essay this week to lift your writing band average.",
            "tip_vi": "Viết một bài Task 2 tuần này để kéo band Writing lên.",
            "action_label": "Luyện viết",
            "action_route": "/write",
        },
        "listening": {
            "tip_en": "Do one dictation exercise a day — it's the biggest needle-mover on listening accuracy.",
            "tip_vi": "Một bài dictation mỗi ngày là đòn bẩy lớn cho Listening.",
            "action_label": "Luyện nghe",
            "action_route": "/listening",
        },
    }

    tips = []
    for skill, _gap in gaps:
        t = templates[skill]
        tips.append({
            "id": f"fallback-{skill}",
            "skill": skill,
            **t,
        })
    return tips


async def generate_recommendations(
    user: dict,
    snapshot: dict,
    trend: list[dict],
) -> list[dict]:
    """Generate the week's tips via Gemini. Returns a normalised list."""
    from prompts.coaching_prompt import COACHING_PROMPT

    skills = snapshot.get("skills") or {}
    vocab = skills.get("vocabulary") or {}
    writing = skills.get("writing") or {}
    listening = skills.get("listening") or {}

    filled = COACHING_PROMPT.format(
        overall=snapshot.get("overall_band", 0.0),
        target=snapshot.get("target_band", 7.0),
        vocabulary=vocab.get("band", 0.0),
        total_words=vocab.get("total_words", 0),
        mastered=vocab.get("mastered_count", 0),
        writing=writing.get("band", 0.0),
        writing_samples=writing.get("sample_size", 0),
        listening=listening.get("band", 0.0),
        listening_samples=listening.get("sample_size", 0),
        trend_summary=_trend_summary(trend),
    )

    try:
        raw = await ai_service.generate_json(filled, priority="foreground")
    except Exception as exc:
        logger.warning("Coaching generation failed, using fallback: %s", exc)
        return _fallback_tips(snapshot)

    tips = _normalize_tips(raw)
    if len(tips) < MIN_TIPS:
        return _fallback_tips(snapshot)
    return tips


async def get_cached_or_generate(
    user: dict,
    snapshot: dict,
    trend: list[dict],
    *,
    now: datetime | None = None,
) -> tuple[str, list[dict], datetime | None]:
    """Return (week_key, tips, generated_at). Cached per user per ISO week."""
    import asyncio

    week_key = current_week_key(now)
    cached = await asyncio.to_thread(
        firebase_service.get_progress_recommendations, user["id"], week_key,
    )
    if cached and cached.get("tips"):
        return week_key, cached["tips"], cached.get("generated_at")

    tips = await generate_recommendations(user, snapshot, trend)
    data = {"tips": tips}
    await asyncio.to_thread(
        firebase_service.save_progress_recommendations,
        user["id"], week_key, data,
    )
    return week_key, tips, datetime.now(timezone.utc)

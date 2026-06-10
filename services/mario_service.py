"""Deterministic state builder for the Mario onboarding assistant."""

from __future__ import annotations

from api.models.mario import (
    MarioActionSuggestion,
    MarioChatMessage,
    MarioChatResponse,
    MarioGreeting,
    MarioStateResponse,
)
from services import ai_service, feature_flag_service

FLAG_NAME = "mario_onboarding"
APP_FEATURES = {
    "home": {
        "purpose": "Dashboard for choosing the next IELTS learning task.",
        "allowed_actions": [
            "Open Daily words from the quick actions.",
            "Open Review to practise due SRS cards.",
            "Open Writing, Reading, Listening, Progress, or Settings from navigation.",
            "Set target band if the profile prompt is visible.",
        ],
    },
    "daily": {
        "purpose": "Daily words page for learning today's personalized vocabulary set.",
        "allowed_actions": [
            "Read each daily word card with definition, IPA, part of speech, and examples.",
            "Use the pronunciation button on a word card.",
            "Open word detail from the eye icon.",
            "Favourite or unfavourite a word with the heart button.",
            "Set word strength with Weak, Learning, Good, or Mastered chips.",
            "Use Learn more / extra words when that section is visible.",
            "Open Review today's words after words are loaded and reviewable.",
            "Open flip mode from the Daily page.",
            "Open the vocabulary hub from the all-words link.",
        ],
        "forbidden_claims": [
            "Do not mention a Complete Lesson button.",
            "Do not say the learner can unlock the next lesson from this page.",
        ],
    },
    "review": {
        "purpose": "SRS review page for practising due vocabulary cards.",
        "allowed_actions": [
            "Review due flashcards.",
            "Use the visible card controls to answer or move through the review flow.",
            "Return to Daily words or the vocabulary hub from navigation if no cards are due.",
        ],
    },
    "vocab": {
        "purpose": "Vocabulary hub for managing saved words and vocabulary learning paths.",
        "allowed_actions": [
            "Browse saved vocabulary.",
            "Open Daily words, Review, public pools, or individual word detail pages.",
            "Use available add/search/filter controls only if they are visible.",
        ],
    },
    "write": {
        "purpose": "Writing practice page for IELTS Task 1 or Task 2 feedback.",
        "allowed_actions": [
            "Choose a writing task.",
            "Write or paste an answer.",
            "Submit for AI feedback when the submit control is visible.",
        ],
    },
    "listening": {
        "purpose": "Listening practice page for IELTS-style listening drills.",
        "allowed_actions": [
            "Start a listening session.",
            "Play audio when controls are visible.",
            "Submit answers and review feedback when the page offers it.",
        ],
    },
    "reading": {
        "purpose": "Reading lab for timed IELTS-style reading passages.",
        "allowed_actions": [
            "Start a reading passage.",
            "Answer questions in the reading session.",
            "Submit and review results when the page offers it.",
        ],
    },
    "progress": {
        "purpose": "Progress dashboard for seeing study history and weak areas.",
        "allowed_actions": [
            "Review progress summaries.",
            "Use weak areas to pick Daily words, Review, Writing, Reading, or Listening.",
        ],
    },
    "settings": {
        "purpose": "Settings page for profile, goals, practice preferences, plan, and privacy.",
        "allowed_actions": [
            "Update name, target band, goals, daily words count, timezone, or privacy settings.",
            "Open linked settings pages such as usage, groups, or Telegram linking when visible.",
        ],
    },
}
ROUTE_IDS = {
    "/learn/daily": "daily",
    "/learn/review": "review",
    "/learn/vocab": "vocab",
    "/practice/writing": "write",
    "/practice/listening": "listening",
    "/practice/reading": "reading",
    "/progress": "progress",
    "/settings": "settings",
    "/daily": "daily",
    "/review": "review",
    "/vocab": "vocab",
    "/write": "write",
    "/listening": "listening",
    "/reading": "reading",
}


def build_state(user: dict, route: str | None = None) -> MarioStateResponse:
    """Return the Mario V1 state for a user.

    The server is authoritative for rollout and durable onboarding
    dismissal. The client may still hide Mario for the current browser
    session without writing profile state.
    """
    if not is_enabled_for(user):
        return MarioStateResponse(enabled=False)

    normalized_route = _normalize_route(route)
    name = _first_name(user.get("name"))
    target_band = float(user.get("target_band") or 7.0)

    return MarioStateResponse(
        enabled=True,
        minimized=True,
        greeting=_greeting_for(normalized_route, name, target_band),
        suggestions=_suggestions_for(normalized_route, user),
    )


def is_enabled_for(user: dict) -> bool:
    uid = str(user["id"])
    return not bool(user.get("dismissed_onboarding")) and feature_flag_service.is_enabled(
        FLAG_NAME, uid,
    )


async def chat(
    user: dict,
    message: str,
    route: str | None = None,
    history: list[MarioChatMessage] | None = None,
) -> MarioChatResponse:
    """Return a short Mario chat reply grounded in the learner context."""
    normalized_route = _normalize_route(route)
    prompt = _chat_prompt(user, normalized_route, message, history or [])
    reply = (await ai_service.generate(
        prompt,
        plan=str(user.get("plan") or "free"),
        quality="cheap",
    )).strip()
    if not reply:
        reply = (
            "I can help you choose the next small IELTS step. "
            "Try review, daily words, or one focused practice task."
        )
    return MarioChatResponse(
        message=MarioChatMessage(role="assistant", content=reply[:1200])
    )


def _normalize_route(route: str | None) -> str:
    if not route:
        return "/"
    cleaned = route.split("?", 1)[0].split("#", 1)[0].strip()
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned.rstrip("/") or "/"


def _first_name(name: object) -> str:
    if not isinstance(name, str):
        return "there"
    first = name.strip().split(" ", 1)[0]
    return first or "there"


def _chat_prompt(
    user: dict,
    route: str,
    message: str,
    history: list[MarioChatMessage],
) -> str:
    route_id = _route_id(route) or "home"
    app_context = _app_context_for(route_id)
    user_context = _user_context_for(user, route, route_id)
    recent = "\n".join(
        f"{item.role}: {item.content}" for item in history[-6:]
    ) or "(no previous chat)"
    return f"""You are Mario, the in-app IELTS Coach assistant.

Your job:
- Help the learner understand and use this IELTS learning platform.
- Recommend only actions that exist in the application context below.
- Adapt advice to the learner context below.
- Keep replies concise, warm, practical, and under 120 words.
- Sound like a calm study coach. Do not use game catchphrases, fake accent, or "It's-a me" wording.
- Do not claim you completed actions. If an action is needed, tell the learner what to click.
- Never invent buttons, lessons, pages, scores, deadlines, or feature names.
- If the requested action is not in the application context, say you do not see that option here and suggest one allowed action.
- If the learner asks for IELTS study help, answer directly.

Learner context:
{user_context}

Application context:
{app_context}

Recent chat:
{recent}

Learner message:
{message}

Mario reply:"""


def _user_context_for(user: dict, route: str, route_id: str) -> str:
    fields = [
        f"- First name: {_first_name(user.get('name'))}",
        f"- Target band: {float(user.get('target_band') or 7.0)}",
        f"- Preferred locale: {user.get('preferred_locale') or 'unknown'}",
        f"- Plan: {user.get('plan') or 'free'}",
        f"- Daily words count preference: {int(user.get('daily_words_count') or 5)}",
        f"- Target band configured: {bool(user.get('target_band_set'))}",
        f"- Weekly goal configured: {bool(user.get('weekly_goal_set'))}",
        f"- Current app route: {route}",
        f"- Current route intent: {route_id}",
    ]
    return "\n".join(fields)


def _app_context_for(route_id: str) -> str:
    feature = APP_FEATURES.get(route_id) or APP_FEATURES["home"]
    allowed = "\n".join(
        f"- {action}" for action in feature["allowed_actions"]
    )
    forbidden = "\n".join(
        f"- {claim}" for claim in feature.get("forbidden_claims", [])
    )
    if forbidden:
        forbidden = f"\nForbidden claims on this route:\n{forbidden}"
    return (
        f"- Feature: {route_id}\n"
        f"- Purpose: {feature['purpose']}\n"
        f"- Allowed actions on this route:\n{allowed}"
        f"{forbidden}"
    )


def _greeting_for(route: str, name: str, target_band: float) -> MarioGreeting:
    route_id = _route_id(route)
    key = f"greeting.{route_id}" if route_id else "greeting.home"
    return MarioGreeting(
        key=key,
        params={"name": name, "target_band": target_band},
    )


def _suggestions_for(route: str, user: dict) -> list[MarioActionSuggestion]:
    route_suggestion = _route_suggestion(route)
    suggestions = [route_suggestion] if route_suggestion else []

    if not bool(user.get("target_band_set")):
        suggestions.append(_suggestion("set-target-band"))
    elif not bool(user.get("weekly_goal_set")):
        suggestions.append(_suggestion("set-weekly-goal"))
    else:
        suggestions.append(_suggestion("daily"))

    suggestions.append(_suggestion("review"))

    unique: list[MarioActionSuggestion] = []
    seen: set[str] = set()
    for suggestion in suggestions:
        if suggestion.id in seen:
            continue
        seen.add(suggestion.id)
        unique.append(suggestion)
    return unique[:3]


def _route_suggestion(route: str) -> MarioActionSuggestion | None:
    suggestion_id = _route_id(route)
    if suggestion_id is None:
        return None
    return _suggestion(suggestion_id)


def _route_id(route: str) -> str | None:
    for prefix, route_id in ROUTE_IDS.items():
        if route == prefix or route.startswith(f"{prefix}/"):
            return route_id
    return None


def _suggestion(suggestion_id: str) -> MarioActionSuggestion:
    data = {
        "daily": ("actions.dailyWords", "/learn/daily"),
        "review": ("actions.reviewDue", "/learn/review"),
        "vocab": ("actions.vocab", "/learn/vocab"),
        "write": ("actions.practiceWriting", "/practice/writing"),
        "listening": ("actions.practiceListening", "/practice/listening"),
        "reading": ("actions.readingLab", "/practice/reading"),
        "progress": ("actions.viewProgress", "/progress"),
        "settings": ("actions.settings", "/settings"),
        "set-target-band": ("actions.setTargetBand", "/settings#goals"),
        "set-weekly-goal": ("actions.setWeeklyGoal", "/settings#goals"),
    }[suggestion_id]
    return MarioActionSuggestion(
        id=suggestion_id,
        label_key=data[0],
        route=data[1],
    )

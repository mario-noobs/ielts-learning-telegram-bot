"""Deterministic state builder for the Mario onboarding assistant."""

from __future__ import annotations

from api.models.mario import (
    MarioActionSuggestion,
    MarioGreeting,
    MarioStateResponse,
)
from services import feature_flag_service

FLAG_NAME = "mario_onboarding"
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
    uid = str(user["id"])
    if user.get("dismissed_onboarding") or not feature_flag_service.is_enabled(
        FLAG_NAME, uid,
    ):
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

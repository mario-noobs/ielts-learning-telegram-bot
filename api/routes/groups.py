"""Group management endpoints (US-#227).

Web UI for managing IELTS-prep groups the user is in. Replaces the
"only the bot's `/groupsettings` command can edit settings" UX —
useful for users who joined groups via Telegram but prefer the web.

Permission rule: **only the group owner** can PATCH settings. Members
get the same detail payload but the frontend hides the save button
based on `role`. The PATCH route enforces server-side too (defense
in depth).

Owner identity = the Telegram id stamped on `groups/{id}.owner_telegram_id`
when the group was first registered. Pre-#227 groups have null
ownership — they show up read-only for every member.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends

from api.auth import get_current_user
from api.errors import ApiError, ERR
from api.models.group import GroupDetail, GroupSummary, GroupUpdate
from services import firebase_service

router = APIRouter(prefix="/api/v1", tags=["groups"])


def _telegram_id(user: dict) -> Optional[int]:
    """Return the Telegram id for a user dict, or None for web-only.

    Web-only rows have `id` like `web_<hex>` — not numeric. Those users
    can't be in any group (groups live entirely in Telegram), so they
    get an empty list / 404.
    """
    raw = str(user.get("id") or "")
    if not raw.isdigit():
        return None
    return int(raw)


def _summarize(group: dict, role: str) -> GroupSummary:
    return GroupSummary(
        id=str(group.get("id", "")),
        name=group.get("name"),
        member_count=int(group.get("member_count", 0)),
        role=role,
        default_band=float(group.get("default_band", 7.0)),
        topics=list(group.get("topics", []) or []),
        daily_time=group.get("daily_time"),
    )


def _detail(group: dict, role: str, member_count: int) -> GroupDetail:
    owner = group.get("owner_telegram_id")
    return GroupDetail(
        id=str(group.get("id", "")),
        name=group.get("name"),
        role=role,
        member_count=member_count,
        owner_telegram_id=int(owner) if owner is not None else None,
        default_band=float(group.get("default_band", 7.0)),
        topics=list(group.get("topics", []) or []),
        daily_time=group.get("daily_time"),
        challenge_time=group.get("challenge_time"),
        word_count=int(group.get("word_count", 10)),
        challenge_question_count=int(group.get("challenge_question_count", 5)),
        challenge_deadline_minutes=int(group.get("challenge_deadline_minutes", 60)),
    )


def _role_for(group: dict, telegram_id: int) -> str:
    owner = group.get("owner_telegram_id")
    if owner is not None and int(owner) == telegram_id:
        return "owner"
    return "member"


@router.get("/me/groups", response_model=list[GroupSummary])
async def list_my_groups(
    user: dict = Depends(get_current_user),
) -> list[GroupSummary]:
    tg_id = _telegram_id(user)
    if tg_id is None:
        return []

    groups = await asyncio.to_thread(
        firebase_service.list_groups_for_user, tg_id,
    )
    out: list[GroupSummary] = []
    for g in groups:
        members = await asyncio.to_thread(
            firebase_service.get_all_users_in_group, int(g["id"]),
        )
        merged = {**g, "member_count": len(members)}
        out.append(_summarize(merged, role=_role_for(g, tg_id)))
    return out


@router.get("/groups/{group_id}", response_model=GroupDetail)
async def get_group(
    group_id: int,
    user: dict = Depends(get_current_user),
) -> GroupDetail:
    tg_id = _telegram_id(user)
    if tg_id is None:
        raise ApiError(ERR.groups_not_member)

    group = await asyncio.to_thread(
        firebase_service.get_group_settings, group_id,
    )
    if not group:
        raise ApiError(ERR.groups_not_member)

    members = await asyncio.to_thread(
        firebase_service.get_all_users_in_group, group_id,
    )
    member_ids = {int(m["id"]) for m in members if str(m.get("id", "")).isdigit()}
    if tg_id not in member_ids:
        raise ApiError(ERR.groups_not_member)

    return _detail(
        {**group, "id": str(group_id)},
        role=_role_for(group, tg_id),
        member_count=len(members),
    )


@router.patch("/groups/{group_id}", response_model=GroupDetail)
async def update_group(
    group_id: int,
    body: GroupUpdate,
    user: dict = Depends(get_current_user),
) -> GroupDetail:
    tg_id = _telegram_id(user)
    if tg_id is None:
        raise ApiError(ERR.groups_not_member)

    group = await asyncio.to_thread(
        firebase_service.get_group_settings, group_id,
    )
    if not group:
        raise ApiError(ERR.groups_not_member)

    # Membership check first — a non-member who guesses an id should
    # see 404 (not 403), so we don't leak group existence to outsiders.
    members = await asyncio.to_thread(
        firebase_service.get_all_users_in_group, group_id,
    )
    member_ids = {int(m["id"]) for m in members if str(m.get("id", "")).isdigit()}
    if tg_id not in member_ids:
        raise ApiError(ERR.groups_not_member)

    if _role_for(group, tg_id) != "owner":
        raise ApiError(ERR.groups_forbidden_not_owner)

    # Build the partial update — Pydantic strips None for us via
    # `exclude_none`. Topics list is allowed to be empty (clearing).
    patch = body.model_dump(exclude_none=True)
    if "topics" in patch:
        patch["topics"] = [t.strip() for t in patch["topics"] if t and t.strip()]

    if patch:
        await asyncio.to_thread(
            firebase_service.update_group_settings, group_id, patch,
        )

    merged = {**group, **patch, "id": str(group_id)}
    return _detail(
        merged, role="owner", member_count=len(members),
    )

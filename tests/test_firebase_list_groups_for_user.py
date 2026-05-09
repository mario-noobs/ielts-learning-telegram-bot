"""Membership scan in `firebase_service.list_groups_for_user` (US-#227 fix).

Bug it covers: relying on ``users.group_id`` missed every user who
DM'd the bot first to /start, then joined a group later — group_id
stays NULL even though they're a real member of the group.

The fix walks ``groups/*`` and checks membership via
``get_all_users_in_group``. These tests pin that behaviour.
"""

from __future__ import annotations

from unittest.mock import patch

from services import firebase_service


def _group(gid: str, **extra) -> dict:
    payload: dict = {"id": gid}
    if gid.isdigit():
        payload["owner_telegram_id"] = int(gid)
    payload.update(extra)
    return payload


def test_returns_groups_where_user_is_member_even_if_group_id_null():
    """User has user.group_id=None but is in get_all_users_in_group(99) → list it."""
    target = 12345

    def fake_members(group_id: int):
        if group_id == 99:
            return [{"id": str(target)}, {"id": "99999"}]
        return [{"id": "11111"}]

    with patch.object(
        firebase_service, "get_all_groups",
        return_value=[_group("99"), _group("88")],
    ), patch.object(
        firebase_service, "get_all_users_in_group",
        side_effect=fake_members,
    ):
        out = firebase_service.list_groups_for_user(target)

    assert [g["id"] for g in out] == ["99"]


def test_returns_empty_when_user_is_member_of_no_group():
    target = 999
    with patch.object(
        firebase_service, "get_all_groups",
        return_value=[_group("99"), _group("88")],
    ), patch.object(
        firebase_service, "get_all_users_in_group",
        return_value=[{"id": "11111"}],
    ):
        out = firebase_service.list_groups_for_user(target)
    assert out == []


def test_skips_groups_with_malformed_id():
    """A group doc with a non-numeric id (legacy / corrupt) is skipped,
    not crashed. Other groups continue to be evaluated."""
    target = 7

    def fake_members(group_id: int):
        if group_id == 42:
            return [{"id": str(target)}]
        return []

    with patch.object(
        firebase_service, "get_all_groups",
        return_value=[_group("not-a-number"), _group("42")],
    ), patch.object(
        firebase_service, "get_all_users_in_group",
        side_effect=fake_members,
    ):
        out = firebase_service.list_groups_for_user(target)
    assert [g["id"] for g in out] == ["42"]

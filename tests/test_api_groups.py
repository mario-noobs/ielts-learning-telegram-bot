"""Group management API tests (US-#227).

Permission contract:
  * Non-member → 404 (don't leak existence to outsiders)
  * Member, not owner → 403 (you can see it, can't edit it)
  * Owner → 200, settings updated
  * Web-only user (no Telegram link) → empty list / 404
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app


GROUP_ID = 99999
OWNER_TG_ID = 12345
MEMBER_TG_ID = 67890
NON_MEMBER_TG_ID = 11111


def _user(uid: int | str) -> dict:
    return {"id": str(uid), "name": "Test", "target_band": 7.0, "topics": []}


def _group_dict() -> dict:
    return {
        "owner_telegram_id": OWNER_TG_ID,
        "default_band": 7.0,
        "topics": ["education", "environment"],
        "daily_time": "08:00",
        "challenge_time": "08:30",
        "word_count": 10,
        "challenge_question_count": 5,
        "challenge_deadline_minutes": 60,
    }


def _members() -> list[dict]:
    return [
        {"id": str(OWNER_TG_ID), "name": "Owner"},
        {"id": str(MEMBER_TG_ID), "name": "Member"},
    ]


def _make_client(user: dict) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_list_my_groups_returns_user_group_with_role():
    client = _make_client(_user(OWNER_TG_ID))
    with patch(
        "api.routes.groups.firebase_service.list_groups_for_user",
        return_value=[{"id": str(GROUP_ID), **_group_dict()}],
    ), patch(
        "api.routes.groups.firebase_service.get_all_users_in_group",
        return_value=_members(),
    ):
        resp = client.get("/api/v1/me/groups")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == str(GROUP_ID)
    assert body[0]["role"] == "owner"
    assert body[0]["member_count"] == 2


def test_list_my_groups_empty_for_web_only_user():
    """`web_xxx` IDs don't have Telegram → no groups."""
    client = _make_client({"id": "web_abc123", "name": "Web", "target_band": 7.0, "topics": []})
    resp = client.get("/api/v1/me/groups")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_group_404_when_not_member():
    client = _make_client(_user(NON_MEMBER_TG_ID))
    with patch(
        "api.routes.groups.firebase_service.get_group_settings",
        return_value=_group_dict(),
    ), patch(
        "api.routes.groups.firebase_service.get_all_users_in_group",
        return_value=_members(),
    ):
        resp = client.get(f"/api/v1/groups/{GROUP_ID}")
    # Non-members see 404, not 403 — don't leak group existence.
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "groups.not_member"


def test_get_group_member_sees_role_member():
    client = _make_client(_user(MEMBER_TG_ID))
    with patch(
        "api.routes.groups.firebase_service.get_group_settings",
        return_value=_group_dict(),
    ), patch(
        "api.routes.groups.firebase_service.get_all_users_in_group",
        return_value=_members(),
    ):
        resp = client.get(f"/api/v1/groups/{GROUP_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "member"
    assert body["owner_telegram_id"] == OWNER_TG_ID


def test_patch_403_when_member_tries_to_edit():
    client = _make_client(_user(MEMBER_TG_ID))
    with patch(
        "api.routes.groups.firebase_service.get_group_settings",
        return_value=_group_dict(),
    ), patch(
        "api.routes.groups.firebase_service.get_all_users_in_group",
        return_value=_members(),
    ), patch(
        "api.routes.groups.firebase_service.update_group_settings",
    ) as upd:
        resp = client.patch(
            f"/api/v1/groups/{GROUP_ID}",
            json={"default_band": 8.0},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "groups.forbidden_not_owner"
    upd.assert_not_called()


def test_patch_200_when_owner_updates():
    client = _make_client(_user(OWNER_TG_ID))
    with patch(
        "api.routes.groups.firebase_service.get_group_settings",
        return_value=_group_dict(),
    ), patch(
        "api.routes.groups.firebase_service.get_all_users_in_group",
        return_value=_members(),
    ), patch(
        "api.routes.groups.firebase_service.update_group_settings",
    ) as upd:
        resp = client.patch(
            f"/api/v1/groups/{GROUP_ID}",
            json={"default_band": 8.0, "topics": ["technology"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["default_band"] == 8.0
    assert body["topics"] == ["technology"]
    assert body["role"] == "owner"
    upd.assert_called_once_with(GROUP_ID, {
        "default_band": 8.0,
        "topics": ["technology"],
    })

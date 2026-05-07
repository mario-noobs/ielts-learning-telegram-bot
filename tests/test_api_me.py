"""Integration tests for GET / PATCH /api/v1/me (US-4.3, US-M11.3 fix)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {
    "id": "123",
    "name": "Alice",
    "email": "alice@example.com",
    "target_band": 7.0,
    "topics": ["environment"],
    "streak": 2,
    "total_words": 10,
    "total_quizzes": 0,
    "total_correct": 0,
    "challenge_wins": 0,
    "weekly_goal_minutes": 150,
}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: dict(FAKE_USER)
    return TestClient(app)


class TestGetMeAdminFields:
    """The /me response must surface the M11.1 admin fields so the web
    app's useProfile() hook can gate the /admin route subtree."""

    def test_defaults_when_user_doc_lacks_admin_fields(self, client):
        """Pre-M11 Firestore docs have no role/plan keys; defaults apply."""
        r = client.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "user"
        assert body["plan"] == "free"
        assert body["plan_expires_at"] is None
        assert body["team_id"] is None
        assert body["org_id"] is None
        assert body["quota_override"] is None

    def test_propagates_admin_fields_from_user_dict(self):
        """role / plan / quota_override on the user dict reach the response."""
        app = create_app()
        admin_user = {
            **FAKE_USER,
            "role": "platform_admin",
            "plan": "personal_pro",
            "plan_expires_at": "2027-01-01",
            "team_id": "team-uuid-1",
            "org_id": "org-uuid-2",
            "quota_override": 500,
        }
        app.dependency_overrides[get_current_user] = lambda: dict(admin_user)
        with TestClient(app) as c:
            r = c.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "platform_admin"
        assert body["plan"] == "personal_pro"
        assert body["plan_expires_at"] == "2027-01-01"
        assert body["team_id"] == "team-uuid-1"
        assert body["org_id"] == "org-uuid-2"
        assert body["quota_override"] == 500


class TestPatchMe:
    def test_sets_exam_date_and_weekly_goal(self, client):
        captured: dict = {}

        def upd(_uid, data):
            captured.update(data)

        with patch(
            "api.routes.auth.firebase_service.update_user",
            side_effect=upd,
        ):
            res = client.patch(
                "/api/v1/me",
                json={"exam_date": "2026-06-01", "weekly_goal_minutes": 210},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["exam_date"] == "2026-06-01"
        assert body["weekly_goal_minutes"] == 210
        assert captured["exam_date"] == "2026-06-01"
        assert captured["weekly_goal_minutes"] == 210

    def test_empty_string_clears_exam_date(self, client):
        captured: dict = {}

        def upd(_uid, data):
            captured.update(data)

        with patch(
            "api.routes.auth.firebase_service.update_user",
            side_effect=upd,
        ):
            res = client.patch("/api/v1/me", json={"exam_date": ""})
        assert res.status_code == 200
        assert res.json()["exam_date"] is None
        assert captured["exam_date"] is None

    def test_invalid_date_rejected(self, client):
        res = client.patch("/api/v1/me", json={"exam_date": "tomorrow"})
        assert res.status_code == 400

    def test_out_of_range_goal_rejected(self, client):
        res = client.patch("/api/v1/me", json={"weekly_goal_minutes": 5})
        assert res.status_code == 422

    def test_preferred_locale_round_trips(self, client):
        """US-M7.2: PATCH accepts + persists preferred_locale; /me returns it."""
        captured: dict = {}

        def upd(_uid, data):
            captured.update(data)

        with patch(
            "api.routes.auth.firebase_service.update_user",
            side_effect=upd,
        ):
            res = client.patch("/api/v1/me", json={"preferred_locale": "en"})
        assert res.status_code == 200
        assert res.json()["preferred_locale"] == "en"
        assert captured["preferred_locale"] == "en"

    def test_preferred_locale_rejects_invalid(self, client):
        res = client.patch("/api/v1/me", json={"preferred_locale": "fr"})
        assert res.status_code == 422

    def test_partial_update_leaves_other_fields(self, client):
        captured: dict = {}

        def upd(_uid, data):
            captured.update(data)

        with patch(
            "api.routes.auth.firebase_service.update_user",
            side_effect=upd,
        ):
            res = client.patch("/api/v1/me", json={"target_band": 8.0})
        assert res.status_code == 200
        body = res.json()
        assert body["target_band"] == 8.0
        # Unchanged fields still reflect original
        assert body["name"] == "Alice"
        assert "exam_date" not in captured

"""Integration tests for /api/v1/plan (US-4.1 + US-4.3 live exam updates)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {
    "id": "123",
    "name": "Alice",
    "target_band": 6.5,
    "topics": ["environment"],
    "total_words": 20,
}


def _client(user: dict | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: dict(user or FAKE_USER)
    return TestClient(app)


@pytest.fixture()
def client():
    return _client()


def _fake_weakness(**overrides) -> dict:
    base = {
        "due_srs_count": 4,
        "total_vocab": 20,
        "daily_words_done_today": False,
        "last_writing_band": 0.0,
        "writing_sample_size": 0,
        "last_listening_score": 0.0,
        "listening_sample_size": 0,
        "weakest_listening_type": "dictation",
        "streak": 0,
    }
    base.update(overrides)
    return base


class TestGetTodayPlan:
    def test_generates_and_caches(self, client):
        captured: dict = {}

        def save(_uid, _date, plan):
            captured["plan"] = plan

        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=None,
        ), patch(
            "api.routes.plan.weakness_service.build_weakness_profile",
            return_value=_fake_weakness(),
        ), patch(
            "api.routes.plan.firebase_service.save_daily_plan",
            side_effect=save,
        ):
            res = client.get("/api/v1/plan/today")

        assert res.status_code == 200
        body = res.json()
        assert 3 <= len(body["activities"]) <= 5
        assert body["total_minutes"] <= body["cap_minutes"]
        assert "plan" in captured
        assert body["activities"][0]["id"] == "srs_review"

    def test_returns_cached_when_present(self, client):
        stored = {
            "date": "2026-04-18",
            "activities": [
                {"id": "srs_review", "type": "srs_review", "title": "x",
                 "description": "", "estimated_minutes": 5, "route": "/review",
                 "meta": {}, "completed": True},
            ],
            "total_minutes": 5,
            "cap_minutes": 30,
            "exam_urgent": False,
            "days_until_exam": None,
            "completed_count": 1,
            "generated_at": datetime.now(timezone.utc),
        }
        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=stored,
        ):
            res = client.get("/api/v1/plan/today")
        assert res.status_code == 200
        body = res.json()
        assert body["completed_count"] == 1
        assert body["activities"][0]["completed"] is True

    def test_mid_day_exam_date_change_updates_countdown(self):
        """When the user sets an exam date after the plan is cached,
        the countdown fields should reflect the current profile, not the
        frozen copy in the plan doc."""
        stored = {
            "date": "2026-04-18",
            "activities": [],
            "total_minutes": 0,
            "cap_minutes": 30,
            "exam_urgent": False,
            "days_until_exam": None,
            "completed_count": 0,
            "generated_at": datetime.now(timezone.utc),
        }
        exam = (datetime.now(timezone.utc).date() + timedelta(days=12)).isoformat()
        user_with_exam = {**FAKE_USER, "exam_date": exam}
        client = _client(user_with_exam)
        with patch(
            "api.routes.plan.firebase_service.get_daily_plan",
            return_value=stored,
        ):
            res = client.get("/api/v1/plan/today")
        assert res.status_code == 200
        body = res.json()
        assert body["days_until_exam"] == 12
        assert body["exam_urgent"] is True


class TestCompleteActivity:
    def test_transactional_complete_marks_and_persists(self, client):
        updated_plan = {
            "date": "2026-04-18",
            "activities": [
                {"id": "a", "type": "writing", "title": "", "description": "",
                 "estimated_minutes": 10, "route": "/write", "meta": {},
                 "completed": False},
                {"id": "b", "type": "listening", "title": "", "description": "",
                 "estimated_minutes": 8, "route": "/listening", "meta": {},
                 "completed": True},
            ],
            "total_minutes": 18,
            "cap_minutes": 30,
            "completed_count": 1,
        }
        with patch(
            "api.routes.plan.firebase_service.complete_plan_activity",
            return_value=updated_plan,
        ):
            res = client.post("/api/v1/plan/today/complete/b")
        assert res.status_code == 200
        body = res.json()
        assert body["completed_count"] == 1
        assert body["activities"][1]["completed"] is True

    def test_missing_plan_returns_404(self, client):
        with patch(
            "api.routes.plan.firebase_service.complete_plan_activity",
            return_value=None,
        ):
            res = client.post("/api/v1/plan/today/complete/anything")
        assert res.status_code == 404

    def test_unknown_activity_returns_404(self, client):
        with patch(
            "api.routes.plan.firebase_service.complete_plan_activity",
            return_value="NOT_FOUND",
        ):
            res = client.post("/api/v1/plan/today/complete/ghost")
        assert res.status_code == 404

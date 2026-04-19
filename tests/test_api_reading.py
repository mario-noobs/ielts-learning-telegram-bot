"""Contract tests for /api/v1/reading (US-M9.2, #136)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app
from services import reading_service

FAKE_USER = {"id": "tester-1", "name": "Tester", "target_band": 7.0}


def test_reading_question_model_accepts_all_service_types():
    """Regression for the mismatch where the Literal listed 'matching'
    but the service + prompt use 'matching-headings' — POST /sessions
    500'd because pydantic rejected the AI-generated payload."""
    from api.models.reading import ReadingQuestion

    for qtype in ("mcq", "tfng", "gap-fill", "matching-headings"):
        ReadingQuestion(id="q1", type=qtype, stem="?")  # must not raise


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from services import rate_limit_service
    rate_limit_service._user_commands.clear()
    yield
    rate_limit_service._user_commands.clear()


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


class TestPassageList:
    def test_list_returns_summaries(self, client):
        res = client.get("/api/v1/reading/passages")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) >= 10, "seed corpus should have at least 10 passages"
        first = items[0]
        for key in ("id", "title", "topic", "band", "word_count", "attribution"):
            assert key in first
        assert "body" not in first, "list response must omit the body"

    def test_list_filters_by_band(self, client):
        res = client.get("/api/v1/reading/passages", params={"band": 5.5})
        assert res.status_code == 200
        items = res.json()["items"]
        assert items, "expected at least one band-5.5 passage"
        assert all(p["band"] == 5.5 for p in items)


class TestPassageDetail:
    def test_detail_returns_body(self, client):
        res = client.get("/api/v1/reading/passages/p001")
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == "p001"
        assert len(body["body"]) > 500, "body should be present and non-trivial"

    def test_detail_404_when_missing(self, client):
        res = client.get("/api/v1/reading/passages/p999")
        assert res.status_code == 404


class TestSessionLifecycle:
    def test_create_then_submit_happy_path(self, client):
        session_doc: dict = {}
        passage = reading_service.get_passage("p001")
        assert passage is not None, "p001 must be present for this test"
        stub_client, stub_key = reading_service.generate_question_set_stub(passage)

        def _save(uid, sid, data):
            session_doc.update({"id": sid, **data})

        def _get(uid, sid):
            return dict(session_doc) if session_doc.get("id") == sid else None

        def _update(uid, sid, data):
            session_doc.update(data)

        with patch(
            "services.reading_service.get_or_generate_questions",
            new=AsyncMock(return_value=(stub_client, stub_key)),
        ), patch("api.routes.reading.firebase_service.save_reading_session",
                 side_effect=_save), \
             patch("api.routes.reading.firebase_service.get_reading_session",
                   side_effect=_get), \
             patch("api.routes.reading.firebase_service.update_reading_session",
                   side_effect=_update):

            # Create
            r = client.post("/api/v1/reading/sessions",
                            json={"passage_id": "p001"})
            assert r.status_code == 201, r.text
            session = r.json()
            assert session["passage_id"] == "p001"
            assert session["status"] == "in_progress"
            assert len(session["questions"]) == 5
            sid = session["id"]

            # Submit with correct answers (all "o1" per stub)
            answers = {q["id"]: "o1" for q in session["questions"]}
            r = client.post(f"/api/v1/reading/sessions/{sid}/submit",
                            json={"answers": answers, "idempotency_key": "k1"})
            assert r.status_code == 200, r.text
            grade = r.json()["grade"]
            assert grade["correct"] == 5
            assert grade["total"] == 5
            assert grade["band"] >= 7.0
            # Explanations from the stub now surface per AC3
            assert all(
                "explanation" in pq for pq in grade["per_question"]
            )

    def test_submit_404_when_session_missing(self, client):
        with patch("api.routes.reading.firebase_service.get_reading_session",
                   return_value=None):
            r = client.post("/api/v1/reading/sessions/rs_nope/submit",
                            json={"answers": {}, "idempotency_key": "x"})
            assert r.status_code == 404

    def test_submit_idempotent_with_matching_key(self, client):
        now = datetime.now(timezone.utc)
        stored = {
            "id": "rs_abc",
            "passage_id": "p001",
            "status": "submitted",
            "started_at": now,
            "expires_at": now + timedelta(minutes=20),
            "submitted_at": now,
            "idempotency_key": "same-key",
            "grade": {
                "correct": 3, "total": 5, "band": 6.0,
                "per_question": [],
            },
        }
        with patch("api.routes.reading.firebase_service.get_reading_session",
                   return_value=stored):
            r = client.post("/api/v1/reading/sessions/rs_abc/submit",
                            json={"answers": {}, "idempotency_key": "same-key"})
            assert r.status_code == 200
            assert r.json()["grade"]["correct"] == 3

    def test_submit_conflict_without_matching_key(self, client):
        now = datetime.now(timezone.utc)
        stored = {
            "id": "rs_abc", "passage_id": "p001", "status": "submitted",
            "started_at": now, "expires_at": now + timedelta(minutes=20),
            "submitted_at": now, "idempotency_key": "orig",
            "grade": {"correct": 0, "total": 5, "band": 3.0, "per_question": []},
        }
        with patch("api.routes.reading.firebase_service.get_reading_session",
                   return_value=stored):
            r = client.post("/api/v1/reading/sessions/rs_abc/submit",
                            json={"answers": {}, "idempotency_key": "different"})
            assert r.status_code == 409

    def test_submit_410_when_expired(self, client):
        now = datetime.now(timezone.utc)
        stored = {
            "id": "rs_old", "passage_id": "p001", "status": "in_progress",
            "started_at": now - timedelta(hours=1),
            "expires_at": now - timedelta(minutes=30),
            "submitted_at": None, "grade": None, "idempotency_key": None,
            "questions": [], "answer_key": [],
        }
        with patch("api.routes.reading.firebase_service.get_reading_session",
                   return_value=stored), \
             patch("api.routes.reading.firebase_service.update_reading_session"):
            r = client.post("/api/v1/reading/sessions/rs_old/submit",
                            json={"answers": {}, "idempotency_key": "k"})
            assert r.status_code == 410

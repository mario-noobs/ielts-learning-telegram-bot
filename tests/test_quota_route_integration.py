"""Integration test: enforce_ai_quota fires through the route layer (US-M11.2)."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.errors import ERR
from api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping route-layer quota integration test",
)


# A real-world-ish caller: no plan/quota_override on the dict, so the
# dep falls back to plan='free' (quota=10/day, seeded by M11.1).
FAKE_USER = {"id": "u-quota-int", "name": "Q", "target_band": 7.0, "topics": []}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def _mc_question(i: int, word_id: str) -> dict:
    return {
        "type": "multiple_choice",
        "question": f"Q{i}",
        "options": ["A", "B", "C", "D"],
        "correct_index": 0,
        "word_id": word_id,
        "explanation": "—",
    }


def test_post_quiz_start_429s_after_free_quota_exhausted(client) -> None:
    """11 POSTs as the same user: 10 succeed, 11th gets 429 with the
    contract-shaped quota.daily_exceeded error."""
    questions = [_mc_question(i, f"w-{i}") for i in range(5)]

    with patch(
        "api.routes.quiz.quiz_service.generate_quiz_batch",
        new=AsyncMock(return_value=questions),
    ), patch("api.routes.quiz.firebase_service.save_quiz_session"):
        for i in range(10):
            r = client.post("/api/v1/quiz/start", json={"count": 5})
            assert r.status_code == 200, f"call {i + 1} should succeed but got {r.status_code}"

        r = client.post("/api/v1/quiz/start", json={"count": 5})
        assert r.status_code == 429
        body = r.json()
        assert body["error"]["code"] == ERR.quota_daily_exceeded.code
        assert body["error"]["params"]["feature"] == "quiz"
        assert body["error"]["params"]["plan_quota"] == 10
        assert body["error"]["params"]["used"] == 11

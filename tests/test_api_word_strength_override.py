"""Manual mastery override (US-#231).

Verifies:
  - Owner can set Mastered → SRS state lifted to 30d/5 reps
  - "Don't roll back quiz progress" rule: Good clicked when already
    past Mastered tier (60d) → no-op, applied=False
  - Weak override always applies, even when current is higher
  - Rate limit: 31st override in a day → 429
  - Non-existent word_id → 404
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app
from api.routes import words as words_route


FAKE_USER = {"id": "12345", "name": "Test", "auth_uid": "auth-12345"}
WORD_ID = "w-abc"


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Drop the per-user rate-limit log between tests."""
    words_route._override_log.clear()
    yield
    words_route._override_log.clear()


@pytest.fixture(autouse=True)
def _stub_streak_update():
    with patch("api.routes.words.firebase_service.update_streak"):
        yield


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def _word(strength_state: dict) -> dict:
    base = {"id": WORD_ID, "word": "ubiquitous", "topic": "education"}
    return {**base, **strength_state}


def test_mastered_override_lifts_srs_state(client):
    """Word at Weak (interval=1, reps=0) → set Mastered → 30d/5 reps."""
    before = _word({"srs_interval": 1, "srs_reps": 0})
    after_state = {"srs_interval": 30, "srs_reps": 5,
                    "srs_next_review": datetime(2026, 6, 9, tzinfo=timezone.utc)}
    after = _word(after_state)

    with patch(
        "api.routes.words.word_service.firebase_service.get_word_by_id",
        return_value=before,
    ), patch(
        "api.routes.words.word_service.set_word_strength_manual",
        return_value=after,
    ):
        resp = client.patch(
            f"/api/v1/words/{WORD_ID}/strength",
            json={"strength": "Mastered"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["strength"] == "Mastered"
    assert body["strength_applied"] is True
    assert body["srs_interval"] == 30
    assert body["srs_reps"] == 5
    assert body["srs_next_review"] is not None


def test_web_user_can_override_strength():
    app = create_app()
    web_user = {"id": "web_abc", "name": "Web", "auth_uid": "firebase-abc"}
    app.dependency_overrides[get_current_user] = lambda: web_user
    web_client = TestClient(app)

    before = _word({"srs_interval": 1, "srs_reps": 0})
    after = _word({
        "srs_interval": 30,
        "srs_reps": 5,
        "srs_next_review": datetime(2026, 6, 9, tzinfo=timezone.utc),
    })

    with patch(
        "api.routes.words.word_service.firebase_service.get_word_by_id",
        return_value=before,
    ) as get_word, patch(
        "api.routes.words.word_service.set_word_strength_manual",
        return_value=after,
    ) as set_strength:
        resp = web_client.patch(
            f"/api/v1/words/{WORD_ID}/strength",
            json={"strength": "Mastered"},
        )

    assert resp.status_code == 200
    get_word.assert_called_once_with("web_abc", WORD_ID)
    set_strength.assert_called_once_with("web_abc", WORD_ID, "Mastered")


def test_no_op_when_target_below_current_progress(client):
    """User clicks Good but they're already past Mastered (60d).
    State should not change; applied=False."""
    before = _word({"srs_interval": 60, "srs_reps": 7})
    # set_word_strength_manual returns the same dict unchanged.
    with patch(
        "api.routes.words.word_service.firebase_service.get_word_by_id",
        return_value=before,
    ), patch(
        "api.routes.words.word_service.set_word_strength_manual",
        return_value=before,
    ):
        resp = client.patch(
            f"/api/v1/words/{WORD_ID}/strength",
            json={"strength": "Good"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["strength_applied"] is False
    assert body["srs_interval"] == 60


def test_weak_target_always_applies(client):
    """Even when current tier is Mastered, choosing Weak is an
    intentional reset and DOES roll the SRS state back."""
    before = _word({"srs_interval": 60, "srs_reps": 7})
    after = _word({"srs_interval": 1, "srs_reps": 0,
                    "srs_next_review": datetime(2026, 5, 10, tzinfo=timezone.utc)})

    with patch(
        "api.routes.words.word_service.firebase_service.get_word_by_id",
        return_value=before,
    ), patch(
        "api.routes.words.word_service.set_word_strength_manual",
        return_value=after,
    ):
        resp = client.patch(
            f"/api/v1/words/{WORD_ID}/strength",
            json={"strength": "Weak"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["strength_applied"] is True
    assert body["srs_interval"] == 1


def test_rate_limit_31st_request_returns_429(client):
    """Pre-fill the rate-limit log with 30 entries, 31st should 429."""
    import time
    now = time.monotonic()
    for _ in range(30):
        words_route._override_log[FAKE_USER["auth_uid"]].append(now)

    resp = client.patch(
        f"/api/v1/words/{WORD_ID}/strength",
        json={"strength": "Mastered"},
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "vocab.override_rate_limited"


def test_404_when_word_missing(client):
    with patch(
        "api.routes.words.word_service.firebase_service.get_word_by_id",
        return_value=None,
    ):
        resp = client.patch(
            f"/api/v1/words/{WORD_ID}/strength",
            json={"strength": "Good"},
        )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "vocab.word_not_found"

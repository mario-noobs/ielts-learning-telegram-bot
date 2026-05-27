from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app


FAKE_USER = {"id": "test-user-1", "name": "Alice", "target_band": 7.0}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def _word_doc(**overrides):
    doc = {
        "id": "w1",
        "word": "resilience",
        "definition": "ability to recover",
        "definition_vi": "khả năng phục hồi",
        "ipa": "/rɪˈzɪliəns/",
        "part_of_speech": "noun",
        "topic": "society",
        "source": 3,
        "srs_interval": 1,
        "srs_ease": 2.5,
        "srs_reps": 0,
        "srs_next_review": datetime(2026, 5, 27, tzinfo=timezone.utc),
    }
    doc.update(overrides)
    return doc


def test_due_review_forwards_my_words_filters(client):
    with patch("api.routes.review.firebase_service.get_due_words",
               return_value=[_word_doc()]) as mock_due:
        response = client.post("/api/v1/review/due", json={
            "limit": 10,
            "source": "manual",
            "topic": "society",
            "status": "New",
        })

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["source"] == "manual"
    assert body["items"][0]["topic"] == "society"
    mock_due.assert_called_once_with("test-user-1", 10, 3, "society", "New")


def test_due_review_accepts_public_pool_source(client):
    with patch("api.routes.review.firebase_service.get_due_words",
               return_value=[_word_doc(source=5)]) as mock_due:
        response = client.post("/api/v1/review/due", json={
            "limit": 10,
            "source": "public_pool",
        })

    assert response.status_code == 200
    assert response.json()["items"][0]["source"] == "public_pool"
    mock_due.assert_called_once_with("test-user-1", 10, 5, None, None)


def test_due_review_rejects_invalid_source(client):
    response = client.post("/api/v1/review/due", json={"source": "unknown"})

    assert response.status_code == 400


def test_rate_returns_status_change_summary(client):
    before = _word_doc(srs_reps=0, srs_interval=1)
    after = _word_doc(srs_reps=1, srs_interval=3)
    with patch("api.routes.review.firebase_service.get_word_by_id",
               side_effect=[before, after]), \
         patch("api.routes.review.firebase_service.update_word_srs") as update:
        response = client.post("/api/v1/review/rate", json={
            "word_id": "w1",
            "rating": "good",
        })

    assert response.status_code == 200
    body = response.json()
    assert body["old_strength"] == "New"
    assert body["new_strength"] == "Learning"
    assert body["strength_change"] is True
    update.assert_called_once()

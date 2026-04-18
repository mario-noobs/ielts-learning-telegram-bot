"""Integration tests for /api/v1/writing (US-2.1)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {"id": "123", "name": "Alice", "target_band": 7.0, "topics": []}

ESSAY_TEXT = (
    "Many people argue that technology has greatly improved education over the "
    "past decade. In my view, while digital tools expand access to knowledge, "
    "they also create new distractions for learners."
)


def _ai_feedback() -> dict:
    return {
        "overall_band": 6.5,
        "scores": {
            "task_achievement": 6.5,
            "coherence_cohesion": 6.0,
            "lexical_resource": 6.5,
            "grammatical_range_accuracy": 6.5,
        },
        "criterion_feedback": {
            "task_achievement": "Addresses the prompt with a clear position.",
            "coherence_cohesion": "Paragraphing is adequate but linking words could improve.",
            "lexical_resource": "Some good vocabulary; a few repeated words.",
            "grammatical_range_accuracy": "Mostly accurate with minor tense errors.",
        },
        "paragraph_annotations": [
            {
                "paragraph_index": 0,
                "excerpt": "technology has greatly improved",
                "issue_type": "weak_vocab",
                "issue": "Vague verb",
                "suggestion": "technology has transformed",
                "explanation_vi": "Dùng động từ mạnh hơn để thể hiện thay đổi lớn.",
            }
        ],
        "summary_vi": "Bài viết đạt yêu cầu cơ bản. Cần cải thiện liên kết câu và đa dạng từ vựng.",
    }


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


class TestSubmit:
    def test_submit_returns_scores_and_annotations(self, client):
        submission_id = "sub123"
        stored = {
            "id": submission_id, "text": ESSAY_TEXT, "task_type": "task2",
            "prompt": "", "word_count": 30,
            "created_at": datetime.now(timezone.utc), **_ai_feedback(),
        }
        with patch("api.routes.writing.writing_service.score_essay",
                   new=AsyncMock(return_value=_ai_feedback())), \
             patch("api.routes.writing.firebase_service.save_writing_submission",
                   return_value=submission_id), \
             patch("api.routes.writing.firebase_service.get_writing_submission",
                   return_value=stored):
            res = client.post(
                "/api/v1/writing/submit",
                json={"text": ESSAY_TEXT, "task_type": "task2", "prompt": ""},
            )

        assert res.status_code == 200
        body = res.json()
        assert body["overall_band"] == 6.5
        assert body["scores"]["task_achievement"] == 6.5
        assert len(body["paragraph_annotations"]) == 1
        assert body["paragraph_annotations"][0]["issue_type"] == "weak_vocab"
        assert body["word_count"] == 30

    def test_short_essay_rejected(self, client):
        res = client.post(
            "/api/v1/writing/submit",
            json={"text": "Too short.", "task_type": "task2", "prompt": ""},
        )
        assert res.status_code == 400

    def test_invalid_task_type_rejected(self, client):
        res = client.post(
            "/api/v1/writing/submit",
            json={"text": ESSAY_TEXT, "task_type": "task5", "prompt": ""},
        )
        assert res.status_code == 422


class TestHistoryAndDetail:
    def test_history_returns_chronological(self, client):
        now = datetime.now(timezone.utc)
        docs = [
            {"id": "s2", "task_type": "task2", "prompt": "Topic B", "text": "…",
             "overall_band": 7.0, "word_count": 260, "created_at": now},
            {"id": "s1", "task_type": "task1", "prompt": "Topic A", "text": "…",
             "overall_band": 6.0, "word_count": 170, "created_at": now},
        ]
        with patch("api.routes.writing.firebase_service.list_writing_submissions",
                   return_value=docs):
            res = client.get("/api/v1/writing/history")
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 2
        assert items[0]["id"] == "s2"
        assert items[0]["prompt_preview"].startswith("Topic B")

    def test_detail_returns_full(self, client):
        stored = {
            "id": "s1", "text": ESSAY_TEXT, "task_type": "task2", "prompt": "",
            "word_count": 30, "created_at": datetime.now(timezone.utc),
            **_ai_feedback(),
        }
        with patch("api.routes.writing.firebase_service.get_writing_submission",
                   return_value=stored):
            res = client.get("/api/v1/writing/s1")
        assert res.status_code == 200
        assert res.json()["id"] == "s1"

    def test_detail_missing_returns_404(self, client):
        with patch("api.routes.writing.firebase_service.get_writing_submission",
                   return_value=None):
            res = client.get("/api/v1/writing/nope")
        assert res.status_code == 404


class TestRevise:
    def test_revision_carries_delta(self, client):
        original = {
            "id": "s1", "text": ESSAY_TEXT, "task_type": "task2",
            "prompt": "Topic A", "word_count": 30, "overall_band": 6.0,
            **_ai_feedback(),
        }
        new_id = "s2"
        improved = {**_ai_feedback(), "overall_band": 7.0,
                    "scores": {**_ai_feedback()["scores"], "task_achievement": 7.0}}
        stored_revised = {
            "id": new_id, "text": ESSAY_TEXT, "task_type": "task2",
            "prompt": "Topic A", "word_count": 30,
            "created_at": datetime.now(timezone.utc),
            "original_id": "s1", "delta_band": 1.0, **improved,
        }

        def get_stub(_uid, sub_id):
            return original if sub_id == "s1" else stored_revised

        with patch("api.routes.writing.writing_service.score_essay",
                   new=AsyncMock(return_value=improved)), \
             patch("api.routes.writing.firebase_service.get_writing_submission",
                   side_effect=get_stub), \
             patch("api.routes.writing.firebase_service.save_writing_submission",
                   return_value=new_id):
            res = client.post(
                "/api/v1/writing/s1/revise",
                json={"text": ESSAY_TEXT},
            )

        assert res.status_code == 200
        body = res.json()
        assert body["original_id"] == "s1"
        assert body["delta_band"] == 1.0
        assert body["overall_band"] == 7.0

    def test_revise_missing_original_returns_404(self, client):
        with patch("api.routes.writing.firebase_service.get_writing_submission",
                   return_value=None):
            res = client.post(
                "/api/v1/writing/nope/revise",
                json={"text": ESSAY_TEXT},
            )
        assert res.status_code == 404


class TestPrompt:
    def test_generates_task_prompt(self, client):
        with patch("api.routes.writing.writing_service.generate_task_prompt",
                   new=AsyncMock(return_value="Some topic to write about.")):
            res = client.post(
                "/api/v1/writing/prompt", json={"task_type": "task2"},
            )
        assert res.status_code == 200
        assert res.json()["prompt"].startswith("Some topic")

"""Integration tests for /api/v1/quiz endpoints (US-1.2)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {"id": "u1", "name": "Alice", "target_band": 7.0, "topics": []}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


def _mc_question(i: int, word_id: str) -> dict:
    return {
        "type": "multiple_choice",
        "question": f"Q{i}: what does x mean?",
        "options": ["A-opt", "B-opt", "C-opt", "D-opt"],
        "correct_index": 2,
        "word_id": word_id,
        "explanation": "Because.",
    }


class TestStartQuiz:
    def test_ac1_returns_batch_with_unique_word_ids(self, client):
        """AC1: user with ≥5 words gets 5 questions with unique word_ids."""
        questions = [_mc_question(i, f"word-{i}") for i in range(5)]
        with patch("api.routes.quiz.quiz_service.generate_quiz_batch",
                   new=AsyncMock(return_value=questions)), \
             patch("api.routes.quiz.firebase_service.save_quiz_session") as save:
            response = client.post("/api/v1/quiz/start", json={"count": 5})

        assert response.status_code == 200
        body = response.json()
        assert len(body["questions"]) == 5
        assert body["session_id"]
        word_ids = {q["word_id"] for q in body["questions"]}
        assert len(word_ids) == 5
        # Sanitized: no correct_index exposed
        assert "correct_index" not in body["questions"][0]
        save.assert_called_once()

    def test_ac3_returns_400_when_not_enough_words(self, client):
        """AC3: <5 words → 400 with clear error."""
        with patch("api.routes.quiz.quiz_service.generate_quiz_batch",
                   new=AsyncMock(return_value=None)):
            response = client.post("/api/v1/quiz/start", json={"count": 5})
        assert response.status_code == 400
        # Error shape changed in US-M7.3: prose `detail` → `{error: {code, params}}`.
        # Legacy routes still raise HTTPException(detail=...); the main.py
        # bridge stashes the message in params.message.
        body = response.json()
        assert body["error"]["code"] == "common.validation"
        assert "Add more words" in body["error"]["params"]["message"]

    def test_default_count_applied(self, client):
        """No count in body → falls back to default."""
        questions = [_mc_question(i, f"w{i}") for i in range(5)]
        with patch("api.routes.quiz.quiz_service.generate_quiz_batch",
                   new=AsyncMock(return_value=questions)) as mock_gen, \
             patch("api.routes.quiz.firebase_service.save_quiz_session"):
            response = client.post("/api/v1/quiz/start", json={})

        assert response.status_code == 200
        kwargs = mock_gen.call_args.kwargs
        assert kwargs["count"] == 5


class TestAnswerQuiz:
    def _session_fixture(self) -> dict:
        q = _mc_question(0, "word-0")
        q["id"] = "q0"
        return {"questions": [q], "answered_ids": []}

    def test_ac2_correct_answer_advances_srs(self, client):
        """AC2: correct MC answer → is_correct=true + SRS interval advances."""
        session = self._session_fixture()
        old_word = {
            "id": "word-0", "word": "aber", "srs_interval": 1, "srs_reps": 0,
            "srs_ease": 2.5, "times_correct": 0, "times_incorrect": 0,
        }
        new_word = {
            **old_word, "srs_interval": 6, "srs_reps": 1, "times_correct": 1,
            "srs_next_review": datetime(2026, 4, 23, tzinfo=timezone.utc),
        }

        with patch("api.routes.quiz.firebase_service.get_quiz_session",
                   return_value=session), \
             patch("api.routes.quiz.firebase_service.get_word_by_id",
                   side_effect=[old_word, new_word]), \
             patch("api.routes.quiz.quiz_service.check_answer",
                   new=AsyncMock(return_value=(True, "✅ Correct!"))), \
             patch("api.routes.quiz.firebase_service.mark_session_question_answered"):
            response = client.post(
                "/api/v1/quiz/answer",
                json={"session_id": "s1", "question_id": "q0", "answer": "C"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["is_correct"] is True
        assert body["feedback"].startswith("✅")
        assert body["srs_update"]["next_review"] is not None
        assert body["srs_update"]["strength_change"] is True

    def test_incorrect_answer_returns_feedback(self, client):
        session = self._session_fixture()
        word = {"id": "word-0", "srs_interval": 1, "times_correct": 0}
        with patch("api.routes.quiz.firebase_service.get_quiz_session",
                   return_value=session), \
             patch("api.routes.quiz.firebase_service.get_word_by_id",
                   return_value=word), \
             patch("api.routes.quiz.quiz_service.check_answer",
                   new=AsyncMock(return_value=(False, "❌ Wrong. Answer: C."))), \
             patch("api.routes.quiz.firebase_service.mark_session_question_answered"):
            response = client.post(
                "/api/v1/quiz/answer",
                json={"session_id": "s1", "question_id": "q0", "answer": "A"},
            )

        assert response.status_code == 200
        assert response.json()["is_correct"] is False

    def test_numeric_index_is_normalized_to_letter(self, client):
        session = self._session_fixture()
        with patch("api.routes.quiz.firebase_service.get_quiz_session",
                   return_value=session), \
             patch("api.routes.quiz.firebase_service.get_word_by_id",
                   return_value={"id": "word-0"}), \
             patch("api.routes.quiz.quiz_service.check_answer",
                   new=AsyncMock(return_value=(True, "ok"))) as check, \
             patch("api.routes.quiz.firebase_service.mark_session_question_answered"):
            response = client.post(
                "/api/v1/quiz/answer",
                json={"session_id": "s1", "question_id": "q0", "answer": "2"},
            )

        assert response.status_code == 200
        passed_answer = check.call_args.args[1]
        assert passed_answer == "C"

    def test_404_for_missing_session(self, client):
        with patch("api.routes.quiz.firebase_service.get_quiz_session",
                   return_value=None):
            response = client.post(
                "/api/v1/quiz/answer",
                json={"session_id": "missing", "question_id": "q0", "answer": "A"},
            )
        assert response.status_code == 404

    def test_404_for_unknown_question_id(self, client):
        session = self._session_fixture()
        with patch("api.routes.quiz.firebase_service.get_quiz_session",
                   return_value=session):
            response = client.post(
                "/api/v1/quiz/answer",
                json={"session_id": "s1", "question_id": "q99", "answer": "A"},
            )
        assert response.status_code == 404

    def test_409_for_duplicate_answer(self, client):
        session = self._session_fixture()
        session["answered_ids"] = ["q0"]
        with patch("api.routes.quiz.firebase_service.get_quiz_session",
                   return_value=session):
            response = client.post(
                "/api/v1/quiz/answer",
                json={"session_id": "s1", "question_id": "q0", "answer": "A"},
            )
        assert response.status_code == 409

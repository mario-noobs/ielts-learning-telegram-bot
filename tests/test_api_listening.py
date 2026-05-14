"""Integration tests for /api/v1/listening (US-3.2, US-M15.6)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {
    "id": "123",
    "name": "Alice",
    "target_band": 6.5,
    "topics": ["environment"],
}


def _dictation_doc(exercise_id: str) -> dict:
    return {
        "id": exercise_id,
        "exercise_type": "dictation",
        "band": 6.5,
        "topic": "environment",
        "title": "Clean Rivers",
        "transcript": "The river flows quickly through the valley.",
        "display_text": "",
        "blanks": [],
        "questions": [],
        "duration_estimate_sec": 18,
        "created_at": datetime.now(timezone.utc),
    }


def _gap_fill_doc(exercise_id: str) -> dict:
    return {
        "id": exercise_id,
        "exercise_type": "gap_fill",
        "band": 6.5,
        "topic": "environment",
        "title": "Wind Energy",
        "transcript": "Wind turbines generate renewable energy efficiently.",
        "display_text": "Wind _____ generate _____ energy efficiently.",
        "blanks": [
            {"index": 0, "answer": "turbines"},
            {"index": 1, "answer": "renewable"},
            {"index": 2, "answer": "efficiently"},
        ],
        "questions": [],
        "duration_estimate_sec": 15,
        "created_at": datetime.now(timezone.utc),
    }


def _comp_doc(exercise_id: str) -> dict:
    return {
        "id": exercise_id,
        "exercise_type": "comprehension",
        "band": 6.5,
        "topic": "environment",
        "title": "Coral Reefs",
        "transcript": "Coral reefs support marine biodiversity.",
        "display_text": "",
        "blanks": [],
        "questions": [
            {
                "question": "What do coral reefs support?",
                "options": ["Industry", "Biodiversity", "Tourism", "Fisheries"],
                "correct_index": 1,
                "explanation_vi": "San hô hỗ trợ đa dạng sinh học biển.",
            },
            {
                "question": "Are reefs found inland?",
                "options": ["Yes", "No", "Sometimes", "Unclear"],
                "correct_index": 1,
                "explanation_vi": "San hô chỉ có trong lòng biển.",
            },
        ],
        "duration_estimate_sec": 20,
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


class TestGenerate:
    def test_generate_dictation_hides_transcript(self, client):
        exercise_id = "ex1"
        stored = _dictation_doc(exercise_id)
        with patch(
            "api.routes.listening.listening_service.generate_exercise",
            new=AsyncMock(return_value={
                "exercise_type": "dictation",
                "band": 6.5,
                "topic": "environment",
                "title": "Clean Rivers",
                "transcript": stored["transcript"],
                "display_text": "",
                "blanks": [],
                "questions": [],
                "duration_estimate_sec": 18,
            }),
        ), patch(
            "api.routes.listening.tts_service.generate_passage_audio",
            return_value="/tmp/fake.mp3",
        ), patch(
            "api.routes.listening.firebase_service.save_listening_exercise",
            return_value=exercise_id,
        ), patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ):
            res = client.post(
                "/api/v1/listening/generate",
                json={"exercise_type": "dictation", "topic": "environment"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == exercise_id
        assert body["audio_url"].endswith(f"/{exercise_id}/audio")
        assert "transcript" not in body
        assert body["submitted"] is False

    def test_generate_comprehension_strips_correct_index(self, client):
        exercise_id = "ex2"
        stored = _comp_doc(exercise_id)
        with patch(
            "api.routes.listening.listening_service.generate_exercise",
            new=AsyncMock(return_value=stored),
        ), patch(
            "api.routes.listening.tts_service.generate_passage_audio",
            return_value="/tmp/fake.mp3",
        ), patch(
            "api.routes.listening.firebase_service.save_listening_exercise",
            return_value=exercise_id,
        ), patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ):
            res = client.post(
                "/api/v1/listening/generate",
                json={"exercise_type": "comprehension"},
            )
        assert res.status_code == 200
        body = res.json()
        assert len(body["questions"]) == 2
        for q in body["questions"]:
            assert "correct_index" not in q
            assert "explanation_vi" not in q

    def test_invalid_type_rejected(self, client):
        res = client.post(
            "/api/v1/listening/generate",
            json={"exercise_type": "speaking"},
        )
        assert res.status_code == 422


class TestSubmit:
    def test_submit_dictation_returns_diff(self, client):
        exercise_id = "ex1"
        stored = _dictation_doc(exercise_id)
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ), patch(
            "api.routes.listening.firebase_service.update_listening_exercise",
            return_value=None,
        ):
            res = client.post(
                f"/api/v1/listening/{exercise_id}/submit",
                json={"user_text": "The river flows slowly through the valley"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["exercise_type"] == "dictation"
        assert body["submitted"] is True
        assert 0 < body["score"] < 1
        assert body["transcript"] == stored["transcript"]
        wrong = [d for d in body["dictation_diff"] if d["type"] == "wrong"]
        assert any(d["expected"] == "quickly" for d in wrong)
        assert "quickly" in body["misheard_words"]

    def test_submit_gap_fill_returns_per_blank(self, client):
        exercise_id = "ex2"
        stored = _gap_fill_doc(exercise_id)
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ), patch(
            "api.routes.listening.firebase_service.update_listening_exercise",
            return_value=None,
        ):
            res = client.post(
                f"/api/v1/listening/{exercise_id}/submit",
                json={"answers": ["turbines", "renewable", "efficient"]},
            )
        assert res.status_code == 200
        body = res.json()
        assert len(body["gap_fill_results"]) == 3
        assert body["gap_fill_results"][0]["is_correct"] is True
        assert body["gap_fill_results"][2]["is_correct"] is False
        assert body["score"] == round(2 / 3, 3)

    def test_submit_comprehension_counts_correct(self, client):
        exercise_id = "ex3"
        stored = _comp_doc(exercise_id)
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ), patch(
            "api.routes.listening.firebase_service.update_listening_exercise",
            return_value=None,
        ):
            res = client.post(
                f"/api/v1/listening/{exercise_id}/submit",
                json={"answers": ["1", "1"]},
            )
        assert res.status_code == 200
        body = res.json()
        assert body["score"] == 1.0
        assert all(r["is_correct"] for r in body["comprehension_results"])

    def test_submit_missing_exercise_returns_404(self, client):
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=None,
        ):
            res = client.post(
                "/api/v1/listening/nope/submit",
                json={"user_text": "hello"},
            )
        assert res.status_code == 404


class TestHistoryAndDetail:
    def test_history_returns_chronological(self, client):
        now = datetime.now(timezone.utc)
        docs = [
            {"id": "b", "exercise_type": "gap_fill", "title": "B",
             "band": 6.5, "score": 0.8, "submitted": True, "created_at": now},
            {"id": "a", "exercise_type": "dictation", "title": "A",
             "band": 6.5, "score": None, "submitted": False, "created_at": now},
        ]
        with patch(
            "api.routes.listening.firebase_service.list_listening_exercises",
            return_value=docs,
        ):
            res = client.get("/api/v1/listening/history")
        assert res.status_code == 200
        body = res.json()
        assert len(body["items"]) == 2
        assert body["items"][0]["id"] == "b"
        assert body["items"][0]["submitted"] is True

    def test_detail_pre_submit_hides_transcript_and_answers(self, client):
        exercise_id = "ex9"
        stored = _comp_doc(exercise_id)
        stored["submitted"] = False
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ):
            res = client.get(f"/api/v1/listening/{exercise_id}")
        assert res.status_code == 200
        body = res.json()
        assert body["transcript"] == ""
        assert body["submitted"] is False
        # Options still exposed so the UI can render the question
        assert body["questions"][0]["options"] == stored["questions"][0]["options"]
        # But answer keys are hidden
        assert body["questions"][0]["correct_index"] == -1
        assert body["questions"][0]["explanation_vi"] == ""

    def test_detail_post_submit_returns_full(self, client):
        exercise_id = "ex9"
        stored = _comp_doc(exercise_id)
        stored["submitted"] = True
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ):
            res = client.get(f"/api/v1/listening/{exercise_id}")
        assert res.status_code == 200
        body = res.json()
        assert body["transcript"] == stored["transcript"]
        assert len(body["questions"]) == 2
        assert body["questions"][0]["correct_index"] == 1

    def test_detail_pre_submit_hides_gap_fill_answers(self, client):
        exercise_id = "ex10"
        stored = _gap_fill_doc(exercise_id)
        stored["submitted"] = False
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ):
            res = client.get(f"/api/v1/listening/{exercise_id}")
        assert res.status_code == 200
        body = res.json()
        assert body["transcript"] == ""
        assert body["display_text"] == stored["display_text"]
        assert len(body["blanks"]) == 3
        assert all(b["answer"] == "" for b in body["blanks"])

    def test_detail_missing_returns_404(self, client):
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=None,
        ):
            res = client.get("/api/v1/listening/nope")
        assert res.status_code == 404


class TestResubmit:
    def test_resubmit_returns_409(self, client):
        exercise_id = "ex1"
        stored = _dictation_doc(exercise_id)
        stored["submitted"] = True
        stored["score"] = 0.9
        with patch(
            "api.routes.listening.firebase_service.get_listening_exercise",
            return_value=stored,
        ):
            res = client.post(
                f"/api/v1/listening/{exercise_id}/submit",
                json={"user_text": "anything"},
            )
        assert res.status_code == 409


_FAKE_TIPS_JSON = {
    "tips": [
        {"id": "tip_1", "title": "Preview before listening", "body": "Read questions first.", "category": "strategy"},
        {"id": "tip_2", "title": "Learn topic vocabulary", "body": "Expand your **academic** word list.", "category": "vocabulary"},
        {"id": "tip_3", "title": "Train connected speech", "body": "English speakers link words:\n- gonna\n- wanna", "category": "pronunciation"},
        {"id": "tip_4", "title": "Anticipate answer types", "body": "Note whether you need a name, date, or number.", "category": "exam_technique"},
        {"id": "tip_5", "title": "Stay calm under pressure", "body": "If you miss an answer, move on immediately.", "category": "mindset"},
    ]
}


class TestTips:
    def setup_method(self):
        # Clear the module-level cache before each test to avoid cross-test pollution.
        import api.routes.listening as _m
        _m._tips_cache.clear()

    def test_happy_path_returns_5_tips(self, client):
        with patch(
            "api.routes.listening.ai_service.generate_json",
            new=AsyncMock(return_value=_FAKE_TIPS_JSON),
        ):
            res = client.get("/api/v1/listening/tips?locale=en")
        assert res.status_code == 200
        body = res.json()
        assert len(body["tips"]) == 5
        categories = {t["category"] for t in body["tips"]}
        assert categories == {"strategy", "vocabulary", "pronunciation", "exam_technique", "mindset"}

    def test_tips_schema_valid(self, client):
        with patch(
            "api.routes.listening.ai_service.generate_json",
            new=AsyncMock(return_value=_FAKE_TIPS_JSON),
        ):
            res = client.get("/api/v1/listening/tips?locale=en")
        body = res.json()
        for tip in body["tips"]:
            assert "id" in tip
            assert "title" in tip
            assert "body" in tip
            assert "category" in tip

    def test_rate_limit_with_cached_fallback_returns_200(self, client):
        from services.ai_service import RateLimitError

        # Prime the cache with a successful response.
        with patch(
            "api.routes.listening.ai_service.generate_json",
            new=AsyncMock(return_value=_FAKE_TIPS_JSON),
        ):
            client.get("/api/v1/listening/tips?locale=en")

        # Second call triggers RateLimitError — should return cached version.
        with patch(
            "api.routes.listening.ai_service.generate_json",
            new=AsyncMock(side_effect=RateLimitError()),
        ):
            res = client.get("/api/v1/listening/tips?locale=en&fresh=true")
        assert res.status_code == 200
        assert len(res.json()["tips"]) == 5

    def test_rate_limit_without_cache_returns_503(self, client):
        from services.ai_service import RateLimitError

        with patch(
            "api.routes.listening.ai_service.generate_json",
            new=AsyncMock(side_effect=RateLimitError()),
        ):
            res = client.get("/api/v1/listening/tips?locale=en")
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "ai.rate_limited"

    def test_vi_locale_accepted(self, client):
        with patch(
            "api.routes.listening.ai_service.generate_json",
            new=AsyncMock(return_value=_FAKE_TIPS_JSON),
        ):
            res = client.get("/api/v1/listening/tips?locale=vi")
        assert res.status_code == 200

    def test_invalid_locale_rejected(self, client):
        res = client.get("/api/v1/listening/tips?locale=fr")
        assert res.status_code == 422

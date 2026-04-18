"""Unit tests for services/listening_service.py (US-3.1)."""

from unittest.mock import AsyncMock, patch

import pytest

from services import listening_service


class TestTokenizeAndDiff:
    def test_score_dictation_all_correct(self):
        target = "The cat sat on the mat."
        user = "the cat sat on the mat"
        result = listening_service.score_dictation(user, target)
        assert result["score"] == 1.0
        assert result["correct_count"] == 6
        assert result["misheard_words"] == []
        assert all(d["type"] == "correct" for d in result["diff"])

    def test_score_dictation_wrong_word(self):
        target = "I went to the park yesterday."
        user = "I went to the store yesterday"
        result = listening_service.score_dictation(user, target)
        wrong = [d for d in result["diff"] if d["type"] == "wrong"]
        assert len(wrong) == 1
        assert wrong[0]["text"] == "store"
        assert wrong[0]["expected"] == "park"
        assert "park" in result["misheard_words"]

    def test_score_dictation_missed_word(self):
        target = "She quickly ran home."
        user = "she ran home"
        result = listening_service.score_dictation(user, target)
        missed = [d for d in result["diff"] if d["type"] == "missed"]
        assert len(missed) == 1
        assert missed[0]["text"] == "quickly"
        assert result["score"] < 1.0

    def test_score_dictation_extra_word(self):
        target = "Let us go."
        user = "let us really go"
        result = listening_service.score_dictation(user, target)
        extra = [d for d in result["diff"] if d["type"] == "extra"]
        assert any(e["text"] == "really" for e in extra)


class TestGapFillScoring:
    def test_all_correct(self):
        blanks = [
            {"index": 0, "answer": "environment"},
            {"index": 1, "answer": "sustainable"},
        ]
        result = listening_service.score_gap_fill(
            ["ENVIRONMENT", "Sustainable"], blanks,
        )
        assert result["score"] == 1.0
        assert result["correct_count"] == 2

    def test_partial_and_missing(self):
        blanks = [
            {"index": 0, "answer": "renewable"},
            {"index": 1, "answer": "emissions"},
            {"index": 2, "answer": "climate"},
        ]
        result = listening_service.score_gap_fill(
            ["renewable", "emmisions"], blanks,
        )
        assert result["correct_count"] == 1
        assert result["score"] == round(1 / 3, 3)
        assert result["per_blank"][1]["is_correct"] is False
        assert result["per_blank"][2]["user_answer"] == ""


class TestComprehensionScoring:
    def test_mixed_results(self):
        questions = [
            {"correct_index": 2, "explanation_vi": "A"},
            {"correct_index": 0, "explanation_vi": "B"},
            {"correct_index": 1, "explanation_vi": "C"},
        ]
        result = listening_service.score_comprehension([2, 1, 1], questions)
        assert result["correct_count"] == 2
        assert result["per_question"][0]["is_correct"] is True
        assert result["per_question"][1]["is_correct"] is False

    def test_missing_answers_treated_as_wrong(self):
        questions = [{"correct_index": 0}, {"correct_index": 0}]
        result = listening_service.score_comprehension([], questions)
        assert result["correct_count"] == 0
        assert result["per_question"][0]["user_index"] == -1


class TestGenerateExerciseDispatch:
    @pytest.mark.asyncio
    async def test_dictation_normalizes_transcript(self):
        with patch(
            "services.listening_service.ai_service.generate_json",
            new=AsyncMock(return_value={
                "title": "Coffee Mornings",
                "transcript": "  Many people drink coffee every morning.  ",
            }),
        ):
            result = await listening_service.generate_exercise(
                "dictation", 6.5, "food",
            )
        assert result["exercise_type"] == "dictation"
        assert result["transcript"] == "Many people drink coffee every morning."
        assert result["title"] == "Coffee Mornings"
        assert result["duration_estimate_sec"] >= 8

    @pytest.mark.asyncio
    async def test_gap_fill_too_few_blanks_raises(self):
        with patch(
            "services.listening_service.ai_service.generate_json",
            new=AsyncMock(return_value={
                "transcript": "A short passage.",
                "display_text": "A _____ passage.",
                "blanks": [{"answer": "short"}],
            }),
        ):
            with pytest.raises(ValueError):
                await listening_service.generate_exercise("gap_fill", 6.0, "travel")

    @pytest.mark.asyncio
    async def test_gap_fill_normalizes_indices(self):
        with patch(
            "services.listening_service.ai_service.generate_json",
            new=AsyncMock(return_value={
                "transcript": "X Y Z W V.",
                "display_text": "_____ _____ _____ _____ _____.",
                "blanks": [
                    {"answer": "x"}, {"answer": "y"}, {"answer": "z"},
                    {"answer": "w"}, {"answer": "v"},
                ],
            }),
        ):
            result = await listening_service.generate_exercise(
                "gap_fill", 7.0, "science",
            )
        assert [b["index"] for b in result["blanks"]] == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_comprehension_clamps_correct_index(self):
        with patch(
            "services.listening_service.ai_service.generate_json",
            new=AsyncMock(return_value={
                "transcript": "A short passage about bees.",
                "questions": [
                    {
                        "question": "Q1",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 99,
                        "explanation_vi": "e1",
                    },
                    {
                        "question": "Q2",
                        "options": ["A", "B", "C", "D"],
                        "correct_index": 2,
                        "explanation_vi": "e2",
                    },
                ],
            }),
        ):
            result = await listening_service.generate_exercise(
                "comprehension", 6.5, "nature",
            )
        assert result["questions"][0]["correct_index"] == 3
        assert result["questions"][1]["correct_index"] == 2

    @pytest.mark.asyncio
    async def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            await listening_service.generate_exercise("speaking", 6.5, "food")

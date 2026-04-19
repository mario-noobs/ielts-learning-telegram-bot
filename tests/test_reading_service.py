"""Unit tests for services/reading_service.py (US-M9.3, #137)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import reading_service


# ─── Fixtures ────────────────────────────────────────────────────────

SAMPLE_BODY = (
    "Regular exercise helps the heart work more efficiently. Doctors "
    "recommend at least thirty minutes of activity each day. Walking, "
    "cycling, and swimming are all good choices. People who exercise "
    "regularly tend to sleep better at night and feel calmer during "
    "the day. Experts agree that enjoyment matters more than intensity."
)


def _valid_question_set(body: str = SAMPLE_BODY) -> list[dict]:
    """Return a payload that passes validate_question_set."""
    questions: list[dict] = []

    # 4 gap-fill
    for i, (stem, ans) in enumerate([
        ("Doctors recommend at least ___ minutes of activity each day.", "thirty"),
        ("People who exercise regularly tend to ___ better at night.", "sleep"),
        ("Experts agree that ___ matters more than intensity.", "enjoyment"),
        ("Regular exercise helps the ___ work more efficiently.", "heart"),
    ], start=1):
        questions.append({
            "id": f"q{i}",
            "type": "gap-fill",
            "stem": stem,
            "answer": ans,
            "passage_span": {"start": 0, "end": min(200, len(body))},
            "explanation": f"The passage states: '{stem}'",
        })

    # 4 tfng
    for i, (stem, ans) in enumerate([
        ("Regular exercise helps the heart.", "TRUE"),
        ("The passage recommends two hours of exercise per day.", "FALSE"),
        ("Exercise is only beneficial for young people.", "NOT_GIVEN"),
        ("Walking is considered a form of exercise in the passage.", "TRUE"),
    ], start=5):
        questions.append({
            "id": f"q{i}",
            "type": "tfng",
            "stem": stem,
            "answer": ans,
            "passage_span": {"start": 0, "end": min(200, len(body))},
            "explanation": f"Grounded in '{stem[:40]}...'",
        })

    # 3 matching-headings
    headings = ["Benefits for the heart", "Mental benefits of exercise", "Recommended daily activity"]
    for i, heading in enumerate(headings, start=9):
        questions.append({
            "id": f"q{i}",
            "type": "matching-headings",
            "stem": f"Which paragraph best matches the heading: \"{heading}\"?",
            "options": [
                {"id": "o1", "text": "Paragraph 1"},
                {"id": "o2", "text": "Paragraph 2"},
                {"id": "o3", "text": "Paragraph 3"},
                {"id": "o4", "text": "Paragraph 4"},
            ],
            "answer": "o1",
            "passage_span": {"start": 0, "end": min(150, len(body))},
            "explanation": "Paragraph 1 discusses the heading.",
        })

    # 2 mcq
    for i, stem in enumerate([
        "Which of the following is NOT mentioned as a benefit?",
        "According to the passage, the key to exercise is:",
    ], start=12):
        questions.append({
            "id": f"q{i}",
            "type": "mcq",
            "stem": stem,
            "options": [
                {"id": "o1", "text": "better sleep"},
                {"id": "o2", "text": "being calmer"},
                {"id": "o3", "text": "winning competitions"},
                {"id": "o4", "text": "enjoyment over intensity"},
            ],
            "answer": "o3" if "NOT" in stem else "o4",
            "passage_span": {"start": 0, "end": min(200, len(body))},
            "explanation": "The passage emphasises enjoyment.",
        })

    return questions


# ─── validate_question_set ────────────────────────────────────────────


class TestValidation:
    def test_valid_set_passes(self):
        reading_service.validate_question_set(_valid_question_set(), SAMPLE_BODY)

    def test_wrong_count_rejected(self):
        qs = _valid_question_set()[:12]
        with pytest.raises(reading_service.QuestionGenerationError,
                           match="expected 13"):
            reading_service.validate_question_set(qs, SAMPLE_BODY)

    def test_wrong_distribution_rejected(self):
        qs = _valid_question_set()
        # Replace a gap-fill with an mcq → 3 gap-fill instead of 4
        qs[0] = {**qs[0], "type": "mcq", "options": [
            {"id": "o1", "text": "a"}, {"id": "o2", "text": "b"},
            {"id": "o3", "text": "c"}, {"id": "o4", "text": "d"},
        ], "answer": "o1"}
        with pytest.raises(reading_service.QuestionGenerationError,
                           match="distribution"):
            reading_service.validate_question_set(qs, SAMPLE_BODY)

    def test_out_of_range_span_rejected(self):
        qs = _valid_question_set()
        qs[0]["passage_span"] = {"start": 0, "end": 99_999}
        with pytest.raises(reading_service.QuestionGenerationError,
                           match="passage_span out of range"):
            reading_service.validate_question_set(qs, SAMPLE_BODY)

    def test_mcq_answer_must_match_an_option(self):
        qs = _valid_question_set()
        qs[11]["answer"] = "o99"  # not in options
        with pytest.raises(reading_service.QuestionGenerationError,
                           match="does not match any option"):
            reading_service.validate_question_set(qs, SAMPLE_BODY)

    def test_tfng_answer_enum_enforced(self):
        qs = _valid_question_set()
        qs[4]["answer"] = "MAYBE"
        with pytest.raises(reading_service.QuestionGenerationError,
                           match="tfng answer must be one of"):
            reading_service.validate_question_set(qs, SAMPLE_BODY)


# ─── generate_question_set_ai ────────────────────────────────────────


class TestAIGeneration:
    @pytest.mark.asyncio
    async def test_happy_path_splits_client_and_key(self):
        passage = {"id": "p_test", "title": "Test", "band": 7.0, "body": SAMPLE_BODY}
        payload = {"questions": _valid_question_set()}

        with patch("services.ai_service.generate_json",
                   new=AsyncMock(return_value=payload)):
            client, key = await reading_service.generate_question_set_ai(passage)

        assert len(client) == 13 and len(key) == 13
        # Client view never carries the answer or span
        for c in client:
            assert "answer" not in c
            assert "passage_span" not in c
            assert "explanation" not in c
        # Answer key carries what grading needs
        for k in key:
            assert {"id", "type", "answer", "explanation"}.issubset(k)

    @pytest.mark.asyncio
    async def test_missing_questions_raises(self):
        passage = {"id": "p_test", "title": "x", "band": 6.0, "body": SAMPLE_BODY}
        with patch("services.ai_service.generate_json",
                   new=AsyncMock(return_value={"oops": []})):
            with pytest.raises(reading_service.QuestionGenerationError):
                await reading_service.generate_question_set_ai(passage)


# ─── get_or_generate_questions (cache orchestrator) ──────────────────


class TestCacheOrchestrator:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_ai(self):
        passage = {"id": "p_test", "title": "x", "band": 6.0, "body": SAMPLE_BODY}
        cached = {
            "questions_client": [{"id": "q1", "type": "mcq", "stem": "...",
                                  "options": [{"id": "o1", "text": "a"}]}],
            "answer_key": [{"id": "q1", "type": "mcq", "answer": "o1",
                            "explanation": "cached"}],
        }
        gen_mock = AsyncMock()
        with patch("services.firebase_service.get_cached_reading_questions",
                   return_value=cached), \
             patch("services.reading_service.generate_question_set_ai", gen_mock):
            client, key = await reading_service.get_or_generate_questions(passage)

        assert client == cached["questions_client"]
        assert key == cached["answer_key"]
        gen_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_generates_and_saves(self):
        passage = {"id": "p_test", "title": "x", "band": 6.0, "body": SAMPLE_BODY}
        payload = {"questions": _valid_question_set()}
        save = MagicMock()
        with patch("services.firebase_service.get_cached_reading_questions",
                   return_value=None), \
             patch("services.firebase_service.save_cached_reading_questions",
                   side_effect=save), \
             patch("services.ai_service.generate_json",
                   new=AsyncMock(return_value=payload)):
            client, key = await reading_service.get_or_generate_questions(passage)

        assert len(client) == 13
        save.assert_called_once()
        saved_pid, saved_data = save.call_args[0]
        assert saved_pid == "p_test"
        assert "questions_client" in saved_data and "answer_key" in saved_data

    @pytest.mark.asyncio
    async def test_ai_failure_falls_back_to_stub(self):
        passage = {"id": "p_test", "title": "x", "band": 6.0, "body": SAMPLE_BODY}
        with patch("services.firebase_service.get_cached_reading_questions",
                   return_value=None), \
             patch("services.reading_service.generate_question_set_ai",
                   new=AsyncMock(side_effect=reading_service.QuestionGenerationError("nope"))):
            client, key = await reading_service.get_or_generate_questions(passage)

        # Stub gives 5 MCQ questions with o1 as the correct answer
        assert len(client) == 5
        assert all(q["type"] == "mcq" for q in client)
        assert all(k["answer"] == "o1" for k in key)


# ─── Grading ─────────────────────────────────────────────────────────


class TestGrading:
    def _key(self):
        return [
            {"id": "q1", "type": "gap-fill", "answer": "Thirty", "explanation": "..."},
            {"id": "q2", "type": "tfng", "answer": "TRUE", "explanation": "..."},
            {"id": "q3", "type": "tfng", "answer": "NOT_GIVEN", "explanation": "..."},
            {"id": "q4", "type": "mcq", "answer": "o2", "explanation": "..."},
        ]

    def test_gap_fill_is_case_and_space_insensitive(self):
        result = reading_service.grade_answers(
            {"q1": "  thirty  "}, self._key()[:1],
        )
        assert result["correct"] == 1

    def test_tfng_accepts_synonyms(self):
        result = reading_service.grade_answers(
            {"q2": "t", "q3": "Not Given"}, self._key()[1:3],
        )
        assert result["correct"] == 2

    def test_mcq_exact_id_match(self):
        result = reading_service.grade_answers(
            {"q4": "o2"}, self._key()[3:4],
        )
        assert result["correct"] == 1

    def test_mixed_scoring_and_band_mapping(self):
        # 2 / 4 correct, total=4 → linear fallback: 3 + 0.5 * 6 = 6.0
        result = reading_service.grade_answers(
            {"q1": "thirty", "q2": "false", "q3": "not given", "q4": "o1"},
            self._key(),
        )
        assert result["correct"] == 2
        assert result["total"] == 4
        assert 5.5 <= result["band"] <= 6.5

    def test_13_question_band_mapping_uses_ielts_table(self):
        # All 13 correct should map to 9.0 per _BAND_BY_CORRECT_13
        key = []
        answers = {}
        for i in range(1, 14):
            key.append({"id": f"q{i}", "type": "mcq", "answer": "o1",
                        "explanation": ""})
            answers[f"q{i}"] = "o1"
        result = reading_service.grade_answers(answers, key)
        assert result["correct"] == 13
        assert result["band"] == 9.0

    def test_per_question_carries_explanation(self):
        result = reading_service.grade_answers(
            {"q1": "wrong"},
            [{"id": "q1", "type": "gap-fill", "answer": "right",
              "explanation": "Because of X."}],
        )
        pq = result["per_question"][0]
        assert pq["is_correct"] is False
        assert pq["explanation"] == "Because of X."
        assert pq["correct_answer"] == "right"

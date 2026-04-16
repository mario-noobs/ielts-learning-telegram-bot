"""Tests for services/srs_service.py — SM-2 algorithm and word strength helpers."""

from datetime import datetime, timezone

import config
from services.srs_service import (
    calculate_next_review,
    get_strength_emoji,
    get_word_strength,
)

# ---------------------------------------------------------------------------
# calculate_next_review
# ---------------------------------------------------------------------------


class TestCalculateNextReviewCorrect:
    """Correct-answer paths through SM-2."""

    def test_first_correct_answer_sets_interval_1_reps_1(self):
        word = {"srs_interval": 1, "srs_ease": 2.5, "srs_reps": 0}
        result = calculate_next_review(word, is_correct=True)

        assert result["srs_interval"] == 1
        assert result["srs_reps"] == 1
        assert result["times_correct"] == 1

    def test_second_correct_answer_sets_interval_3_reps_2(self):
        word = {"srs_interval": 1, "srs_ease": 2.5, "srs_reps": 1}
        result = calculate_next_review(word, is_correct=True)

        assert result["srs_interval"] == 3
        assert result["srs_reps"] == 2

    def test_third_correct_answer_multiplies_by_ease(self):
        word = {"srs_interval": 3, "srs_ease": 2.5, "srs_reps": 2}
        result = calculate_next_review(word, is_correct=True)

        assert result["srs_interval"] == round(3 * 2.5)  # 8
        assert result["srs_reps"] == 3

    def test_ease_increases_on_correct(self):
        word = {"srs_interval": 1, "srs_ease": 2.5, "srs_reps": 0}
        result = calculate_next_review(word, is_correct=True)

        assert result["srs_ease"] == 2.6

    def test_ease_capped_at_max(self):
        word = {"srs_interval": 1, "srs_ease": config.SRS_MAX_EASE, "srs_reps": 0}
        result = calculate_next_review(word, is_correct=True)

        assert result["srs_ease"] == config.SRS_MAX_EASE

    def test_next_review_is_in_the_future(self):
        word = {"srs_interval": 1, "srs_ease": 2.5, "srs_reps": 0}
        before = datetime.now(timezone.utc)
        result = calculate_next_review(word, is_correct=True)

        assert result["srs_next_review"] >= before

    def test_times_correct_accumulates(self):
        word = {"srs_reps": 0, "times_correct": 5}
        result = calculate_next_review(word, is_correct=True)

        assert result["times_correct"] == 6

    def test_times_incorrect_unchanged_on_correct(self):
        word = {"srs_reps": 0, "times_incorrect": 3}
        result = calculate_next_review(word, is_correct=True)

        assert result["times_incorrect"] == 3


class TestCalculateNextReviewIncorrect:
    """Incorrect-answer paths through SM-2."""

    def test_incorrect_resets_reps_and_interval(self):
        word = {"srs_interval": 10, "srs_ease": 2.5, "srs_reps": 5}
        result = calculate_next_review(word, is_correct=False)

        assert result["srs_interval"] == 1
        assert result["srs_reps"] == 0

    def test_ease_decreases_on_incorrect(self):
        word = {"srs_interval": 1, "srs_ease": 2.5, "srs_reps": 1}
        result = calculate_next_review(word, is_correct=False)

        assert result["srs_ease"] == 2.3

    def test_ease_never_below_min(self):
        word = {"srs_interval": 1, "srs_ease": config.SRS_MIN_EASE, "srs_reps": 1}
        result = calculate_next_review(word, is_correct=False)

        assert result["srs_ease"] == config.SRS_MIN_EASE

    def test_repeated_incorrect_keeps_ease_at_floor(self):
        word = {"srs_interval": 1, "srs_ease": 1.4, "srs_reps": 1}
        # First incorrect: 1.4 - 0.2 = 1.2 -> clamped to 1.3
        r1 = calculate_next_review(word, is_correct=False)
        assert r1["srs_ease"] == config.SRS_MIN_EASE

        # Second incorrect from floor: should stay at 1.3
        r2 = calculate_next_review(
            {"srs_interval": 1, "srs_ease": r1["srs_ease"], "srs_reps": 1},
            is_correct=False,
        )
        assert r2["srs_ease"] == config.SRS_MIN_EASE

    def test_times_incorrect_accumulates(self):
        word = {"srs_reps": 3, "times_incorrect": 2}
        result = calculate_next_review(word, is_correct=False)

        assert result["times_incorrect"] == 3

    def test_times_correct_unchanged_on_incorrect(self):
        word = {"srs_reps": 3, "times_correct": 7}
        result = calculate_next_review(word, is_correct=False)

        assert result["times_correct"] == 7


class TestCalculateNextReviewDefaults:
    """When word_data is missing SRS keys, defaults should apply."""

    def test_empty_dict_correct(self):
        result = calculate_next_review({}, is_correct=True)

        assert result["srs_interval"] == 1
        assert result["srs_reps"] == 1
        assert result["srs_ease"] == 2.6  # 2.5 + 0.1
        assert result["times_correct"] == 1
        assert result["times_incorrect"] == 0

    def test_empty_dict_incorrect(self):
        result = calculate_next_review({}, is_correct=False)

        assert result["srs_interval"] == 1
        assert result["srs_reps"] == 0
        assert result["srs_ease"] == 2.3  # 2.5 - 0.2
        assert result["times_correct"] == 0
        assert result["times_incorrect"] == 1


# ---------------------------------------------------------------------------
# get_word_strength
# ---------------------------------------------------------------------------


class TestGetWordStrength:
    def test_reps_zero_is_new(self):
        assert get_word_strength({"srs_reps": 0, "srs_interval": 5}) == "New"

    def test_interval_1_is_weak(self):
        assert get_word_strength({"srs_reps": 1, "srs_interval": 1}) == "Weak"

    def test_interval_7_is_learning(self):
        assert get_word_strength({"srs_reps": 2, "srs_interval": 7}) == "Learning"

    def test_interval_2_is_learning(self):
        assert get_word_strength({"srs_reps": 1, "srs_interval": 2}) == "Learning"

    def test_interval_30_is_good(self):
        assert get_word_strength({"srs_reps": 3, "srs_interval": 30}) == "Good"

    def test_interval_8_is_good(self):
        assert get_word_strength({"srs_reps": 2, "srs_interval": 8}) == "Good"

    def test_interval_31_is_mastered(self):
        assert get_word_strength({"srs_reps": 4, "srs_interval": 31}) == "Mastered"

    def test_interval_100_is_mastered(self):
        assert get_word_strength({"srs_reps": 5, "srs_interval": 100}) == "Mastered"

    def test_empty_dict_is_new(self):
        assert get_word_strength({}) == "New"


# ---------------------------------------------------------------------------
# get_strength_emoji
# ---------------------------------------------------------------------------


class TestGetStrengthEmoji:
    def test_new(self):
        assert get_strength_emoji("New") == "\U0001f195"

    def test_weak(self):
        assert get_strength_emoji("Weak") == "\U0001f534"

    def test_learning(self):
        assert get_strength_emoji("Learning") == "\U0001f7e1"

    def test_good(self):
        assert get_strength_emoji("Good") == "\U0001f7e2"

    def test_mastered(self):
        assert get_strength_emoji("Mastered") == "\u2b50"

    def test_unknown_strength_returns_default(self):
        assert get_strength_emoji("Unknown") == "\u26aa"

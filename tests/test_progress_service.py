"""Unit tests for services/progress_service.py (US-5.1)."""

from unittest.mock import patch

from services import progress_service


class TestBandEstimation:
    def test_vocab_band_zero_words_returns_starting(self):
        assert progress_service.estimate_vocab_band(0, 0) == 4.0

    def test_vocab_band_grows_with_word_count(self):
        small = progress_service.estimate_vocab_band(40, 0)
        big = progress_service.estimate_vocab_band(600, 0)
        assert big > small

    def test_vocab_band_mastery_boosts_but_caps_at_half(self):
        base = progress_service.estimate_vocab_band(200, 0)
        boosted = progress_service.estimate_vocab_band(200, 200)
        assert boosted - base <= 0.5
        assert boosted > base

    def test_vocab_band_clamped_to_max(self):
        band = progress_service.estimate_vocab_band(5000, 5000)
        assert band <= 9.0

    def test_writing_band_no_data_returns_starting(self):
        assert progress_service.estimate_writing_band([]) == 4.0

    def test_writing_band_averages_last_five(self):
        history = [
            {"overall_band": 7.0}, {"overall_band": 6.5},
            {"overall_band": 7.0}, {"overall_band": 6.0},
            {"overall_band": 6.5}, {"overall_band": 5.0},  # older, ignored
        ]
        band = progress_service.estimate_writing_band(history)
        assert band == 6.5

    def test_listening_band_no_data_returns_starting(self):
        assert progress_service.estimate_listening_band([]) == 4.0

    def test_reading_band_no_data_returns_starting(self):
        assert progress_service.estimate_reading_band([]) == 4.0

    def test_reading_band_averages_submitted_only(self):
        sessions = [
            {"status": "in_progress", "grade": {"band": 9.0}},  # ignored
            {"status": "submitted", "grade": {"band": 6.0}},
            {"status": "submitted", "grade": {"band": 7.0}},
            {"status": "expired", "grade": None},  # ignored
        ]
        assert progress_service.estimate_reading_band(sessions) == 6.5

    def test_reading_band_caps_at_sample_window(self):
        sessions = [
            {"status": "submitted", "grade": {"band": 8.0}},
            {"status": "submitted", "grade": {"band": 8.0}},
            {"status": "submitted", "grade": {"band": 8.0}},
            {"status": "submitted", "grade": {"band": 8.0}},
            {"status": "submitted", "grade": {"band": 8.0}},
            # 6th session below is beyond READING_SAMPLE and must not pull down
            {"status": "submitted", "grade": {"band": 3.0}},
        ]
        assert progress_service.estimate_reading_band(sessions) == 8.0

    def test_listening_band_weights_type_accuracy(self):
        history = [
            {"exercise_type": "dictation", "score": 0.8, "submitted": True},
            {"exercise_type": "gap_fill", "score": 0.7, "submitted": True},
            {"exercise_type": "comprehension", "score": 0.7, "submitted": True},
        ]
        band = progress_service.estimate_listening_band(history)
        assert 6.5 <= band <= 7.5

    def test_listening_band_unsubmitted_ignored(self):
        history = [
            {"exercise_type": "dictation", "score": 0.95, "submitted": False},
        ]
        assert progress_service.estimate_listening_band(history) == 4.0

    def test_all_bands_are_half_steps(self):
        for total in (0, 17, 123, 876, 2345):
            b = progress_service.estimate_vocab_band(total, 0)
            assert (b * 2).is_integer()


class TestBuildSnapshot:
    def test_snapshot_with_no_data(self):
        user = {"id": "u1", "target_band": 7.0, "total_words": 0}
        with patch(
            "services.progress_service.firebase_service.get_mastered_words",
            return_value=[],
        ), patch(
            "services.progress_service.firebase_service.list_writing_submissions",
            return_value=[],
        ), patch(
            "services.progress_service.firebase_service.list_listening_exercises",
            return_value=[],
        ), patch(
            "services.progress_service.firebase_service.list_reading_sessions",
            return_value=[],
        ):
            snap = progress_service.build_snapshot(user)
        assert snap["skills"]["vocabulary"]["band"] == 4.0
        assert snap["skills"]["writing"]["band"] == 4.0
        assert snap["skills"]["listening"]["band"] == 4.0
        assert snap["skills"]["reading"]["band"] == 4.0
        assert snap["overall_band"] == 4.0

    def test_snapshot_aggregates_skills(self):
        user = {"id": "u1", "target_band": 7.0, "total_words": 300}
        with patch(
            "services.progress_service.firebase_service.get_mastered_words",
            return_value=[{}] * 50,
        ), patch(
            "services.progress_service.firebase_service.list_writing_submissions",
            return_value=[{"overall_band": 7.0}, {"overall_band": 7.0}],
        ), patch(
            "services.progress_service.firebase_service.list_listening_exercises",
            return_value=[
                {"exercise_type": "dictation", "score": 0.6, "submitted": True},
                {"exercise_type": "gap_fill", "score": 0.6, "submitted": True},
                {"exercise_type": "comprehension", "score": 0.6, "submitted": True},
            ],
        ), patch(
            "services.progress_service.firebase_service.list_reading_sessions",
            return_value=[
                {"status": "submitted", "grade": {"band": 6.5}},
                {"status": "submitted", "grade": {"band": 7.0}},
            ],
        ):
            snap = progress_service.build_snapshot(user)
        assert snap["skills"]["writing"]["band"] == 7.0
        assert snap["skills"]["writing"]["sample_size"] == 2
        assert snap["skills"]["reading"]["band"] == 7.0  # (6.5 + 7.0) / 2 = 6.75 → 7.0 clamped
        assert snap["skills"]["reading"]["sample_size"] == 2
        assert 6.0 <= snap["overall_band"] <= 8.0
        assert snap["target_band"] == 7.0


class TestPrediction:
    def test_predict_with_no_history_returns_starting(self):
        assert progress_service.predict_band([], 30) == 4.0

    def test_predict_with_single_point_returns_clamped_value(self):
        history = [{"overall_band": 6.0}]
        assert progress_service.predict_band(history, 60) == 6.0

    def test_predict_extrapolates_upward_trend(self):
        history = [
            {"overall_band": 5.5},
            {"overall_band": 6.0},
            {"overall_band": 6.5},
        ]
        projected = progress_service.predict_band(history, 30)
        assert projected >= 6.5


class TestHistoryWindow:
    def test_returns_sorted_snapshots(self):
        def list_snaps(_uid, date_strs):
            return [
                {"date": date_strs[3], "overall_band": 6.5},
                {"date": date_strs[0], "overall_band": 6.0},
            ]

        with patch(
            "services.progress_service.firebase_service.list_progress_snapshots",
            side_effect=list_snaps,
        ):
            out = progress_service.history_window("u1", days=7)
        assert len(out) == 2
        assert out[0]["date"] < out[1]["date"]

"""Unit tests for services/plan_service.py + weakness_service.py (US-4.1)."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from services import plan_service, weakness_service


def _fresh_weakness(**overrides) -> dict:
    base = {
        "due_srs_count": 0,
        "total_vocab": 0,
        "daily_words_done_today": False,
        "last_writing_band": 0.0,
        "writing_sample_size": 0,
        "last_listening_score": 0.0,
        "listening_sample_size": 0,
        "weakest_listening_type": "dictation",
        "streak": 0,
    }
    base.update(overrides)
    return base


class TestPlanGeneration:
    def test_srs_always_included_when_due(self):
        user = {"id": "u1", "target_band": 7.0}
        w = _fresh_weakness(due_srs_count=5)
        plan = plan_service.generate_plan(user, w, today=date(2026, 4, 18))
        ids = [a["id"] for a in plan["activities"]]
        assert "srs_review" in ids
        assert ids[0] == "srs_review"

    def test_srs_skipped_when_no_due(self):
        user = {"id": "u1"}
        plan = plan_service.generate_plan(
            user, _fresh_weakness(), today=date(2026, 4, 18),
        )
        ids = [a["id"] for a in plan["activities"]]
        assert "srs_review" not in ids

    def test_skills_rotate_no_duplicates(self):
        user = {"id": "u1"}
        w = _fresh_weakness(due_srs_count=3)
        plan = plan_service.generate_plan(user, w, today=date(2026, 4, 18))
        types = [a["type"] for a in plan["activities"]]
        # No three consecutive same-type activities
        for i in range(len(types) - 2):
            assert not (types[i] == types[i + 1] == types[i + 2])

    def test_respects_30_minute_cap_by_default(self):
        user = {"id": "u1"}
        w = _fresh_weakness(due_srs_count=50)
        plan = plan_service.generate_plan(user, w, today=date(2026, 4, 18))
        assert plan["total_minutes"] <= 30
        assert len(plan["activities"]) >= 3

    def test_exam_urgent_lifts_cap_and_adds_sprint(self):
        exam = (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat()
        user = {"id": "u1", "exam_date": exam}
        w = _fresh_weakness(due_srs_count=3)
        plan = plan_service.generate_plan(user, w)
        assert plan["exam_urgent"] is True
        assert plan["cap_minutes"] == 45
        ids = [a["id"] for a in plan["activities"]]
        assert "sprint_quiz" in ids

    def test_writing_rotates_by_day(self):
        """Odd-parity days run the writing big-block (reading runs on even days —
        see test_reading_vs_writing_alternate)."""
        user = {"id": "u1"}
        w = _fresh_weakness()
        # 2026-04-19 and 2026-04-21 are both odd ordinals, so both plans
        # carry writing — but the task_type rotates by inner parity.
        # Using two even-delta days keeps this a writing-vs-writing check.
        p_a = plan_service.generate_plan(user, w, today=date(2026, 4, 19))
        p_b = plan_service.generate_plan(user, w, today=date(2026, 4, 21))
        wa = next(a for a in p_a["activities"] if a["type"] == "writing")
        wb = next(a for a in p_b["activities"] if a["type"] == "writing")
        assert wa["meta"]["task_type"] != wb["meta"]["task_type"]

    def test_reading_picks_band_matched_passage(self):
        """AC1: target_band=6.5 user should see a passage within 6.0–7.0."""
        user = {"id": "u1", "target_band": 6.5}
        w = _fresh_weakness()
        # Even ordinal day → reading is active
        plan = plan_service.generate_plan(user, w, today=date(2026, 4, 18))
        reading = next(
            (a for a in plan["activities"] if a["type"] == "reading"),
            None,
        )
        assert reading is not None, "reading activity expected on even-ordinal day"
        assert 6.0 <= reading["meta"]["band"] <= 7.0
        assert reading["route"].startswith("/reading/")

    def test_reading_vs_writing_alternate(self):
        """Reading runs on even ordinal days, writing on odd (US-M9.5)."""
        user = {"id": "u1"}
        w = _fresh_weakness()
        p_even = plan_service.generate_plan(user, w, today=date(2026, 4, 18))
        p_odd = plan_service.generate_plan(user, w, today=date(2026, 4, 19))
        even_types = [a["type"] for a in p_even["activities"]]
        odd_types = [a["type"] for a in p_odd["activities"]]
        # On days when a seeded corpus is present, the even-parity day
        # carries reading (not writing); the odd-parity day carries writing.
        assert ("reading" in even_types) != ("reading" in odd_types)
        assert "writing" in odd_types

    def test_listening_picks_weakest_type(self):
        user = {"id": "u1"}
        w = _fresh_weakness(weakest_listening_type="gap_fill")
        plan = plan_service.generate_plan(user, w, today=date(2026, 4, 18))
        listening = next(a for a in plan["activities"] if a["type"] == "listening")
        assert listening["meta"]["exercise_type"] == "gap_fill"


class TestMarkCompleted:
    def _sample_plan(self) -> dict:
        return {
            "date": "2026-04-18",
            "activities": [
                {"id": "a", "type": "writing", "completed": False,
                 "title": "", "description": "", "estimated_minutes": 10,
                 "route": "/", "meta": {}},
                {"id": "b", "type": "listening", "completed": False,
                 "title": "", "description": "", "estimated_minutes": 8,
                 "route": "/", "meta": {}},
            ],
            "completed_count": 0,
            "total_minutes": 18,
            "cap_minutes": 30,
        }

    def test_marks_target_and_bumps_count(self):
        before = self._sample_plan()
        after = plan_service.mark_completed(before, "b")
        assert after["completed_count"] == 1
        assert after["activities"][0]["completed"] is False
        assert after["activities"][1]["completed"] is True

    def test_unknown_id_returns_same_plan(self):
        before = self._sample_plan()
        after = plan_service.mark_completed(before, "ghost")
        assert after is before

    def test_idempotent_on_already_completed(self):
        before = self._sample_plan()
        before["activities"][0]["completed"] = True
        before["completed_count"] = 1
        after = plan_service.mark_completed(before, "a")
        assert after is before


class TestWeaknessProfile:
    def test_weakest_listening_prefers_unseen_types(self):
        history = [
            {"exercise_type": "dictation", "score": 0.8, "submitted": True},
            {"exercise_type": "dictation", "score": 0.7, "submitted": True},
        ]
        assert weakness_service._weakest_listening_type(history) in (
            "gap_fill", "comprehension",
        )

    def test_weakest_listening_between_seen_types(self):
        history = [
            {"exercise_type": "dictation", "score": 0.9},
            {"exercise_type": "gap_fill", "score": 0.3},
            {"exercise_type": "comprehension", "score": 0.7},
        ]
        assert weakness_service._weakest_listening_type(history) == "gap_fill"

    def test_days_until_exam_positive(self):
        future = (datetime.now(timezone.utc).date() + timedelta(days=14)).isoformat()
        assert weakness_service.days_until_exam({"exam_date": future}) == 14

    def test_days_until_exam_missing(self):
        assert weakness_service.days_until_exam({}) is None

    def test_build_weakness_profile_aggregates(self):
        user = {"id": "u1", "target_band": 7.0, "total_words": 42, "streak": 3}

        with patch(
            "services.weakness_service.firebase_service.get_due_words",
            return_value=[{}, {}, {}],
        ), patch(
            "services.weakness_service.firebase_service.get_user_daily_words",
            return_value=None,
        ), patch(
            "services.weakness_service.firebase_service.list_writing_submissions",
            return_value=[{"overall_band": 6.5}, {"overall_band": 7.0}],
        ), patch(
            "services.weakness_service.firebase_service.list_listening_exercises",
            return_value=[
                {"exercise_type": "dictation", "score": 0.4, "submitted": True},
            ],
        ):
            profile = weakness_service.build_weakness_profile(user)

        assert profile["due_srs_count"] == 3
        assert profile["daily_words_done_today"] is False
        assert profile["last_writing_band"] == 6.8
        assert profile["listening_sample_size"] == 1
        assert profile["streak"] == 3

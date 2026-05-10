"""Unit tests for services/readiness_service.py (US-#223).

Pure-functional service — no DB, no AI. Each test exercises one of
the documented state variants from the design brief: no-exam-date /
0% / partial / 100% / <7-days-final-stretch.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from services import readiness_service


def _today() -> date:
    return date.today()


def _user(**overrides) -> dict:
    base = {
        "id": "u1",
        "name": "Test",
        "target_band": 7.0,
        "exam_date": None,
        "weekly_goal_minutes": 0,
        "daily_time": None,
    }
    base.update(overrides)
    return base


def _progress(skills_at_band: float = 0.0) -> dict:
    return {
        "snapshot": {
            "skills": {
                "writing": {"band": skills_at_band},
                "listening": {"band": skills_at_band},
                "vocabulary": {"band": skills_at_band},
                "reading": {"band": skills_at_band},
            },
        },
    }


def test_empty_user_step1_active_others_upcoming_or_locked():
    """Brand-new user — no goal, no plan, no exam. Step 1 active,
    Steps 2+3 upcoming, Step 4 locked because no date."""
    snap = readiness_service.compute_readiness(
        _user(target_band=0, exam_date=None), None,
    )
    statuses = [s["status"] for s in snap["steps"]]
    assert statuses == ["active", "upcoming", "upcoming", "locked"]
    assert snap["pct_complete"] == 0
    assert snap["days_until_exam"] is None
    assert snap["urgent"] is False


def test_goal_set_step1_done_step2_active():
    """Goal locked (band + date) → Step 1 done, Step 2 active."""
    far_future = (_today() + timedelta(days=180)).isoformat()
    snap = readiness_service.compute_readiness(
        _user(exam_date=far_future), _progress(0),
    )
    statuses = [s["status"] for s in snap["steps"]]
    assert statuses[0] == "done"
    assert statuses[1] == "active"
    # Step 4 still locked — 180 days > 14-day unlock window.
    assert statuses[3] == "locked"


def test_full_setup_skills_active_pct_25():
    """Goal + daily plan locked → Step 3 active. Pct = 50% of step 3
    progress (0/4 skills hit) added to 50% of step 3? No — at_target=0
    → Step 3 has 0 sub-tasks (skills nest in frontend), so pct = 25*2 = 50%."""
    far_future = (_today() + timedelta(days=180)).isoformat()
    snap = readiness_service.compute_readiness(
        _user(
            exam_date=far_future,
            weekly_goal_minutes=150,
            daily_time="08:00",
        ),
        _progress(0),
    )
    statuses = [s["status"] for s in snap["steps"]]
    assert statuses == ["done", "done", "active", "locked"]
    # Steps 1+2 done = 50%; Step 3 active with no sub_tasks contributes 0%.
    assert snap["pct_complete"] == 50


def test_skills_at_target_step3_done():
    """All 4 skills at target band → Step 3 done."""
    far_future = (_today() + timedelta(days=180)).isoformat()
    snap = readiness_service.compute_readiness(
        _user(
            exam_date=far_future,
            weekly_goal_minutes=150,
            daily_time="08:00",
            target_band=6.5,
        ),
        _progress(7.0),  # All 4 skills > target
    )
    statuses = [s["status"] for s in snap["steps"]]
    assert statuses[2] == "done"
    # 3 of 4 done = 75%; mock_test still locked at 180d out.
    assert snap["pct_complete"] == 75


def test_subtasks_tick_only_after_user_set_flag():
    """target_band 7.0 + weekly_goal_minutes 150 are unclearable
    defaults; the sub-tasks tick off explicit *_set flags stamped by
    PATCH /me, not the underlying values (#dashboard-polish).

    This test pins both halves of the contract:
      - flags absent / false  → sub-tasks open (○)
      - flags true            → sub-tasks ticked (✓)
    """
    # Fresh user: defaults present, no flags → sub-tasks open.
    snap = readiness_service.compute_readiness(
        _user(target_band=7.0, weekly_goal_minutes=150),
        _progress(0),
    )
    goal = snap["steps"][0]
    daily = snap["steps"][1]
    target_band_task = next(t for t in goal["sub_tasks"] if t["id"] == "target_band")
    weekly_goal_task = next(t for t in daily["sub_tasks"] if t["id"] == "weekly_goal")
    assert target_band_task["done"] is False
    assert weekly_goal_task["done"] is False
    assert goal["status"] == "active"

    # User has saved both fields → flags flip true → sub-tasks tick.
    snap = readiness_service.compute_readiness(
        _user(
            target_band=7.0,
            weekly_goal_minutes=150,
            target_band_set=True,
            weekly_goal_set=True,
        ),
        _progress(0),
    )
    goal = snap["steps"][0]
    daily = snap["steps"][1]
    assert next(t for t in goal["sub_tasks"] if t["id"] == "target_band")["done"] is True
    assert next(t for t in daily["sub_tasks"] if t["id"] == "weekly_goal")["done"] is True


def test_urgent_window_under_seven_days_flips_flag():
    """Exam within EXAM_URGENT_DAYS → urgent flag true + Step 4 active."""
    near = (_today() + timedelta(days=5)).isoformat()
    snap = readiness_service.compute_readiness(
        _user(
            exam_date=near,
            weekly_goal_minutes=150,
            daily_time="08:00",
        ),
        _progress(0),
    )
    assert snap["urgent"] is True
    assert snap["days_until_exam"] == 5
    # Step 4 unlocked (5 ≤ 14) → active, not locked.
    assert snap["steps"][3]["status"] == "active"
    assert snap["steps"][3]["rationale_params"] == {"days": 5}

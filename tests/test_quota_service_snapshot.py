"""Tests for ``quota_service.get_usage_snapshot`` (US-M13.5).

Kept separate from ``test_quota_service.py`` so the snapshot helper —
which is pure compute over two repo reads — can be exercised without
a Postgres ``DATABASE_URL`` (the increment/enforce tests still need
real DB; these don't).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


class _FakeAiUsageRepo:
    def __init__(self, today: dict[str, int]) -> None:
        self._today = today

    def get_today(self, user_uid: str) -> dict[str, int]:  # noqa: ARG002
        return dict(self._today)


class _FakePlanRepo:
    def __init__(self, daily_ai_quota: int) -> None:
        self._plan = SimpleNamespace(daily_ai_quota=daily_ai_quota)

    def get(self, plan_id: str):  # noqa: ARG002
        return self._plan


def test_get_usage_snapshot_returns_shape_for_seeded_rows() -> None:
    """Snapshot sums per-feature rows and exposes plan/cap/by_feature/reset_at."""
    from services.admin import quota_service

    with patch(
        "services.admin.quota_service.get_ai_usage_repo",
        return_value=_FakeAiUsageRepo({"quiz": 3, "writing": 2}),
    ), patch(
        "services.admin.quota_service.get_plan_repo",
        return_value=_FakePlanRepo(daily_ai_quota=10),
    ):
        snap = quota_service.get_usage_snapshot(
            user_uid="u1", plan="free", quota_override=None,
        )

    assert snap["plan"] == "free"
    assert snap["cap"] == 10
    assert snap["used"] == 5  # 3 + 2, well under cap so no clamp
    assert snap["by_feature"] == {"quiz": 3, "writing": 2}
    assert snap["reset_at"].endswith("+00:00")


def test_get_usage_snapshot_clamps_used_when_raw_exceeds_cap() -> None:
    """Admin override-lowering can leave raw used > cap; snapshot clamps display."""
    from services.admin import quota_service

    # Raw usage = 12 (quiz=7 + writing=5) but override caps at 5.
    # Snapshot should clamp `used` to 5 so the bot doesn't render
    # "12/5". The raw `by_feature` map is preserved for transparency.
    with patch(
        "services.admin.quota_service.get_ai_usage_repo",
        return_value=_FakeAiUsageRepo({"quiz": 7, "writing": 5}),
    ):
        snap = quota_service.get_usage_snapshot(
            user_uid="u1", plan="free", quota_override=5,
        )

    assert snap["cap"] == 5
    assert snap["used"] == 5
    assert snap["by_feature"] == {"quiz": 7, "writing": 5}

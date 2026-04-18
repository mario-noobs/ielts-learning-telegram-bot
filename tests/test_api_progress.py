"""Integration tests for /api/v1/progress (US-5.1)."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {
    "id": "u1",
    "name": "Alice",
    "target_band": 7.0,
    "total_words": 120,
    "topics": ["environment"],
}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: dict(FAKE_USER)
    return TestClient(app)


def _history_docs(dates: list[str]) -> list[dict]:
    return [
        {
            "date": d,
            "overall_band": 6.0,
            "skills": {
                "vocabulary": {"band": 5.5},
                "writing": {"band": 6.5},
                "listening": {"band": 6.0},
            },
        }
        for d in dates
    ]


class TestGetProgress:
    def test_returns_snapshot_trend_and_predictions(self, client):
        save_called: dict = {}

        def save(_u, snap):
            save_called["snap"] = snap

        def window(_uid, _days):
            return _history_docs(["2026-04-10", "2026-04-11", "2026-04-12"])

        with patch(
            "api.routes.progress.progress_service.build_snapshot",
            return_value={
                "overall_band": 6.0,
                "skills": {
                    "vocabulary": {"band": 5.5, "total_words": 120, "mastered_count": 10},
                    "writing": {"band": 6.5, "sample_size": 2},
                    "listening": {"band": 6.0, "sample_size": 3, "accuracy_by_type": {}},
                },
                "target_band": 7.0,
                "date": "2026-04-12",
                "generated_at": datetime.now(timezone.utc),
            },
        ), patch(
            "api.routes.progress.progress_service.save_today_snapshot",
            side_effect=save,
        ), patch(
            "api.routes.progress.progress_service.history_window",
            side_effect=window,
        ):
            res = client.get("/api/v1/progress")

        assert res.status_code == 200
        body = res.json()
        assert body["snapshot"]["overall_band"] == 6.0
        assert body["snapshot"]["target_band"] == 7.0
        assert len(body["trend"]) == 3
        assert [p["days_ahead"] for p in body["predictions"]] == [30, 60, 90]
        assert "snap" in save_called

    def test_zero_data_user_still_returns_200(self, client):
        with patch(
            "api.routes.progress.progress_service.build_snapshot",
            return_value={
                "overall_band": 4.0,
                "skills": {
                    "vocabulary": {"band": 4.0, "total_words": 0, "mastered_count": 0},
                    "writing": {"band": 4.0, "sample_size": 0},
                    "listening": {"band": 4.0, "sample_size": 0, "accuracy_by_type": {}},
                },
                "target_band": 7.0,
            },
        ), patch(
            "api.routes.progress.progress_service.save_today_snapshot",
            return_value="2026-04-18",
        ), patch(
            "api.routes.progress.progress_service.history_window",
            return_value=[],
        ):
            res = client.get("/api/v1/progress")
        assert res.status_code == 200
        body = res.json()
        assert body["snapshot"]["overall_band"] == 4.0
        assert body["trend"] == []
        assert all(4.0 <= p["projected_band"] <= 9.0 for p in body["predictions"])


class TestGetHistory:
    def test_returns_trend_points(self, client):
        with patch(
            "api.routes.progress.progress_service.history_window",
            return_value=_history_docs(["2026-04-15", "2026-04-16"]),
        ):
            res = client.get("/api/v1/progress/history?days=7")
        assert res.status_code == 200
        body = res.json()
        assert len(body["items"]) == 2
        assert body["items"][0]["vocabulary_band"] == 5.5

    def test_invalid_days_rejected(self, client):
        res = client.get("/api/v1/progress/history?days=1000")
        assert res.status_code == 422

"""Integration tests for /api/v1/progress/recommendations (US-5.3)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {"id": "u1", "name": "A", "target_band": 7.0, "topics": []}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: dict(FAKE_USER)
    return TestClient(app)


def test_returns_tips(client):
    tips = [
        {"id": "v-srs", "skill": "vocabulary", "tip_en": "Review SRS",
         "tip_vi": "Ôn SRS", "action_label": "Ôn ngay",
         "action_route": "/review"},
        {"id": "w-t2", "skill": "writing", "tip_en": "Write Task 2",
         "tip_vi": "Viết Task 2", "action_label": "Viết bài",
         "action_route": "/write"},
        {"id": "l-dict", "skill": "listening", "tip_en": "Dictate daily",
         "tip_vi": "Dictation hằng ngày", "action_label": "Nghe",
         "action_route": "/listening"},
    ]
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
        },
    ), patch(
        "api.routes.progress.progress_service.history_window",
        return_value=[],
    ), patch(
        "api.routes.progress.coaching_service.get_cached_or_generate",
        new=AsyncMock(return_value=(
            "2026-W16", tips, datetime(2026, 4, 18, tzinfo=timezone.utc),
        )),
    ):
        res = client.get("/api/v1/progress/recommendations")
    assert res.status_code == 200
    body = res.json()
    assert body["week_key"] == "2026-W16"
    assert len(body["tips"]) == 3
    assert body["tips"][0]["action_route"] in {"/review", "/vocab", "/write", "/listening"}

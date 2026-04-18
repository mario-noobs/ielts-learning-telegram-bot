"""Unit tests for services/coaching_service.py (US-5.3)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from services import coaching_service


def _snapshot() -> dict:
    return {
        "overall_band": 5.5,
        "target_band": 7.0,
        "skills": {
            "vocabulary": {"band": 5.0, "total_words": 120, "mastered_count": 10},
            "writing": {"band": 5.5, "sample_size": 3},
            "listening": {"band": 6.0, "sample_size": 5},
        },
    }


class TestCurrentWeekKey:
    def test_format(self):
        key = coaching_service.current_week_key(datetime(2026, 4, 18, tzinfo=timezone.utc))
        assert key.startswith("2026-W")
        assert len(key) == 8


class TestNormalize:
    def test_rejects_invalid_skill_and_route(self):
        raw = {
            "tips": [
                {
                    "id": "bad-skill",
                    "skill": "speaking",
                    "tip_en": "t", "tip_vi": "t",
                    "action_label": "x", "action_route": "/unknown",
                },
            ],
        }
        out = coaching_service._normalize_tips(raw)
        assert out[0]["skill"] == "overall"
        assert out[0]["action_route"] == "/review"

    def test_deduplicates_slugs(self):
        raw = {
            "tips": [
                {"id": "tip", "skill": "writing", "tip_en": "a", "tip_vi": "a",
                 "action_label": "x", "action_route": "/write"},
                {"id": "tip", "skill": "writing", "tip_en": "b", "tip_vi": "b",
                 "action_label": "x", "action_route": "/write"},
            ],
        }
        out = coaching_service._normalize_tips(raw)
        assert out[0]["id"] != out[1]["id"]

    def test_caps_at_max_tips(self):
        raw = {
            "tips": [
                {"id": f"t{i}", "skill": "writing", "tip_en": "x",
                 "tip_vi": "x", "action_label": "a", "action_route": "/write"}
                for i in range(10)
            ],
        }
        out = coaching_service._normalize_tips(raw)
        assert len(out) == coaching_service.MAX_TIPS


class TestGenerateRecommendations:
    @pytest.mark.asyncio
    async def test_uses_ai_tips_when_enough(self):
        ai_response = {
            "tips": [
                {"id": "v-srs", "skill": "vocabulary", "tip_en": "Review SRS",
                 "tip_vi": "Ôn SRS", "action_label": "Ôn ngay",
                 "action_route": "/review"},
                {"id": "w-t2", "skill": "writing", "tip_en": "Write Task 2",
                 "tip_vi": "Viết Task 2", "action_label": "Viết bài",
                 "action_route": "/write"},
                {"id": "l-dict", "skill": "listening", "tip_en": "Dictate daily",
                 "tip_vi": "Dictation hằng ngày", "action_label": "Nghe",
                 "action_route": "/listening"},
            ],
        }
        with patch(
            "services.coaching_service.ai_service.generate_json",
            new=AsyncMock(return_value=ai_response),
        ):
            tips = await coaching_service.generate_recommendations(
                {"id": "u"}, _snapshot(), [],
            )
        assert len(tips) == 3
        assert all(t["action_route"].startswith("/") for t in tips)

    @pytest.mark.asyncio
    async def test_falls_back_when_ai_returns_too_few(self):
        with patch(
            "services.coaching_service.ai_service.generate_json",
            new=AsyncMock(return_value={"tips": []}),
        ):
            tips = await coaching_service.generate_recommendations(
                {"id": "u"}, _snapshot(), [],
            )
        assert len(tips) >= coaching_service.MIN_TIPS

    @pytest.mark.asyncio
    async def test_falls_back_on_ai_exception(self):
        with patch(
            "services.coaching_service.ai_service.generate_json",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            tips = await coaching_service.generate_recommendations(
                {"id": "u"}, _snapshot(), [],
            )
        assert len(tips) >= coaching_service.MIN_TIPS
        # Fallback prioritises widest gap (vocabulary at 5.0 vs target 7.0 — gap=2.0)
        assert tips[0]["skill"] == "vocabulary"


class TestCachedOrGenerate:
    @pytest.mark.asyncio
    async def test_returns_cached_without_ai_call(self):
        cached = {
            "tips": [
                {"id": "c1", "skill": "writing", "tip_en": "x", "tip_vi": "x",
                 "action_label": "a", "action_route": "/write"},
            ],
            "generated_at": datetime(2026, 4, 18, tzinfo=timezone.utc),
        }
        ai_mock = AsyncMock()
        with patch(
            "services.coaching_service.firebase_service.get_progress_recommendations",
            return_value=cached,
        ), patch(
            "services.coaching_service.ai_service.generate_json",
            new=ai_mock,
        ):
            key, tips, _ = await coaching_service.get_cached_or_generate(
                {"id": "u"}, _snapshot(), [],
            )
        assert len(tips) == 1
        assert tips[0]["id"] == "c1"
        ai_mock.assert_not_called()
        assert key.startswith(str(datetime.now(timezone.utc).year))

    @pytest.mark.asyncio
    async def test_generates_and_saves_when_not_cached(self):
        saved: dict = {}

        def save(_uid, key, data):
            saved["key"] = key
            saved["data"] = data

        with patch(
            "services.coaching_service.firebase_service.get_progress_recommendations",
            return_value=None,
        ), patch(
            "services.coaching_service.firebase_service.save_progress_recommendations",
            side_effect=save,
        ), patch(
            "services.coaching_service.ai_service.generate_json",
            new=AsyncMock(return_value={"tips": []}),  # triggers fallback
        ):
            _, tips, _ = await coaching_service.get_cached_or_generate(
                {"id": "u"}, _snapshot(), [],
            )
        assert len(tips) >= coaching_service.MIN_TIPS
        assert "key" in saved
        assert saved["data"]["tips"] == tips

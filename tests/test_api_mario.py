"""Integration tests for Mario onboarding assistant API."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {
    "id": "user-123",
    "name": "Alice Nguyen",
    "target_band": 7.5,
    "target_band_set": True,
    "weekly_goal_set": True,
}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: dict(FAKE_USER)
    return TestClient(app)


class TestMarioState:
    def test_requires_authentication(self):
        app = create_app()
        with TestClient(app) as c:
            response = c.get("/api/v1/mario/state")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "common.unauthorized"

    def test_returns_disabled_when_feature_flag_is_off(self, client):
        with patch(
            "services.mario_service.feature_flag_service.is_enabled",
            return_value=False,
        ) as is_enabled:
            response = client.get("/api/v1/mario/state?route=/reading")

        assert response.status_code == 200
        assert response.json() == {
            "enabled": False,
            "minimized": True,
            "greeting": None,
            "suggestions": [],
        }
        is_enabled.assert_called_once_with("mario_onboarding", "user-123")

    def test_returns_route_aware_state_when_feature_flag_is_on(self, client):
        with patch(
            "services.mario_service.feature_flag_service.is_enabled",
            return_value=True,
        ):
            response = client.get(
                "/api/v1/mario/state?route=/practice/reading/session/abc"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["minimized"] is True
        assert body["greeting"] == {
            "key": "greeting.reading",
            "params": {"name": "Alice", "target_band": 7.5},
        }
        assert body["suggestions"][0] == {
            "id": "reading",
            "label_key": "actions.readingLab",
            "route": "/practice/reading",
            "params": {},
        }

    def test_returns_disabled_when_user_dismissed_onboarding(self, client):
        client.app.dependency_overrides[get_current_user] = lambda: {
            **FAKE_USER,
            "dismissed_onboarding": True,
        }
        with patch(
            "services.mario_service.feature_flag_service.is_enabled",
            return_value=True,
        ) as is_enabled:
            response = client.get("/api/v1/mario/state")

        assert response.status_code == 200
        assert response.json()["enabled"] is False
        is_enabled.assert_not_called()

    def test_uses_profile_gaps_for_default_suggestions(self, client):
        client.app.dependency_overrides[get_current_user] = lambda: {
            **FAKE_USER,
            "target_band_set": False,
            "weekly_goal_set": False,
        }
        with patch(
            "services.mario_service.feature_flag_service.is_enabled",
            return_value=True,
        ):
            response = client.get("/api/v1/mario/state")

        assert response.status_code == 200
        suggestion_ids = [item["id"] for item in response.json()["suggestions"]]
        assert suggestion_ids == ["set-target-band", "review"]


class TestMarioEvents:
    def test_accepts_event_without_persistence(self, client):
        response = client.post(
            "/api/v1/mario/events",
            json={
                "event": "action_clicked",
                "route": "/learn/daily",
                "suggestion_id": "daily",
                "metadata": {"source": "bubble"},
            },
        )

        assert response.status_code == 204
        assert response.content == b""

    def test_invalid_event_uses_error_contract(self, client):
        response = client.post(
            "/api/v1/mario/events",
            json={"event": "nope"},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "common.validation"


class TestMarioChat:
    def test_requires_enabled_mario(self, client):
        with patch(
            "services.mario_service.feature_flag_service.is_enabled",
            return_value=False,
        ):
            response = client.post(
                "/api/v1/mario/chat",
                json={"message": "What should I do next?", "route": "/learn/review"},
            )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "common.forbidden"

    def test_returns_ai_reply_with_route_context(self, client):
        with (
            patch(
                "services.mario_service.feature_flag_service.is_enabled",
                return_value=True,
            ),
            patch(
                "services.mario_service.ai_service.generate",
                new_callable=AsyncMock,
                return_value="Review 10 due cards first, then check your mistakes.",
            ) as generate,
        ):
            response = client.post(
                "/api/v1/mario/chat",
                json={
                    "message": "What should I do here?",
                    "route": "/learn/review",
                    "history": [
                        {"role": "assistant", "content": "Ready for review?"},
                    ],
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "message": {
                "role": "assistant",
                "content": "Review 10 due cards first, then check your mistakes.",
            }
        }
        prompt = generate.await_args.args[0]
        assert "Current app route: /learn/review" in prompt
        assert "First name: Alice" in prompt
        assert generate.await_args.kwargs == {"plan": "free", "quality": "cheap"}

    def test_daily_chat_prompt_is_grounded_in_real_page_actions(self, client):
        with (
            patch(
                "services.mario_service.feature_flag_service.is_enabled",
                return_value=True,
            ),
            patch(
                "services.mario_service.ai_service.generate",
                new_callable=AsyncMock,
                return_value="Use the pronunciation button, then mark each word strength.",
            ) as generate,
        ):
            response = client.post(
                "/api/v1/mario/chat",
                json={
                    "message": "What should I click next?",
                    "route": "/learn/daily",
                },
            )

        assert response.status_code == 200
        prompt = generate.await_args.args[0]
        assert "Daily words page" in prompt
        assert "Use the pronunciation button" in prompt
        assert "Set word strength with Weak, Learning, Good, or Mastered" in prompt
        assert "Do not mention a Complete Lesson button." in prompt

    def test_validates_empty_message(self, client):
        response = client.post(
            "/api/v1/mario/chat",
            json={"message": ""},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "common.validation"

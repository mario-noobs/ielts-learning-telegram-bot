"""Integration tests for POST /api/v1/users/link (US-1.7)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture()
def client():
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _stub_db():
    with patch("api.routes.auth.firebase_service._get_db", return_value=object()):
        yield


@pytest.fixture()
def valid_token():
    with patch("api.routes.auth.firebase_admin.auth.verify_id_token",
               return_value={"uid": "auth-123", "email": "x@y.com", "name": "New Name"}):
        yield "valid-token"


def _mk_record(telegram_id: int, ttl_seconds: int = 300) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "telegram_id": telegram_id,
        "created_at": now,
        "expires_at": now + timedelta(seconds=ttl_seconds),
    }


class TestLinkEndpoint:
    def test_happy_path_links_and_returns_profile(self, client, valid_token):
        telegram_user = {
            "id": "777",
            "name": "",
            "email": None,
            "target_band": 7.5,
            "topics": ["education"],
            "total_words": 42,
            "streak": 3,
        }
        with patch("api.routes.auth.firebase_service.get_link_code",
                   return_value=_mk_record(777)), \
             patch("api.routes.auth.firebase_service.get_user_by_auth_uid",
                   return_value=None), \
             patch("api.routes.auth.firebase_service.get_user",
                   return_value=telegram_user), \
             patch("api.routes.auth.firebase_service.link_telegram_to_auth") as mock_link, \
             patch("api.routes.auth.firebase_service.update_user") as mock_update, \
             patch("api.routes.auth.firebase_service.delete_link_code") as mock_delete:
            res = client.post(
                "/api/v1/users/link",
                json={"code": "123456"},
                headers={"Authorization": "Bearer valid-token"},
            )

        assert res.status_code == 200
        body = res.json()
        assert body["total_words"] == 42
        assert body["target_band"] == 7.5
        mock_link.assert_called_once_with(777, "auth-123")
        mock_delete.assert_called_once_with("123456")
        assert mock_update.called  # email/name merged

    def test_invalid_code_format_returns_400(self, client, valid_token):
        res = client.post(
            "/api/v1/users/link",
            json={"code": "abc"},
            headers={"Authorization": "Bearer valid-token"},
        )
        assert res.status_code == 400

    def test_missing_code_returns_404(self, client, valid_token):
        with patch("api.routes.auth.firebase_service.get_link_code", return_value=None):
            res = client.post(
                "/api/v1/users/link",
                json={"code": "123456"},
                headers={"Authorization": "Bearer valid-token"},
            )
        assert res.status_code == 404

    def test_expired_code_returns_410_and_deletes(self, client, valid_token):
        with patch("api.routes.auth.firebase_service.get_link_code",
                   return_value=_mk_record(777, ttl_seconds=-10)), \
             patch("api.routes.auth.firebase_service.delete_link_code") as mock_delete:
            res = client.post(
                "/api/v1/users/link",
                json={"code": "123456"},
                headers={"Authorization": "Bearer valid-token"},
            )
        assert res.status_code == 410
        mock_delete.assert_called_once_with("123456")

    def test_auth_uid_already_linked_to_other_telegram_user_returns_409(self, client, valid_token):
        other_user = {"id": "555", "target_band": 6.0, "topics": []}
        with patch("api.routes.auth.firebase_service.get_link_code",
                   return_value=_mk_record(777)), \
             patch("api.routes.auth.firebase_service.get_user_by_auth_uid",
                   return_value=other_user):
            res = client.post(
                "/api/v1/users/link",
                json={"code": "123456"},
                headers={"Authorization": "Bearer valid-token"},
            )
        assert res.status_code == 409

    def test_web_placeholder_is_repointed(self, client, valid_token):
        """Google users auto-registered as web_* should be repointed, not blocked."""
        placeholder = {"id": "web_abc", "target_band": 7.0, "topics": []}
        telegram_user = {
            "id": "777", "name": "Telegram User", "email": None,
            "target_band": 7.5, "topics": [], "total_words": 10,
        }
        with patch("api.routes.auth.firebase_service.get_link_code",
                   return_value=_mk_record(777)), \
             patch("api.routes.auth.firebase_service.get_user_by_auth_uid",
                   return_value=placeholder), \
             patch("api.routes.auth.firebase_service.get_user",
                   return_value=telegram_user), \
             patch("api.routes.auth.firebase_service.link_telegram_to_auth"), \
             patch("api.routes.auth.firebase_service.update_user"), \
             patch("api.routes.auth.firebase_service.delete_link_code"):
            res = client.post(
                "/api/v1/users/link",
                json={"code": "123456"},
                headers={"Authorization": "Bearer valid-token"},
            )
        assert res.status_code == 200

    def test_telegram_user_already_linked_elsewhere_returns_409(self, client, valid_token):
        telegram_user = {
            "id": "777", "target_band": 7.5, "topics": [],
            "auth_uid": "different-auth-uid",
        }
        with patch("api.routes.auth.firebase_service.get_link_code",
                   return_value=_mk_record(777)), \
             patch("api.routes.auth.firebase_service.get_user_by_auth_uid",
                   return_value=None), \
             patch("api.routes.auth.firebase_service.get_user",
                   return_value=telegram_user):
            res = client.post(
                "/api/v1/users/link",
                json={"code": "123456"},
                headers={"Authorization": "Bearer valid-token"},
            )
        assert res.status_code == 409

    def test_invalid_token_returns_401(self, client):
        with patch("api.routes.auth.firebase_admin.auth.verify_id_token",
                   side_effect=Exception("bad")):
            res = client.post(
                "/api/v1/users/link",
                json={"code": "123456"},
                headers={"Authorization": "Bearer bad-token"},
            )
        assert res.status_code == 401

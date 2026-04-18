"""Integration tests for /api/v1/audio/{word} (US-1.6)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth import get_current_user
from api.main import create_app

FAKE_USER = {"id": "test-user-1", "name": "Alice", "target_band": 7.0, "topics": []}


@pytest.fixture()
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    return TestClient(app)


@pytest.fixture()
def fake_mp3(tmp_path):
    path = tmp_path / "ubiquitous.mp3"
    path.write_bytes(b"ID3FAKEMP3BYTES")
    return str(path)


class TestAudioEndpoint:
    def test_returns_audio_with_cache_headers(self, client, fake_mp3):
        with patch("api.routes.audio.tts_service.generate_audio",
                   return_value=fake_mp3) as mock_fn:
            response = client.get("/api/v1/audio/ubiquitous")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("audio/mpeg")
        assert "max-age=86400" in response.headers["cache-control"]
        assert response.content == b"ID3FAKEMP3BYTES"
        mock_fn.assert_called_once_with("ubiquitous")

    def test_normalizes_word(self, client, fake_mp3):
        with patch("api.routes.audio.tts_service.generate_audio",
                   return_value=fake_mp3) as mock_fn:
            response = client.get("/api/v1/audio/%20UBIQUITOUS%20")

        assert response.status_code == 200
        mock_fn.assert_called_once_with("ubiquitous")

    def test_empty_word_returns_400(self, client):
        response = client.get("/api/v1/audio/%20")
        assert response.status_code == 400

    def test_tts_failure_returns_503(self, client):
        with patch("api.routes.audio.tts_service.generate_audio", return_value=None):
            response = client.get("/api/v1/audio/ubiquitous")
        assert response.status_code == 503

    def test_requires_auth(self):
        app = create_app()
        client_no_auth = TestClient(app)
        response = client_no_auth.get("/api/v1/audio/ubiquitous")
        assert response.status_code in (401, 403)

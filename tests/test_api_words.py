"""Integration tests for /api/v1/words/{word} (US-1.1)."""

from unittest.mock import AsyncMock, patch

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


def _enriched_fixture() -> dict:
    return {
        "word": "ubiquitous",
        "ipa": "/juːˈbɪkwɪtəs/",
        "syllable_stress": "u-BIK-wi-tous",
        "part_of_speech": "adjective",
        "definition_en": "Present, appearing, or found everywhere.",
        "definition_vi": "Hiện diện khắp nơi.",
        "word_family": ["ubiquity (n)", "ubiquitously (adv)"],
        "collocations": ["ubiquitous presence", "become ubiquitous"],
        "examples_by_band": {
            "7": {
                "en": "Smartphones have become ubiquitous in modern life.",
                "vi": "Điện thoại thông minh đã trở nên phổ biến khắp nơi.",
            }
        },
        "ielts_tip": "Strong Band 7+ vocabulary for Writing Task 2.",
    }


class TestEnrichedWord:
    def test_ac3_full_cache_hit_returns_enrichment(self, client):
        """AC3: GET /api/v1/words/ubiquitous returns full enrichment."""
        with patch("api.routes.words.word_service.get_enriched_word",
                   new=AsyncMock(return_value=_enriched_fixture())) as mock_fn:
            response = client.get("/api/v1/words/ubiquitous")

        assert response.status_code == 200
        body = response.json()
        assert body["word"] == "ubiquitous"
        assert body["ipa"] == "/juːˈbɪkwɪtəs/"
        assert "7" in body["examples_by_band"]
        assert body["examples_by_band"]["7"]["en"].startswith("Smartphones")
        assert len(body["collocations"]) == 2
        mock_fn.assert_called_once_with("ubiquitous", 7.0)

    def test_word_is_normalized_before_lookup(self, client):
        """Leading/trailing whitespace and caps are stripped."""
        with patch("api.routes.words.word_service.get_enriched_word",
                   new=AsyncMock(return_value=_enriched_fixture())) as mock_fn:
            response = client.get("/api/v1/words/%20UBIQUITOUS%20")

        assert response.status_code == 200
        mock_fn.assert_called_once_with("ubiquitous", 7.0)

    def test_partial_cache_hit_path_returns_data(self, client):
        """Cache miss / partial hit is handled by word_service — endpoint just serializes."""
        partial = _enriched_fixture()
        partial["examples_by_band"] = {}
        with patch("api.routes.words.word_service.get_enriched_word",
                   new=AsyncMock(return_value=partial)):
            response = client.get("/api/v1/words/ubiquitous")

        assert response.status_code == 200
        assert response.json()["examples_by_band"] == {}

    def test_user_target_band_forwarded(self, client):
        """Band from user profile is used for enrichment."""
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "u1", "target_band": 8.0, "topics": []
        }
        test_client = TestClient(app)

        with patch("api.routes.words.word_service.get_enriched_word",
                   new=AsyncMock(return_value=_enriched_fixture())) as mock_fn:
            response = test_client.get("/api/v1/words/ubiquitous")

        assert response.status_code == 200
        mock_fn.assert_called_once_with("ubiquitous", 8.0)

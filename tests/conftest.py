"""Shared fixtures for the test suite.

Environment variables and Firebase mocks are set up BEFORE any
application code is imported, so modules like config.py and
firebase_service.py never attempt real connections.
"""

import os

# Set env vars before any application imports
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("FIREBASE_CREDENTIALS_PATH", "test.json")

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True, scope="session")
def _mock_firebase():
    """Prevent Firebase SDK from initializing with real credentials."""
    with patch("firebase_admin.credentials.Certificate", return_value=MagicMock()), \
         patch("firebase_admin.initialize_app", return_value=MagicMock()):
        yield

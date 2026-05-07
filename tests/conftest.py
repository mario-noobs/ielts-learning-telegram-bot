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


@pytest.fixture(autouse=True)
def _wipe_ai_usage():
    """Reset the per-user AI quota counter at the start of every test.

    Once a route is wired with ``enforce_ai_quota`` (M11.2 part D), every
    request bumps ``ai_usage``. Without this fixture, counters bleed
    between tests for users that share an id (e.g. ``FAKE_USER`` in the
    existing API tests), and the 11th call across the suite trips a 429
    that has nothing to do with the test's intent.

    No-op when ``DATABASE_URL`` isn't set (Postgres-less test runs).
    """
    if not os.environ.get("DATABASE_URL"):
        yield
        return

    from sqlalchemy import delete

    from services.db import get_sync_session
    from services.db.models import AiUsage

    with get_sync_session() as s, s.begin():
        s.execute(delete(AiUsage))
    yield

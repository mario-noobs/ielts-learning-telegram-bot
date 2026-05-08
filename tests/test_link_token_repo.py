"""US-M12.2 ``PostgresLinkTokenRepo`` round-trips."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping Postgres link_token tests",
)


@pytest.fixture(autouse=True)
def _truncate():
    from services.db import get_sync_session
    from services.db.models import LinkToken

    with get_sync_session() as s, s.begin():
        s.execute(delete(LinkToken))
    yield
    with get_sync_session() as s, s.begin():
        s.execute(delete(LinkToken))


def _repo():
    from services.repositories.postgres import PostgresLinkTokenRepo
    return PostgresLinkTokenRepo()


# ── create ────────────────────────────────────────────────────────────

def test_create_tg_to_web_token():
    doc = _repo().create(direction="tg_to_web", telegram_id=42, ttl_seconds=900)
    assert doc.token
    assert len(doc.token) >= 30  # secrets.token_urlsafe(24) → ~32 chars
    assert doc.direction == "tg_to_web"
    assert doc.telegram_id == 42
    assert doc.auth_uid is None
    assert doc.redeemed_at is None
    assert doc.expires_at > doc.created_at


def test_create_web_to_tg_token():
    doc = _repo().create(direction="web_to_tg", auth_uid="auth-foo", ttl_seconds=900)
    assert doc.direction == "web_to_tg"
    assert doc.telegram_id is None
    assert doc.auth_uid == "auth-foo"


def test_create_rejects_bad_direction():
    with pytest.raises(ValueError, match="unknown direction"):
        _repo().create(direction="sideways", telegram_id=1)


def test_create_tg_to_web_requires_telegram_id():
    with pytest.raises(ValueError, match="requires telegram_id"):
        _repo().create(direction="tg_to_web")


def test_create_web_to_tg_requires_auth_uid():
    with pytest.raises(ValueError, match="requires auth_uid"):
        _repo().create(direction="web_to_tg")


# ── redeem ───────────────────────────────────────────────────────────

def test_redeem_marks_token_used_returns_doc():
    repo = _repo()
    minted = repo.create(direction="tg_to_web", telegram_id=42)

    redeemed = repo.redeem(minted.token, redeemed_by="auth-zzz")
    assert redeemed is not None
    assert redeemed.token == minted.token
    assert redeemed.redeemed_at is not None
    assert redeemed.redeemed_by == "auth-zzz"


def test_redeem_returns_none_for_unknown_token():
    assert _repo().redeem("not-a-real-token", redeemed_by="x") is None


def test_redeem_single_use_second_call_returns_none():
    repo = _repo()
    minted = repo.create(direction="tg_to_web", telegram_id=42)
    assert repo.redeem(minted.token, redeemed_by="a") is not None
    assert repo.redeem(minted.token, redeemed_by="b") is None


def test_redeem_returns_none_for_expired_token():
    """Force expires_at into the past via a direct UPDATE, then redeem."""
    from services.db import get_sync_session
    from services.db.models import LinkToken
    repo = _repo()
    minted = repo.create(direction="tg_to_web", telegram_id=42, ttl_seconds=60)

    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    with get_sync_session() as s, s.begin():
        row = s.get(LinkToken, minted.token)
        row.expires_at = past

    assert repo.redeem(minted.token, redeemed_by="x") is None


# ── cleanup_expired ──────────────────────────────────────────────────

def test_cleanup_expired_keeps_recent_expiry():
    """Tokens that expired but within the debug window are NOT deleted."""
    from services.db import get_sync_session
    from services.db.models import LinkToken
    repo = _repo()
    minted = repo.create(direction="tg_to_web", telegram_id=99)

    # Move expires_at to 1 hour ago — still within the 24h debug window.
    short_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    with get_sync_session() as s, s.begin():
        s.get(LinkToken, minted.token).expires_at = short_ago

    deleted = repo.cleanup_expired(older_than_seconds=24 * 3600)
    assert deleted == 0


def test_cleanup_expired_drops_old_rows():
    from services.db import get_sync_session
    from services.db.models import LinkToken
    repo = _repo()
    minted = repo.create(direction="tg_to_web", telegram_id=99)

    long_ago = datetime.now(timezone.utc) - timedelta(days=2)
    with get_sync_session() as s, s.begin():
        s.get(LinkToken, minted.token).expires_at = long_ago

    deleted = repo.cleanup_expired(older_than_seconds=24 * 3600)
    assert deleted == 1
    with get_sync_session() as s:
        rows = s.execute(select(LinkToken)).scalars().all()
    assert rows == []


# ── get ──────────────────────────────────────────────────────────────

def test_get_returns_doc_or_none():
    repo = _repo()
    minted = repo.create(direction="web_to_tg", auth_uid="auth-zz")
    fetched = repo.get(minted.token)
    assert fetched is not None
    assert fetched.token == minted.token
    assert repo.get("missing") is None

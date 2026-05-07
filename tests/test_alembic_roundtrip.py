"""Alembic upgrade/downgrade round-trip on the configured DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping Alembic round-trip test",
)


def _alembic_cfg() -> Config:
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    return cfg


def test_upgrade_downgrade_roundtrip() -> None:
    cfg = _alembic_cfg()
    # Land at head, then walk back to base, then forward again.
    # Net effect: starts and ends at head; assertion is "no exception".
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

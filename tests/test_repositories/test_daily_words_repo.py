"""Tests for ``services.repositories.firestore.daily_words_repo``."""

from __future__ import annotations

from services.repositories import (
    DailyWordsDoc,
    get_daily_words_repo,
    get_user_repo,
)
from services.repositories.firestore import FirestoreDailyWordsRepo

# ── save / get ──────────────────────────────────────────────────────

def test_save_and_get_round_trip(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_daily_words_repo()

    words = [
        {"word": "resilient", "definition_en": "able to withstand"},
        {"word": "diligent", "definition_en": "careful and persistent"},
    ]
    repo.save(1, "2026-04-18", words, topic="character")

    fetched = repo.get(1, "2026-04-18")
    assert fetched is not None
    assert isinstance(fetched, DailyWordsDoc)
    assert fetched.id == "2026-04-18"
    assert fetched.topic == "character"
    assert fetched.words == words
    assert fetched.generated_at == frozen_now


def test_get_missing_returns_none(fake_db):
    get_user_repo().create(1, "A")
    assert get_daily_words_repo().get(1, "2026-04-18") is None


def test_save_overwrites_existing_doc(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_daily_words_repo()
    repo.save(1, "2026-04-18", [{"word": "old"}], "initial")
    repo.save(1, "2026-04-18", [{"word": "new"}], "replacement")

    fetched = repo.get(1, "2026-04-18")
    assert fetched.topic == "replacement"
    assert fetched.words == [{"word": "new"}]


def test_save_scoped_to_user(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    get_user_repo().create(2, "B")
    repo = get_daily_words_repo()

    repo.save(1, "2026-04-18", [{"word": "alpha"}], "x")
    repo.save(2, "2026-04-18", [{"word": "beta"}], "y")

    assert repo.get(1, "2026-04-18").words == [{"word": "alpha"}]
    assert repo.get(2, "2026-04-18").words == [{"word": "beta"}]


def test_save_scoped_to_date(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_daily_words_repo()

    repo.save(1, "2026-04-18", [{"word": "today"}], "x")
    repo.save(1, "2026-04-19", [{"word": "tomorrow"}], "y")

    assert repo.get(1, "2026-04-18").words == [{"word": "today"}]
    assert repo.get(1, "2026-04-19").words == [{"word": "tomorrow"}]


# ── Protocol conformance ────────────────────────────────────────────

def test_firestore_impl_satisfies_protocol():
    from services.repositories.protocols import DailyWordsRepo

    assert isinstance(FirestoreDailyWordsRepo(), DailyWordsRepo)

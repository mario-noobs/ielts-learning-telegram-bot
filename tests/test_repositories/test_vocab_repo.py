"""Tests for ``services.repositories.firestore.vocab_repo``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import config
from services.repositories import (
    VocabularyItem,
    get_user_repo,
    get_vocab_repo,
)
from services.repositories.firestore import FirestoreVocabRepo

# ── add_word ────────────────────────────────────────────────────────

def test_add_word_creates_doc_and_bumps_counter(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()

    word_id = repo.add_word(1, {"word": "resilient", "topic": "psychology"})
    assert isinstance(word_id, str) and word_id

    # Word should be retrievable
    item = repo.get_by_id(1, word_id)
    assert item is not None
    assert item.word == "resilient"
    assert item.topic == "psychology"
    assert item.srs_interval == config.SRS_INITIAL_INTERVAL
    assert item.srs_ease == config.SRS_INITIAL_EASE
    assert item.srs_next_review == frozen_now
    assert item.added_at == frozen_now

    # total_words bumped on parent user doc
    user = get_user_repo().get(1)
    assert user.total_words == 1


def test_add_word_returns_vocabulary_item_dto(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    word_id = repo.add_word(1, {"word": "cat"})
    item = repo.get_by_id(1, word_id)
    assert isinstance(item, VocabularyItem)


# ── add_word_if_not_exists ──────────────────────────────────────────

def test_add_word_if_not_exists_creates_when_missing(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    word_id, created = repo.add_word_if_not_exists(1, {"word": "Resilient"})
    assert created is True
    assert word_id

    item = repo.get_by_id(1, word_id)
    assert item.word == "resilient"  # normalized to lowercase
    assert get_user_repo().get(1).total_words == 1


def test_add_word_if_not_exists_is_idempotent(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    id1, c1 = repo.add_word_if_not_exists(1, {"word": "abundant"})
    id2, c2 = repo.add_word_if_not_exists(1, {"word": "  Abundant "})

    assert c1 is True
    assert c2 is False
    assert id1 == id2
    # counter only incremented once
    assert get_user_repo().get(1).total_words == 1


# ── list_by_user ────────────────────────────────────────────────────

def test_list_by_user_orders_by_added_at_desc(fake_db):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    base = datetime(2026, 4, 10, tzinfo=timezone.utc)

    # Directly seed docs with distinct added_at so we can assert order
    for i in range(3):
        word_id = repo.add_word(1, {"word": f"word{i}"})
        repo.update_srs(1, word_id, {"added_at": base + timedelta(days=i)})

    items = repo.list_by_user(1, limit=10)
    assert [i.word for i in items] == ["word2", "word1", "word0"]


def test_list_by_user_respects_limit(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    for i in range(5):
        repo.add_word(1, {"word": f"w{i}"})
    assert len(repo.list_by_user(1, limit=3)) == 3


# ── list_word_strings ───────────────────────────────────────────────

def test_list_word_strings(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    repo.add_word(1, {"word": "alpha"})
    repo.add_word(1, {"word": "beta"})

    words = repo.list_word_strings(1)
    assert sorted(words) == ["alpha", "beta"]


# ── list_page (cursor) ──────────────────────────────────────────────

def test_list_page_cursor(fake_db):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    base = datetime(2026, 4, 10, tzinfo=timezone.utc)
    ids = []
    for i in range(5):
        wid = repo.add_word(1, {"word": f"w{i}"})
        repo.update_srs(1, wid, {"added_at": base + timedelta(days=i)})
        ids.append((wid, base + timedelta(days=i)))

    # First page, descending
    page1 = repo.list_page(1, limit=2)
    assert [i.word for i in page1] == ["w4", "w3"]

    # Cursor after the last one in page1
    page2 = repo.list_page(1, limit=2, after_added_at=page1[-1].added_at)
    assert [i.word for i in page2] == ["w2", "w1"]


# ── count_by_topic ──────────────────────────────────────────────────

def test_count_by_topic(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    repo.add_word(1, {"word": "tree", "topic": "environment"})
    repo.add_word(1, {"word": "river", "topic": "environment"})
    repo.add_word(1, {"word": "algorithm", "topic": "technology"})
    repo.add_word(1, {"word": "untopic"})  # no topic — excluded

    counts = repo.count_by_topic(1)
    assert counts == {"environment": 2, "technology": 1}


# ── get_mastered ────────────────────────────────────────────────────

def test_get_mastered_filters_by_interval(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    w1 = repo.add_word(1, {"word": "easy"})
    w2 = repo.add_word(1, {"word": "medium"})
    w3 = repo.add_word(1, {"word": "hard"})

    repo.update_srs(1, w1, {"srs_interval": 45})   # mastered
    repo.update_srs(1, w2, {"srs_interval": 31})   # mastered
    repo.update_srs(1, w3, {"srs_interval": 10})   # not

    mastered = repo.get_mastered(1)
    words = sorted(m.word for m in mastered)
    assert words == ["easy", "medium"]


# ── get_due ─────────────────────────────────────────────────────────

def test_get_due_filters_by_next_review(fake_db):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    now = datetime.now(timezone.utc)

    w1 = repo.add_word(1, {"word": "overdue"})
    w2 = repo.add_word(1, {"word": "future"})

    repo.update_srs(1, w1, {"srs_next_review": now - timedelta(days=1)})
    repo.update_srs(1, w2, {"srs_next_review": now + timedelta(days=5)})

    due = repo.get_due(1, limit=10)
    due_words = [d.word for d in due]
    assert "overdue" in due_words
    assert "future" not in due_words


def test_get_due_respects_limit(fake_db):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    now = datetime.now(timezone.utc)
    for i in range(5):
        wid = repo.add_word(1, {"word": f"w{i}"})
        repo.update_srs(1, wid, {"srs_next_review": now - timedelta(hours=i)})
    assert len(repo.get_due(1, limit=2)) == 2


# ── get_by_id ───────────────────────────────────────────────────────

def test_get_by_id_missing_returns_none(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    assert get_vocab_repo().get_by_id(1, "does-not-exist") is None


# ── DTO round-trip ──────────────────────────────────────────────────

def test_vocabulary_item_dto_round_trip(fake_db, frozen_now):
    get_user_repo().create(1, "A")
    repo = get_vocab_repo()
    wid = repo.add_word(1, {
        "word": "abundance",
        "topic": "finance",
        "ipa": "/əˈbʌn.dəns/",
    })
    item = repo.get_by_id(1, wid)
    dumped = item.model_dump()
    assert dumped["word"] == "abundance"
    assert dumped["ipa"] == "/əˈbʌn.dəns/"
    assert dumped["topic"] == "finance"


# ── Protocol conformance ────────────────────────────────────────────

def test_firestore_impl_satisfies_protocol():
    from services.repositories.protocols import VocabRepo

    assert isinstance(FirestoreVocabRepo(), VocabRepo)

"""Block-E+F Postgres repo smoke tests (M8 #234) — content + auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from services import feature_flag_service, firebase_service
from services.db import get_sync_session


@pytest.fixture(autouse=True)
def _reset_flag_cache():
    """Each test starts with a clean flag cache so set_flag/delete_flag are isolated."""
    feature_flag_service._cache.clear()
    yield
    feature_flag_service._cache.clear()


def test_reading_questions_round_trip():
    pid = "p_test_unit"
    firebase_service.save_cached_reading_questions(pid, {
        "questions_client": [{"id": "q1", "stem": "?"}],
        "answer_key": [{"id": "q1", "answer": "A"}],
    })
    out = firebase_service.get_cached_reading_questions(pid)
    assert out["questions_client"][0]["stem"] == "?"
    assert out["answer_key"][0]["answer"] == "A"

    with get_sync_session() as s, s.begin():
        s.execute(
            text("DELETE FROM reading_questions WHERE passage_id = :p"),
            {"p": pid},
        )


def test_enriched_word_update_example_merges():
    word = "test_unit_word"
    firebase_service.set_enriched_word_doc(word, {
        "ipa": "/t/",
        "examples_by_band": {"b6": "demo"},
    })
    firebase_service.update_enriched_word_example(word, "b7", "better demo")
    out = firebase_service.get_enriched_word_doc(word)
    assert out["examples_by_band"] == {"b6": "demo", "b7": "better demo"}

    with get_sync_session() as s, s.begin():
        s.execute(
            text("DELETE FROM enriched_words WHERE word = :w"),
            {"w": word},
        )


def test_feature_flag_set_then_evaluate():
    feature_flag_service.set_flag(
        "unit_test_flag", enabled=True, rollout_pct=100,
    )
    assert feature_flag_service.is_enabled("unit_test_flag", uid="any") is True

    feature_flag_service.set_flag("unit_test_flag", enabled=False)
    feature_flag_service._cache.clear()  # invalidate cache so fresh DB read
    assert feature_flag_service.is_enabled("unit_test_flag", uid="any") is False

    feature_flag_service.delete_flag("unit_test_flag")


def test_feature_flag_uid_allowlist_overrides_rollout():
    feature_flag_service.set_flag(
        "unit_allow_flag",
        enabled=True,
        rollout_pct=0,  # nobody by percent
        uid_allowlist=["alice"],
    )
    feature_flag_service._cache.clear()
    assert feature_flag_service.is_enabled("unit_allow_flag", uid="alice") is True
    assert feature_flag_service.is_enabled("unit_allow_flag", uid="bob") is False

    feature_flag_service.delete_flag("unit_allow_flag")


def test_auth_link_code_create_get_delete():
    code = "unit_test_code_123"
    firebase_service.create_link_code(code, telegram_id=99887766)
    out = firebase_service.get_link_code(code)
    assert out["telegram_id"] == 99887766
    assert out["expires_at"] > datetime.now(timezone.utc)

    firebase_service.delete_link_code(code)
    assert firebase_service.get_link_code(code) is None


def test_cleanup_expired_drops_only_past_link_codes():
    fresh = "unit_fresh_code"
    stale = "unit_stale_code"
    firebase_service.create_link_code(fresh, telegram_id=1)
    firebase_service.create_link_code(stale, telegram_id=2)

    # Backdate stale's expires_at into the past.
    with get_sync_session() as s, s.begin():
        s.execute(
            text(
                "UPDATE auth_link_codes SET expires_at = :ts WHERE code = :c"
            ),
            {
                "ts": datetime.now(timezone.utc) - timedelta(days=1),
                "c": stale,
            },
        )

    from scripts.cleanup_expired import cleanup_auth_link_codes
    cleanup_auth_link_codes()

    assert firebase_service.get_link_code(stale) is None
    assert firebase_service.get_link_code(fresh) is not None
    firebase_service.delete_link_code(fresh)

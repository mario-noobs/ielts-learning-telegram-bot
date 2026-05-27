"""Tests for services/word_service.py."""

from unittest.mock import AsyncMock

import pytest

from services import word_service
from services.word_service import band_tier, normalize_word

# ---------------------------------------------------------------------------
# normalize_word
# ---------------------------------------------------------------------------


class TestNormalizeWord:
    def test_strips_leading_whitespace(self):
        assert normalize_word("  hello") == "hello"

    def test_strips_trailing_whitespace(self):
        assert normalize_word("hello  ") == "hello"

    def test_strips_both_sides(self):
        assert normalize_word("  hello  ") == "hello"

    def test_lowercases(self):
        assert normalize_word("HELLO") == "hello"

    def test_mixed_case_and_whitespace(self):
        assert normalize_word("  HeLLo WoRLd  ") == "hello world"

    def test_already_normalized(self):
        assert normalize_word("hello") == "hello"

    def test_empty_string(self):
        assert normalize_word("") == ""

    def test_tabs_and_newlines(self):
        assert normalize_word("\thello\n") == "hello"


# ---------------------------------------------------------------------------
# band_tier
# ---------------------------------------------------------------------------


class TestBandTier:
    def test_below_6_returns_5(self):
        assert band_tier(5.0) == "5"

    def test_5_5_returns_5(self):
        assert band_tier(5.5) == "5"

    def test_5_9_returns_5(self):
        assert band_tier(5.9) == "5"

    def test_6_0_returns_6(self):
        assert band_tier(6.0) == "6"

    def test_6_5_returns_6(self):
        assert band_tier(6.5) == "6"

    def test_6_9_returns_6(self):
        assert band_tier(6.9) == "6"

    def test_7_0_returns_7(self):
        assert band_tier(7.0) == "7"

    def test_7_5_returns_7(self):
        assert band_tier(7.5) == "7"

    def test_7_9_returns_7(self):
        assert band_tier(7.9) == "7"

    def test_8_0_returns_8(self):
        assert band_tier(8.0) == "8"

    def test_8_5_returns_8(self):
        assert band_tier(8.5) == "8"

    def test_9_0_returns_8(self):
        assert band_tier(9.0) == "8"

    def test_low_band_returns_5(self):
        assert band_tier(4.0) == "5"


@pytest.mark.asyncio
async def test_empty_freedict_synonyms_do_not_call_gemini(monkeypatch):
    monkeypatch.setattr(
        word_service,
        "_fetch_synonyms_antonyms_sync",
        lambda word: ([], [], "freedict"),
    )
    gemini = AsyncMock()
    monkeypatch.setattr(word_service.ai_service, "generate_json", gemini)

    syns, ants, source = await word_service._fetch_synonyms_antonyms("opaque")

    assert syns == []
    assert ants == []
    assert source == "freedict"
    gemini.assert_not_awaited()


@pytest.mark.asyncio
async def test_fast_detail_cache_hit_schedules_backfill(monkeypatch):
    cached = {
        "word": "ubiquitous",
        "definition_en": "Present everywhere.",
        "examples_by_band": {"7": {"en": "Example.", "vi": ""}},
        "synonyms": None,
    }
    scheduled = {}
    monkeypatch.setattr(
        word_service.firebase_service,
        "get_enriched_word_doc",
        lambda word: cached,
    )
    monkeypatch.setattr(
        word_service,
        "_schedule_metadata_backfill",
        lambda word, data: scheduled.update({"word": word, "data": data}),
    )

    result = await word_service.get_word_detail_fast(" UBIQUITOUS ", 7.0)

    assert result is cached
    assert scheduled["word"] == "ubiquitous"


@pytest.mark.asyncio
async def test_fast_detail_schedules_backfill_when_antonyms_missing(monkeypatch):
    cached = {
        "word": "ubiquitous",
        "definition_en": "Present everywhere.",
        "examples_by_band": {"7": {"en": "Example.", "vi": ""}},
        "synonyms": {"words": ["common"], "source": "test"},
        "antonyms": None,
    }
    scheduled = {}
    monkeypatch.setattr(
        word_service.firebase_service,
        "get_enriched_word_doc",
        lambda word: cached,
    )
    monkeypatch.setattr(
        word_service,
        "_schedule_metadata_backfill",
        lambda word, data: scheduled.update({"word": word, "data": data}),
    )

    result = await word_service.get_word_detail_fast("ubiquitous", 7.0)

    assert result is cached
    assert scheduled["word"] == "ubiquitous"


@pytest.mark.asyncio
async def test_fast_detail_uses_master_when_cache_misses(monkeypatch):
    master = {
        "word": "deficit",
        "definition_en": "A shortfall.",
        "examples_by_band": {"7": {"en": "A deficit grew.", "vi": ""}},
        "synonyms": {"words": ["shortfall"], "source": "wordlevel"},
    }
    monkeypatch.setattr(
        word_service.firebase_service,
        "get_enriched_word_doc",
        lambda word: None,
    )
    monkeypatch.setattr(word_service, "get_master_word_detail", lambda word, band: master)
    monkeypatch.setattr(word_service, "_schedule_metadata_backfill", lambda word, data: None)

    result = await word_service.get_word_detail_fast("deficit", 7.0)

    assert result is master


@pytest.mark.asyncio
async def test_backfill_caches_master_detail(monkeypatch):
    cached = {
        "source": "vocabulary_master",
        "word": "deficit",
        "synonyms": {"words": ["shortfall"], "source": "wordlevel"},
        "image_url": None,
    }
    writes = []
    monkeypatch.setattr(
        word_service.firebase_service,
        "set_enriched_word_doc",
        lambda word, data: writes.append((word, data)),
    )
    monkeypatch.setattr(word_service.config, "UNSPLASH_ACCESS_KEY", "")

    await word_service._backfill_missing_metadata("deficit", cached)

    assert writes == [("deficit", cached)]


@pytest.mark.asyncio
async def test_backfill_fetches_metadata_when_only_antonyms_missing(monkeypatch):
    cached = {
        "word": "deficit",
        "synonyms": {"words": ["shortfall"], "source": "test"},
        "antonyms": None,
        "image_url": None,
    }
    writes = []
    monkeypatch.setattr(word_service.config, "UNSPLASH_ACCESS_KEY", "")
    monkeypatch.setattr(
        word_service,
        "_fetch_synonyms_antonyms",
        AsyncMock(return_value=(["shortfall"], ["surplus"], "freedict")),
    )
    monkeypatch.setattr(
        word_service.firebase_service,
        "update_enriched_word_synonyms_antonyms",
        lambda word, syns, ants, source: writes.append((word, syns, ants, source)),
    )

    await word_service._backfill_missing_metadata("deficit", cached)

    assert writes == [("deficit", ["shortfall"], ["surplus"], "freedict")]


def test_core_detail_complete_ignores_metadata(monkeypatch):
    monkeypatch.setattr(word_service.config, "UNSPLASH_ACCESS_KEY", "key")
    data = {
        "ipa": "/test/",
        "syllable_stress": "TEST",
        "part_of_speech": "noun",
        "definition_en": "A definition.",
        "definition_vi": "Một định nghĩa.",
        "collocations": [{"phrase": "test phrase", "label": "neutral"}],
        "word_family": ["test"],
        "ielts_tip": "Use it carefully.",
        "examples_by_band": {"7": {"en": "Example.", "vi": "Ví dụ."}},
        "synonyms": None,
        "antonyms": None,
        "image_url": None,
    }

    assert word_service.is_word_core_detail_complete(data, 7.0) is True
    assert word_service.is_word_detail_complete(data, 7.0) is False

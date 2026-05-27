"""Daily vocab dedup + topic rotation (US-#226).

Pure-functional helpers in `services.vocab_service`. AI calls are
mocked via `ai_service.generate_vocabulary` so the suite runs without
network or Gemini/Groq keys.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services import vocab_service

# ─── Topic rotation ────────────────────────────────────────────────────


def test_pick_topic_avoids_recent_n():
    """Recent A,B,C → must pick from {D,E,...}."""
    topics = ["A", "B", "C", "D", "E"]
    recent = ["A", "B", "C"]
    pick = vocab_service._pick_topic_avoiding_recent(topics, recent)
    assert pick in ("D", "E")


def test_pick_topic_falls_back_when_all_recent():
    """Group has 3 topics, all recently used → fall back to full list."""
    topics = ["A", "B", "C"]
    recent = ["A", "B", "C", "A"]  # all topics in recent
    pick = vocab_service._pick_topic_avoiding_recent(topics, recent)
    assert pick in topics  # whatever — just don't raise


def test_push_recent_topic_caps_fifo():
    """List is bounded to RECENT_TOPICS_KEEP — oldest entry drops."""
    recent = ["A", "B", "C", "D", "E"]
    out = vocab_service._push_recent_topic(recent, "F")
    assert out == ["B", "C", "D", "E", "F"]
    assert len(out) == vocab_service.RECENT_TOPICS_KEEP


# ─── Dedup ─────────────────────────────────────────────────────────────


def test_filter_dupes_drops_existing_and_intra_batch_dupes():
    existing = {"hello", "world"}
    words = [
        {"word": "Hello"},      # case-insensitive match → drop
        {"word": " world  "},   # whitespace → drop
        {"word": "fresh"},      # keep
        {"word": "fresh"},      # intra-batch dupe → drop
        {"word": ""},           # empty → drop
    ]
    out = vocab_service._filter_dupes_lc(words, existing)
    assert [w["word"] for w in out] == ["fresh"]


def test_weighted_topics_prefer_private_vocab_topics():
    out = vocab_service._weighted_topics_with_private_context(
        ["education", "environment"],
        {"technology": 7, "health": 3},
    )

    assert out[:4] == ["technology", "technology", "health", "health"]
    assert out[-2:] == ["education", "environment"]


@pytest.mark.asyncio
async def test_generate_with_dedup_tops_up_when_short():
    """AI returns 3 words but 2 are dupes → top-up retry fills the gap."""
    existing = {"alpha", "beta"}
    primary = [
        {"word": "alpha"},      # dupe
        {"word": "beta"},       # dupe
        {"word": "gamma"},      # fresh
    ]
    topup = [{"word": "delta"}, {"word": "epsilon"}]

    # Two distinct calls → two return values.
    mock = AsyncMock(side_effect=[primary, topup])
    with patch.object(vocab_service.ai_service, "generate_vocabulary", mock):
        out = await vocab_service._generate_with_dedup(
            count=3, band=7.0, topic="education", existing_lc=existing,
        )
    words = [w["word"] for w in out]
    # Should land at exactly 3, no dupes against existing or each other.
    assert len(words) == 3
    assert "gamma" in words
    assert "delta" in words or "epsilon" in words
    # AI was called twice (primary + one top-up)
    assert mock.await_count == 2


@pytest.mark.asyncio
async def test_generate_with_dedup_returns_short_when_topup_fails():
    """AI's top-up call raises → return what we have rather than blowing up."""
    existing: set[str] = set()
    primary = [{"word": "only_one"}]

    async def first_then_raise(**kwargs):
        if not first_then_raise.called:
            first_then_raise.called = True
            return primary
        raise RuntimeError("AI down")
    first_then_raise.called = False

    with patch.object(
        vocab_service.ai_service, "generate_vocabulary",
        side_effect=first_then_raise,
    ):
        out = await vocab_service._generate_with_dedup(
            count=5, band=7.0, topic="education", existing_lc=existing,
        )
    assert [w["word"] for w in out] == ["only_one"]


@pytest.mark.asyncio
async def test_generate_with_master_first_skips_ai_when_master_has_enough():
    master = [
        {"word": "deficit", "definition_en": "shortfall"},
        {"word": "equilibrium", "definition_en": "balance"},
    ]
    with patch.object(vocab_service, "_select_master_words", return_value=master), \
            patch.object(vocab_service.ai_service, "generate_vocabulary", AsyncMock()) as mock:
        out = await vocab_service._generate_with_master_first(
            count=2, band=7.0, topic="Economy & Business", existing_lc=set(),
        )

    assert [w["word"] for w in out] == ["deficit", "equilibrium"]
    mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_with_master_first_tops_up_with_ai_when_master_short():
    master = [{"word": "deficit", "definition_en": "shortfall"}]
    ai_words = [{"word": "tariff", "definition_en": "tax"}]
    mock = AsyncMock(return_value=ai_words)
    with patch.object(vocab_service, "_select_master_words", return_value=master), \
            patch.object(vocab_service.ai_service, "generate_vocabulary", mock):
        out = await vocab_service._generate_with_master_first(
            count=2, band=7.0, topic="Economy & Business", existing_lc=set(),
        )

    assert [w["word"] for w in out] == ["deficit", "tariff"]
    assert mock.await_count == 1
    assert "deficit" in mock.await_args.kwargs["exclude_words"]


@pytest.mark.asyncio
async def test_personal_daily_uses_my_words_context_and_excludes_existing():
    ai_words = [{"word": "throughput", "definition_en": "amount processed"}]
    with patch.object(vocab_service.firebase_service, "get_user",
                      return_value={"recent_personal_topics": []}), \
            patch.object(vocab_service.firebase_service, "count_words_by_topic",
                         return_value={"technology": 5}), \
            patch.object(vocab_service.firebase_service, "get_user_vocabulary_page",
                         return_value=[
                             {"word": "latency"},
                             {"word": "scalability"},
                         ]) as recent_words, \
            patch.object(vocab_service.firebase_service, "get_user_word_list",
                         return_value=["latency"]), \
            patch.object(vocab_service.firebase_service, "update_user"), \
            patch.object(vocab_service, "_select_master_words", return_value=[]), \
            patch.object(vocab_service, "_pick_topic_avoiding_recent",
                         return_value="technology") as pick_topic, \
            patch.object(vocab_service.ai_service, "generate_vocabulary",
                         AsyncMock(return_value=ai_words)) as mock_ai:
        words, topic = await vocab_service.generate_personal_daily_words(
            telegram_id=123,
            count=1,
            band=7.0,
            topics=["education", "environment"],
            context_words=["cloud"],
        )

    assert topic == "Technology & Innovation"
    assert [w["word"] for w in words] == ["throughput"]
    pick_topic.assert_called_once_with(
        ["technology", "technology", "education", "environment"],
        [],
    )
    recent_words.assert_called_once_with(123, 10, None, None, None, 3)
    assert "latency" in mock_ai.await_args.kwargs["exclude_words"]
    prompt_topic = mock_ai.await_args.kwargs["topic"]
    assert "cloud" in prompt_topic
    assert "scalability" in prompt_topic


@pytest.mark.asyncio
async def test_stream_personal_daily_yields_after_first_ai_batch():
    first_batch = [{"word": f"word{i}", "definition_en": "d"} for i in range(5)]
    second_batch = [{"word": "word5", "definition_en": "d"}]
    mock_ai = AsyncMock(side_effect=[first_batch, second_batch])

    with patch.object(vocab_service.firebase_service, "get_user",
                      return_value={"recent_personal_topics": []}), \
            patch.object(vocab_service.firebase_service, "count_words_by_topic",
                         return_value={}), \
            patch.object(vocab_service.firebase_service, "get_user_vocabulary_page",
                         return_value=[]), \
            patch.object(vocab_service.firebase_service, "get_user_word_list",
                         return_value=[]), \
            patch.object(vocab_service.firebase_service, "update_user"), \
            patch.object(vocab_service, "_select_master_words", return_value=[]), \
            patch.object(vocab_service, "_pick_topic_avoiding_recent",
                         return_value="education"), \
            patch.object(vocab_service.ai_service, "generate_vocabulary", mock_ai):
        stream = vocab_service.stream_personal_daily_words(
            telegram_id=123,
            count=6,
            band=7.0,
            topics=["education"],
        )

        start = await stream.__anext__()
        first_word = await stream.__anext__()
        await stream.aclose()

    assert start["type"] == "start"
    assert first_word == {"type": "word", "word": first_batch[0]}
    assert mock_ai.await_count == 1

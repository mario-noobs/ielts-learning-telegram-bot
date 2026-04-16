"""Tests for services/word_service.py — normalize_word and band_tier."""

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

"""Tests for bot/utils.py — message splitting and Markdown stripping."""

from bot.utils import split_message, strip_markdown

# ---------------------------------------------------------------------------
# split_message
# ---------------------------------------------------------------------------


class TestSplitMessage:
    def test_short_text_returns_single_chunk(self):
        text = "Hello world"
        result = split_message(text, limit=100)

        assert result == ["Hello world"]

    def test_exact_limit_length_no_split(self):
        text = "x" * 100
        result = split_message(text, limit=100)

        assert result == [text]

    def test_splits_at_newline(self):
        line1 = "a" * 50
        line2 = "b" * 50
        text = f"{line1}\n{line2}"
        result = split_message(text, limit=60)

        assert len(result) == 2
        assert result[0] == line1
        assert result[1] == line2

    def test_splits_at_space_when_no_newline(self):
        word1 = "a" * 40
        word2 = "b" * 40
        text = f"{word1} {word2}"
        result = split_message(text, limit=50)

        assert len(result) == 2
        assert result[0] == word1
        # split_message only strips newlines, so leading space remains
        assert result[1].strip() == word2

    def test_hard_splits_when_no_space_or_newline(self):
        text = "a" * 200
        result = split_message(text, limit=100)

        assert len(result) == 2
        assert result[0] == "a" * 100
        assert result[1] == "a" * 100

    def test_empty_string(self):
        result = split_message("", limit=100)

        assert result == [""]

    def test_multiple_chunks(self):
        lines = [f"line{i}" for i in range(20)]
        text = "\n".join(lines)
        result = split_message(text, limit=30)

        # All original content should be preserved
        rejoined = "\n".join(result)
        assert all(f"line{i}" in rejoined for i in range(20))

    def test_preserves_content(self):
        text = "Hello\nWorld\nFoo\nBar"
        result = split_message(text, limit=12)

        # Rejoin and verify content is intact
        combined = "\n".join(result)
        assert "Hello" in combined
        assert "World" in combined
        assert "Foo" in combined
        assert "Bar" in combined

    def test_default_limit_is_tg_safe_length(self):
        from bot.utils import TG_SAFE_LENGTH

        short = "x" * (TG_SAFE_LENGTH - 1)
        result = split_message(short)

        assert result == [short]


# ---------------------------------------------------------------------------
# strip_markdown
# ---------------------------------------------------------------------------


class TestStripMarkdown:
    def test_removes_bold_markers(self):
        assert strip_markdown("This is *bold* text") == "This is bold text"

    def test_removes_italic_markers(self):
        assert strip_markdown("This is _italic_ text") == "This is italic text"

    def test_removes_code_backticks(self):
        assert strip_markdown("Use `print()` here") == "Use print() here"

    def test_removes_code_blocks(self):
        # strip_markdown regex uses [^`]* which matches within backtick pairs
        # but only removes the backticks themselves for inline code;
        # triple-backtick blocks without newlines are treated as inline
        text = "before```\ncode block\n```after"
        result = strip_markdown(text)

        assert "before" in result
        assert "```" not in result

    def test_preserves_content_between_markers(self):
        text = "*bold* and _italic_ and `code`"
        result = strip_markdown(text)

        assert result == "bold and italic and code"

    def test_plain_text_unchanged(self):
        text = "No formatting here"
        assert strip_markdown(text) == text

    def test_empty_string(self):
        assert strip_markdown("") == ""

    def test_multiple_bold_markers(self):
        text = "*one* and *two* and *three*"
        result = strip_markdown(text)

        assert result == "one and two and three"

    def test_nested_content_preserved(self):
        text = "*some important text*"
        result = strip_markdown(text)

        assert result == "some important text"

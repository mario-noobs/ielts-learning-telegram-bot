import logging
import re

logger = logging.getLogger(__name__)

# Max Telegram message length
TG_MAX_LENGTH = 4096
TG_SAFE_LENGTH = 3800


async def safe_send(target, text: str, **kwargs):
    """Send a message with Markdown, falling back to plain text on parse errors.

    Args:
        target: update.message or bot (anything with reply_text/send_message)
        text: The message text
        **kwargs: Extra args like chat_id (for bot.send_message)
    """
    chat_id = kwargs.pop("chat_id", None)

    for msg_chunk in split_message(text):
        try:
            if chat_id:
                await target.send_message(
                    chat_id=chat_id, text=msg_chunk,
                    parse_mode="Markdown", **kwargs
                )
            else:
                await target.reply_text(
                    msg_chunk, parse_mode="Markdown", **kwargs
                )
        except Exception as e:
            error_str = str(e)
            if "parse entities" in error_str.lower() or "can't find end" in error_str.lower():
                logger.warning(f"Markdown parse failed, sending as plain text: {error_str[:100]}")
                clean = strip_markdown(msg_chunk)
                try:
                    if chat_id:
                        await target.send_message(
                            chat_id=chat_id, text=clean, **kwargs
                        )
                    else:
                        await target.reply_text(clean, **kwargs)
                except Exception as e2:
                    logger.error(f"Failed to send even plain text: {e2}")
            else:
                raise


def split_message(text: str, limit: int = TG_SAFE_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit."""
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        # Try to split at a newline
        split_pos = text.rfind("\n", 0, limit)
        if split_pos == -1:
            # No newline found, split at space
            split_pos = text.rfind(" ", 0, limit)
        if split_pos == -1:
            # No space found, hard split
            split_pos = limit

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")

    return chunks


def rate_limit_message(e) -> str:
    """Build a user-friendly rate limit error message."""
    from services.ai_service import RateLimitError
    if isinstance(e, RateLimitError):
        return (
            f"\u26a0\ufe0f API rate limit reached!\n\n"
            f"Limit hit: {e.limit_type}\n"
            f"Wait: ~{e.retry_after}s before trying again\n\n"
            f"Don't spam commands - the free tier has limits:\n"
            f"- 15 requests/min\n"
            f"- 1,500 requests/day\n"
            f"- 1M tokens/min"
        )
    return "\u274c AI service error. Try again later."


def strip_markdown(text: str) -> str:
    """Remove Markdown formatting characters for plain text fallback."""
    # Remove bold/italic markers but keep the content
    text = re.sub(r'\*([^*]*)\*', r'\1', text)
    text = re.sub(r'_([^_]*)_', r'\1', text)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'```[^`]*```', '', text)
    return text

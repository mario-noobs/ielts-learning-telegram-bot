import os
import tempfile
import logging
from gtts import gTTS

logger = logging.getLogger(__name__)

# Cache directory for audio files
AUDIO_CACHE_DIR = os.path.join(tempfile.gettempdir(), "ielts_bot_audio")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)


def generate_audio(word: str) -> str | None:
    """Generate pronunciation audio for a word using gTTS.

    Returns the file path to the generated MP3, or None on failure.
    """
    safe_name = "".join(c if c.isalnum() else "_" for c in word.lower())
    filepath = os.path.join(AUDIO_CACHE_DIR, f"{safe_name}.mp3")

    # Return cached file if exists
    if os.path.exists(filepath):
        return filepath

    try:
        tts = gTTS(text=word, lang="en", slow=True)
        tts.save(filepath)
        logger.info(f"Generated audio for: {word}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to generate audio for '{word}': {e}")
        return None


def generate_sentence_audio(sentence: str) -> str | None:
    """Generate audio for a full sentence (normal speed)."""
    safe_name = "".join(c if c.isalnum() else "_" for c in sentence[:50].lower())
    filepath = os.path.join(AUDIO_CACHE_DIR, f"sent_{safe_name}.mp3")

    if os.path.exists(filepath):
        return filepath

    try:
        tts = gTTS(text=sentence, lang="en", slow=False)
        tts.save(filepath)
        return filepath
    except Exception as e:
        logger.error(f"Failed to generate sentence audio: {e}")
        return None


def cleanup_cache():
    """Remove all cached audio files."""
    for f in os.listdir(AUDIO_CACHE_DIR):
        os.remove(os.path.join(AUDIO_CACHE_DIR, f))
    logger.info("Audio cache cleaned")

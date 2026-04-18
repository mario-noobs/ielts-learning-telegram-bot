import hashlib
import logging
import os
import tempfile

from gtts import gTTS

logger = logging.getLogger(__name__)

# Cache directory for audio files
AUDIO_CACHE_DIR = os.path.join(tempfile.gettempdir(), "ielts_bot_audio")
os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)


def _passage_filepath(text: str) -> str:
    digest = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:20]
    return os.path.join(AUDIO_CACHE_DIR, f"passage_{digest}.mp3")


def generate_passage_audio(text: str) -> str | None:
    """Generate audio for a multi-sentence passage. Cached by content hash."""
    text = (text or "").strip()
    if not text:
        return None
    filepath = _passage_filepath(text)
    if os.path.exists(filepath):
        return filepath
    try:
        gTTS(text=text, lang="en", slow=False).save(filepath)
        return filepath
    except Exception as e:
        logger.error(f"Failed to generate passage audio: {e}")
        return None


def passage_audio_path(text: str) -> str:
    """Return the deterministic path for a passage (no generation)."""
    return _passage_filepath(text)


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

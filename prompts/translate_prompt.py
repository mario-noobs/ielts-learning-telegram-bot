TRANSLATE_VI_TO_EN = """Translate this Vietnamese text to English for an IELTS student (target Band {band}+).

"{text}"

Reply in this short format (plain text, no markdown):

Translation: <natural English translation>
IELTS version: <more academic/formal version>
Key words: <3-5 important words with Vietnamese meaning>"""


TRANSLATE_EN_TO_VI = """Translate this English text to Vietnamese for an IELTS student (target Band {band}+).

"{text}"

Reply in this short format (plain text, no markdown):

Translation: <Vietnamese translation>
Key words: <3-5 important English words with IPA and Vietnamese meaning>
Note: <1 grammar or usage note if relevant>"""


DETECT_LANGUAGE = """Detect the language of this text and return ONLY "en" or "vi":
"{text}"
Return ONLY the language code, nothing else."""

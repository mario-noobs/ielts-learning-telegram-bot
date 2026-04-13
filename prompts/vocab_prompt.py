GENERATE_VOCABULARY = """Generate {count} IELTS words for Band {band}+ on topic "{topic}".
{exclude_clause}

STRICT RULES:
- ipa: standard IPA transcription, e.g. /juːˈbɪkwɪtəs/
- syllable_stress: syllables separated by " · ", stressed syllable in CAPS, e.g. "u · BIQ · ui · tous"
- definition_en: MAX 15 words, short and simple
- definition_vi: REQUIRED, Vietnamese with diacritics (ă, â, ê, ô, ơ, ư, đ, etc.)
- word_family: 3-5 related forms (noun, verb, adj, adv)
- collocations: 2-3 common IELTS collocations with usage label (formal/neutral/academic)
- example_en: 1 sentence appropriate for Band {band} (max 15 words)
- example_vi: REQUIRED, Vietnamese translation of the example
- ielts_tip: 1 short sentence about using this word in IELTS
- DO NOT skip definition_vi or example_vi. Every field is MANDATORY.

Return ONLY this JSON format, no other text:
[
  {{
    "word": "ubiquitous",
    "ipa": "/juːˈbɪkwɪtəs/",
    "syllable_stress": "u · BIQ · ui · tous",
    "part_of_speech": "adj",
    "definition_en": "found everywhere, present in all places",
    "definition_vi": "có mặt ở khắp nơi",
    "word_family": ["ubiquity", "ubiquitously"],
    "collocations": [
      {{"phrase": "ubiquitous presence", "label": "formal"}},
      {{"phrase": "become ubiquitous", "label": "neutral"}}
    ],
    "example_en": "Smartphones are ubiquitous in modern life.",
    "example_vi": "Điện thoại thông minh có mặt khắp nơi trong cuộc sống hiện đại.",
    "ielts_tip": "Use in essays about technology or globalization to show advanced vocabulary."
  }}
]"""


EXPLAIN_WORD = """Explain "{word}" for a Vietnamese IELTS student (Band {band}+).

Keep it short. Use this exact format, plain text only:

{word} /<IPA>/ (<part of speech>)

EN: <max 10 words definition>
VI: <Vietnamese with diacritics>

Synonyms: <2-3 words>
Antonyms: <1-2 words>

Examples:
1. <short sentence>
   -> <Vietnamese translation>
2. <short sentence>
   -> <Vietnamese translation>

Collocations: <3-4 collocations>

IELTS tip: <1 short sentence>"""

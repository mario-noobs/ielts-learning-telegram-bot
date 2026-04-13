ENRICH_WORD = """You are an IELTS vocabulary expert helping Vietnamese learners.

Enrich the English word "{word}" for an IELTS Band {band} student.

STRICT RULES:
- ipa: standard IPA transcription, e.g. /ɪˈkɒnəmi/
- syllable_stress: syllables separated by " · ", stressed syllable in CAPS, e.g. "e · CON · o · my"
- definition_en: MAX 15 words
- definition_vi: Vietnamese with diacritics (ă, â, ê, ô, ơ, ư, đ)
- word_family: 3-5 related forms (noun, verb, adj, adv)
- collocations: 2-3 common IELTS collocations with usage label (formal/neutral/academic)
- example: 1 sentence appropriate for Band {band}, with Vietnamese translation
- ielts_tip: 1 short sentence about using this word in IELTS

Return ONLY this JSON, no other text:
{{
  "word": "{word}",
  "ipa": "/<IPA>/",
  "syllable_stress": "<syllables with stress>",
  "part_of_speech": "<pos>",
  "definition_en": "<short definition>",
  "definition_vi": "<Vietnamese definition>",
  "word_family": ["<form1>", "<form2>", "<form3>"],
  "collocations": [
    {{"phrase": "<collocation>", "label": "<formal|neutral|academic>"}},
    {{"phrase": "<collocation>", "label": "<formal|neutral|academic>"}}
  ],
  "example_en": "<example sentence for Band {band}>",
  "example_vi": "<Vietnamese translation>",
  "ielts_tip": "<tip>"
}}"""


ENRICH_WORD_EXAMPLE = """Generate ONE example sentence using the word "{word}" ({part_of_speech}: {definition_en}) appropriate for IELTS Band {band}.

Band 5-6: simple structure, common vocabulary, straightforward meaning.
Band 7+: complex structure, nuanced vocabulary, academic tone.
Band 8+: sophisticated, idiomatic, publication-quality.

Return ONLY this JSON:
{{
  "en": "<example sentence>",
  "vi": "<Vietnamese translation with diacritics>"
}}"""

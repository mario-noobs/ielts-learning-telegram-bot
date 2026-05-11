"""IELTS Listening prompts (Tier 1: AI-generated practice).

Mock-test ("thi thử") content is sourced from the S3 corpus and never
flows through these templates — that tier reads real Cambridge / British
Council material curated over time. These prompts only feed the
practice / warm-up tier the user can replay on demand.
"""

# Band-tier guidance shared by all three exercise types. The previous
# rule ("Use vocabulary appropriate to Band {band}") was too vague —
# Gemini defaulted to safe everyday topics for every band, leaving 7.5+
# users feeling the content was too easy. Inject this block into every
# prompt so the model anchors on a concrete tier.
_BAND_TIER_GUIDANCE = """
Band-tier guidance (apply strictly to the band given above):
- Band 4.5-5.5: everyday topics (shopping, housing, travel directions).
  Top-2000 English wordlist. Short sentences (max 12 words). Concrete
  nouns. Minimal idiom.
- Band 6.0-7.0: semi-academic topics (work, study, environment).
  Mid-frequency vocabulary. Mixed sentence structures. Some idiomatic
  verbs ("set up", "carry out"). Light cohesion devices.
- Band 7.5-8.5: academic topics (research, policy, technology, social
  science). Lower-frequency vocabulary and field-specific terms
  ("methodology", "demographic shift"). Complex syntax with
  subordination. Idiomatic phrases. In comprehension MCQ, the
  distractors must paraphrase the passage so surface-level matching
  fails.
- Band 9.0: scholarly register, abstract argumentation, hedging, and
  cohesion devices. Density comparable to Cambridge IELTS Part 4
  lectures.
""".strip()


DICTATION_PROMPT = (
    """You are an IELTS Listening item writer. Generate ONE short dictation passage at Band {band} on the topic "{topic}".

Rules:
- 3-5 sentences total, 40-70 words.
- Sound natural when read aloud (avoid lists, parentheses, dashes, quotation marks).
- No numbers beyond simple cardinals, no URLs, no brand names.

"""
    + _BAND_TIER_GUIDANCE
    + """

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:

{{
  "title": "<3-6 word title in English>",
  "transcript": "<the passage exactly as it should be heard>"
}}
"""
)


GAP_FILL_PROMPT = (
    """You are an IELTS Listening item writer. Generate ONE gap-fill passage at Band {band} on the topic "{topic}".

Rules:
- 60-110 words, 2-4 paragraphs.
- Contain exactly 5 to 8 blanks. Each blank replaces a single meaningful word (noun, verb, adjective, or adverb). Never blank out articles, prepositions, or conjunctions.
- Mark each blank in the display text with five underscores: "_____".
- Each answer must be a single word (no multi-word phrases) of 3-12 letters.

CRITICAL audio contract:
- The `transcript` field MUST be the natural-speech passage with EVERY word spelled out exactly as it should sound. The audio reader speaks this verbatim — any placeholder will be read aloud as a missing word and break the exercise.
- NEVER insert underscores, the literal word "blank", "[blank]", "<answer>", or any other placeholder into `transcript`. The answer word itself must appear in the corresponding position of `transcript`.
- The `display_text` field is the ONLY place where blanks are marked (with exactly five underscores `_____`).
- Worked example: if `display_text` reads "She was _____ about the results" with `blanks[0].answer = "anxious"`, then `transcript` MUST read "She was anxious about the results" — never "She was _____ about ..." and never "She was blank about ...".

"""
    + _BAND_TIER_GUIDANCE
    + """

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:

{{
  "title": "<3-6 word title in English>",
  "transcript": "<full passage with all words intact, audio-ready>",
  "display_text": "<same passage but every blank replaced with _____>",
  "blanks": [
    {{"index": 0, "answer": "<word that fills the first blank>"}},
    {{"index": 1, "answer": "<word that fills the second blank>"}}
  ]
}}
"""
)


COMPREHENSION_PROMPT = (
    """You are an IELTS Listening item writer. Generate ONE comprehension passage at Band {band} on the topic "{topic}", plus 4 multiple-choice questions.

Rules:
- Passage: 90-140 words, 2-3 paragraphs, natural spoken English.
- Generate exactly 4 questions. Each has 4 options labelled A/B/C/D but expose them as a plain array.
- One correct answer per question. Distractors must be plausible but clearly wrong from the passage.
- Each question has a one-sentence Vietnamese explanation.

"""
    + _BAND_TIER_GUIDANCE
    + """

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:

{{
  "title": "<3-6 word title in English>",
  "transcript": "<passage text>",
  "questions": [
    {{
      "question": "<question in English>",
      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "correct_index": 0,
      "explanation_vi": "<one-sentence Vietnamese explanation>"
    }}
  ]
}}
"""
)

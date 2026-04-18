DICTATION_PROMPT = """You are an IELTS Listening item writer. Generate ONE short dictation passage at Band {band} on the topic "{topic}".

Rules:
- 3-5 sentences total, 40-70 words.
- Use vocabulary and sentence structures appropriate to Band {band} (simpler at 5.0, more nuanced at 7.5+).
- Sound natural when read aloud (avoid lists, parentheses, dashes, quotation marks).
- No numbers beyond simple cardinals, no URLs, no brand names.

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:

{{
  "title": "<3-6 word title in English>",
  "transcript": "<the passage exactly as it should be heard>"
}}
"""


GAP_FILL_PROMPT = """You are an IELTS Listening item writer. Generate ONE gap-fill passage at Band {band} on the topic "{topic}".

Rules:
- 60-110 words, 2-4 paragraphs.
- Contain exactly 5 to 8 blanks. Each blank replaces a single meaningful word (noun, verb, adjective, or adverb). Never blank out articles, prepositions, or conjunctions.
- Mark each blank in the display text with five underscores: "_____".
- The answer for each blank must appear verbatim in the corresponding position of the transcript.
- Each answer must be a single word (no multi-word phrases) of 3-12 letters.

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:

{{
  "title": "<3-6 word title in English>",
  "transcript": "<full passage with all words intact>",
  "display_text": "<same passage but every blank replaced with _____>",
  "blanks": [
    {{"index": 0, "answer": "<word that fills the first blank>"}},
    {{"index": 1, "answer": "<word that fills the second blank>"}}
  ]
}}
"""


COMPREHENSION_PROMPT = """You are an IELTS Listening item writer. Generate ONE comprehension passage at Band {band} on the topic "{topic}", plus 4 multiple-choice questions.

Rules:
- Passage: 90-140 words, 2-3 paragraphs, natural spoken English.
- Generate exactly 4 questions. Each has 4 options labelled A/B/C/D but expose them as a plain array.
- One correct answer per question. Distractors must be plausible but clearly wrong from the passage.
- Each question has a one-sentence Vietnamese explanation.

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

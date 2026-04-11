GENERATE_MULTIPLE_CHOICE = """Word: "{word}" = "{definition}"

Generate a multiple choice question. Return ONLY valid JSON:
{{
  "question": "What does '{word}' mean?",
  "options": ["correct answer", "wrong 1", "wrong 2", "wrong 3"],
  "correct_index": 0,
  "explanation": "short explanation"
}}
Correct answer at index 0. Keep explanation to 1 sentence."""


GENERATE_FILL_BLANK = """Word: "{word}" = "{definition}"

Generate a fill-in-the-blank sentence. Return ONLY valid JSON:
{{
  "question": "The government _____ new policies to address the issue.",
  "answer": "{word}",
  "hint": "First letter: {first_letter}",
  "explanation": "short explanation"
}}
Keep explanation to 1 sentence."""


GENERATE_SYNONYM_ANTONYM = """Word: "{word}" = "{definition}"

Generate a synonym/antonym question. Return ONLY valid JSON:
{{
  "question": "Which is a SYNONYM of '{word}'?",
  "options": ["correct", "wrong 1", "wrong 2", "wrong 3"],
  "correct_index": 0,
  "is_synonym": true,
  "explanation": "short explanation"
}}
Correct answer at index 0. Keep explanation to 1 sentence."""


GENERATE_PARAPHRASE = """Word: "{word}" = "{definition}"

Generate a paraphrase challenge. Return ONLY valid JSON:
{{
  "question": "Rewrite WITHOUT using '{word}':\\n'<sentence using the word>'",
  "sample_answer": "<rewritten sentence>",
  "key_points": ["same meaning", "no target word"],
  "explanation": "short explanation"
}}"""


GENERATE_CHALLENGE = """Generate exactly {count} IELTS quiz questions at Band {band}+ on topic "{topic}".

Mix: 3 multiple_choice + 2 fill_blank.

STRICT: every question MUST have all fields. Keep questions SHORT (max 15 words).

Return ONLY this exact JSON format:
[
  {{
    "type": "multiple_choice",
    "word": "pedagogy",
    "question": "What does 'pedagogy' mean?",
    "options": ["teaching methods", "school building", "student group", "exam type"],
    "correct_index": 0,
    "explanation": "Pedagogy refers to the method of teaching."
  }},
  {{
    "type": "fill_blank",
    "word": "augment",
    "question": "Technology can _____ classroom learning.",
    "answer": "augment",
    "hint": "First letter: A",
    "explanation": "Augment means to increase or enhance."
  }}
]

Rules:
- multiple_choice: correct answer at index 0, exactly 4 short options
- fill_blank: use _____ for the blank, answer is the target word
- ALL fields required. DO NOT leave any field empty."""


EVALUATE_PARAPHRASE = """Original: "{original}"
Word to avoid: "{word}"
Student wrote: "{student_answer}"
Sample answer: "{sample_answer}"

Return ONLY valid JSON:
{{
  "avoided_word": true,
  "meaning_score": 4,
  "grammar_correct": true,
  "grammar_notes": "",
  "academic_level": true,
  "overall_score": 4,
  "feedback": "1-2 sentence feedback",
  "improved_version": "improved version if needed"
}}"""

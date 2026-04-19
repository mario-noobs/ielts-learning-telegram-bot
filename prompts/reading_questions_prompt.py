"""Prompt for Reading Lab question generation (US-M9.3, issue #137).

Produces exactly 13 IELTS-authentic questions per passage, grounded in
span offsets to prevent hallucination. Distribution mirrors Cambridge
Academic Reading (one passage of a 3-passage exam):

    4 × gap-fill         (short single-word or short-phrase answers)
    4 × T/F/NG           (statement vs. passage)
    3 × matching-headings (heading ↔ paragraph number)
    2 × mcq              (detail / inference)

The prompt is kept as a module constant so the scoring pipeline can
version it independently of the service code.
"""

GENERATE_READING_QUESTIONS = """\
You are an IELTS Academic Reading question author. Given a passage, \
produce exactly 13 exam-authentic questions in the distribution below. \
Return a single JSON object with key "questions". No markdown, no commentary.

Distribution (MUST match exactly):
  • Questions q1-q4:   gap-fill       (single word / short phrase)
  • Questions q5-q8:   tfng           (TRUE / FALSE / NOT_GIVEN)
  • Questions q9-q11:  matching-headings (pick paragraph number)
  • Questions q12-q13: mcq            (4 options)

GROUNDING RULE (critical):
Every question must be justified by a specific span of the passage. \
Report the start and end character offsets of that span (0-indexed, \
end-exclusive) in `passage_span`. If you cannot ground a question, \
choose a different one — never fabricate.

For matching-headings, the paragraphs are 1-indexed in reading order. \
The `options` list is the candidate paragraph numbers + a short label \
(e.g. "Paragraph 2"), and the `answer` is the option id matching the \
correct paragraph.

For mcq and matching-headings, `options` must contain 4 items with \
ids "o1".."o4" and the `answer` is one of those ids.

For gap-fill, `answer` is the exact word or short phrase from the \
passage (case-insensitive match will be used at grading time). Keep \
gap-fill answers to 1-3 words.

For tfng, `answer` is one of "TRUE", "FALSE", "NOT_GIVEN".

Every question carries a one-sentence `explanation` that cites the \
span and explains why the answer is correct. Write the explanation \
in English for now; a Vietnamese sibling will ship with US-M7.4.

Question schema (one item per question):
{{
  "id": "q1",
  "type": "gap-fill" | "tfng" | "matching-headings" | "mcq",
  "stem": "The sentence or question as shown to the learner.",
  "options": [ {{"id": "o1", "text": "..."}}, ... ],
  "answer": "string (exact text for gap-fill/tfng, option id otherwise)",
  "passage_span": {{"start": 0, "end": 0}},
  "explanation": "One-sentence justification referencing the span."
}}

Respond ONLY with valid JSON.

Passage title: {title}
Passage band (target difficulty): {band}

Passage body (character offsets are 0-indexed from the first character \
of the block between the triple-quotes, EXCLUDING the opening newline):
\"\"\"
{body}
\"\"\"
"""

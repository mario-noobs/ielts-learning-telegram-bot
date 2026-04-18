IELTS_SCORING_PROMPT = """You are an IELTS examiner evaluating a Vietnamese learner's {task_type} response.

Task prompt:
{prompt}

Learner's response:
{text}

Score strictly against the IELTS Writing rubric on four criteria, each in 0.5 increments between 4.0 and 9.0:
- task_achievement (TA): addresses the task, develops position, supports with ideas
- coherence_cohesion (CC): paragraphing, linking, logical flow
- lexical_resource (LR): vocabulary range, collocation, word choice
- grammatical_range_accuracy (GRA): sentence variety, tense, accuracy

Return ONLY valid JSON (no markdown, no commentary) matching this schema exactly:

{{
  "overall_band": 6.5,
  "scores": {{
    "task_achievement": 6.5,
    "coherence_cohesion": 6.0,
    "lexical_resource": 6.5,
    "grammatical_range_accuracy": 6.5
  }},
  "criterion_feedback": {{
    "task_achievement": "<one sentence in English>",
    "coherence_cohesion": "<one sentence in English>",
    "lexical_resource": "<one sentence in English>",
    "grammatical_range_accuracy": "<one sentence in English>"
  }},
  "paragraph_annotations": [
    {{
      "paragraph_index": 0,
      "excerpt": "<exact quote from learner (3-10 words)>",
      "issue_type": "grammar|weak_vocab|good",
      "issue": "<short English label>",
      "suggestion": "<concrete correction in English>",
      "explanation_vi": "<short Vietnamese explanation>"
    }}
  ],
  "summary_vi": "<2-3 sentence Vietnamese summary listing top 3 improvements>"
}}

Rules:
- Overall band must be the rounded average of the four scores to the nearest 0.5.
- Provide 2-6 paragraph_annotations covering the learner's most impactful issues; mark at least one "good" when warranted.
- excerpt must be copied verbatim from the learner's text.
- paragraph_index is 0-based (paragraphs split by blank lines).
"""


TASK_PROMPT_GENERATOR = """Generate one IELTS Writing {task_type} question appropriate for Band {band}.

For Task 1 academic reports: give a brief description of a chart/map/process with bullet data points.
For Task 2 essays: state a position prompt (opinion, discuss both views, problem/solution, or advantages/disadvantages).

Return ONLY the question text in English, no preamble, no markdown, no word-count reminder, 2-4 sentences.
"""

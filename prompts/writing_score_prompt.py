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


TASK1_PROMPT_GENERATOR = """You are an IELTS item writer. Generate ONE IELTS Academic Writing TASK 1 question at Band {band}, together with the underlying visualization data so the learner can actually see a chart.

Pick exactly one chart_type: "line", "bar", "pie", or "table". Invent plausible realistic numbers.

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema:

{{
  "prompt": "The <chart_type> below shows ... . Summarise the information by selecting and reporting the main features, and make comparisons where relevant.",
  "visualization": {{
    "chart_type": "line|bar|pie|table",
    "title": "<short title with units>",
    "x_axis_label": "<x axis label, empty for pie/table>",
    "y_axis_label": "<y axis label with units, empty for pie/table>",
    "x_labels": ["<category or year 1>", "<category or year 2>", "..."],
    "series": [
      {{"name": "<series name>", "values": [<number>, <number>, ...]}}
    ],
    "slices": [
      {{"label": "<slice label>", "value": <number>}}
    ],
    "table_headers": ["<col1>", "<col2>"],
    "table_rows": [["<r1c1>", "<r1c2>"]],
    "y_min": 0,
    "y_max": 100
  }}
}}

Rules:
- "line" or "bar": populate x_labels, series (1-4 series, each with values.length === x_labels.length); leave slices / table_* empty.
- "pie": populate 3-6 slices whose values sum to 100 (percentages); leave x_labels/series/table_* empty.
- "table": populate table_headers (2-5 cols) and table_rows (3-6 rows, same column count); leave x_labels/series/slices empty.
- Keep the prompt text single-paragraph, 2-3 sentences, ending with the standard "Summarise..." line.
- Never output values the chart type does not use.
"""


TASK2_PROMPT_GENERATOR = """You are an IELTS item writer. Generate ONE IELTS Writing TASK 2 essay question at Band {band}.

Pick exactly one of these question types at random and phrase the prompt accordingly:
- Opinion ("To what extent do you agree or disagree?")
- Discuss both views ("Discuss both views and give your own opinion.")
- Problem + solution ("What are the causes of this problem and what measures could solve it?")
- Advantages + disadvantages ("Do the advantages outweigh the disadvantages?")

Topic must be a broad IELTS theme (education, technology, environment, health, work, urbanisation, globalisation, media, crime, family). Avoid Task 1 framing — do NOT mention charts, tables, graphs, processes, or maps.

Format:
- Sentence 1-2: the situation or claim.
- Final sentence: the exact question line from the type you chose.

Return ONLY the task text in English. No preamble, no markdown, no word-count reminder, no answer.
"""

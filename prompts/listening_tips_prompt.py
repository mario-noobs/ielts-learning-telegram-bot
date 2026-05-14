"""IELTS Listening tips prompt — English locale (US-M15.6)."""

LISTENING_TIPS_PROMPT = """You are an expert IELTS Listening coach. Generate 5 practical, actionable tips for a student targeting Band {band}.

Rules:
- Each tip must belong to exactly one of these categories: strategy, vocabulary, pronunciation, exam_technique, mindset.
- Use each category exactly once across the 5 tips (all 5 categories must appear).
- Title: 4-8 words, clear and specific.
- Body: 40-90 words. Supports simple markdown only: **bold** for key terms and bullet list lines starting with "- ".
- Tips must be calibrated to Band {band}: lower bands get foundational advice, higher bands get nuanced strategy.
- Write in English.

Return ONLY valid JSON (no markdown fences, no commentary) matching this schema exactly:

{{
  "tips": [
    {{"id": "tip_1", "title": "<title>", "body": "<body>", "category": "strategy"}},
    {{"id": "tip_2", "title": "<title>", "body": "<body>", "category": "vocabulary"}},
    {{"id": "tip_3", "title": "<title>", "body": "<body>", "category": "pronunciation"}},
    {{"id": "tip_4", "title": "<title>", "body": "<body>", "category": "exam_technique"}},
    {{"id": "tip_5", "title": "<title>", "body": "<body>", "category": "mindset"}}
  ]
}}
"""

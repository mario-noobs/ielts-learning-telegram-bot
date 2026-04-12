import logging
from services import ai_service, firebase_service

import config

logger = logging.getLogger(__name__)


async def create_daily_challenge(group_id: int) -> tuple[list, str]:
    """Generate a daily challenge for the group."""
    group = firebase_service.get_group_settings(group_id)
    band = group.get("default_band", 7.0) if group else 7.0
    topics = group.get("topics", ["education"]) if group else ["education"]

    import random
    topic = random.choice(topics)

    questions = await ai_service.generate_challenge(
        count=config.CHALLENGE_QUESTION_COUNT,
        band=band,
        topic=topic
    )

    date_str = config.local_date_str()
    firebase_service.save_challenge(group_id, date_str, questions)

    return questions, date_str


def format_challenge(questions: list, date_str: str) -> str:
    """Format challenge questions for group display."""
    lines = [
        f"\u26a1 *Daily IELTS Challenge* \u2014 {date_str}\n",
        f"Answer all {len(questions)} questions! DM me your answers.\n"
    ]

    for i, q in enumerate(questions, 1):
        q_type = q.get("type", "multiple_choice")
        question_text = q.get("question", "")

        if q_type in ("multiple_choice", "synonym_antonym"):
            options = q.get("options", [])
            lines.append(f"*Q{i}.* {question_text}")
            for j, opt in enumerate(options):
                label = chr(65 + j)
                lines.append(f"  {label}. {opt}")
            lines.append("")
        elif q_type == "fill_blank":
            hint = q.get("hint", "")
            lines.append(f"*Q{i}.* {question_text}")
            if hint:
                lines.append(f"  \U0001f4a1 _{hint}_")
            lines.append("")
        elif q_type == "paraphrase":
            lines.append(f"*Q{i}.* {question_text}")
            lines.append("")

    lines.append(
        f"\u23f0 You have {config.CHALLENGE_DEADLINE_MINUTES} minutes! "
        f"DM me with /answer <Q number> <your answer>"
    )

    return "\n".join(lines)


def format_challenge_results(group_id: int, date_str: str) -> str:
    """Format challenge results with rankings."""
    challenge = firebase_service.get_challenge(group_id, date_str)
    if not challenge:
        return "No challenge found for today."

    participants = challenge.get("participants", {})
    total_q = len(challenge.get("questions", []))

    if not participants:
        return "\U0001f614 No one participated in today's challenge."

    # Sort by score descending
    sorted_p = sorted(participants.items(), key=lambda x: x[1], reverse=True)

    lines = [
        f"\U0001f3c6 *Daily Challenge Results* \u2014 {date_str}\n"
    ]

    medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
    for i, (user_id, score) in enumerate(sorted_p):
        user = firebase_service.get_user(int(user_id))
        name = user.get("name", "Unknown") if user else "Unknown"
        medal = medals[i] if i < 3 else f"  {i + 1}."
        lines.append(f"{medal} *{name}* \u2014 {score}/{total_q}")

    # Update winner's challenge_wins (only once — guard with close_challenge)
    if sorted_p:
        challenge_data = firebase_service.get_challenge(group_id, date_str)
        if challenge_data and challenge_data.get("status") != "closed":
            from firebase_admin import firestore as fs
            winner_id = int(sorted_p[0][0])
            firebase_service.update_user(winner_id, {
                "challenge_wins": fs.Increment(1)
            })
            firebase_service.close_challenge(group_id, date_str)

    return "\n".join(lines)

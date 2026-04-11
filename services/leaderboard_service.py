from services import firebase_service


def format_leaderboard(group_id: int) -> str:
    """Generate a formatted leaderboard for the group."""
    users = firebase_service.get_leaderboard(group_id)

    if not users:
        return "No users registered yet. Use /start to join!"

    # Sort by different criteria
    by_words = sorted(users, key=lambda u: u.get("total_words", 0), reverse=True)
    by_accuracy = sorted(users, key=lambda u: u.get("accuracy", 0), reverse=True)
    by_streak = sorted(users, key=lambda u: u.get("streak", 0), reverse=True)
    by_challenge = sorted(users, key=lambda u: u.get("challenge_wins", 0), reverse=True)

    def _format_ranking(sorted_users, field, label, emoji, formatter=str):
        lines = [f"{emoji} *{label}*"]
        medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
        for i, u in enumerate(sorted_users[:5]):
            name = u.get("name", "Unknown")
            username = u.get("username", "")
            display = f"@{username}" if username else name
            value = u.get(field, 0)
            medal = medals[i] if i < 3 else f"  {i + 1}."
            lines.append(f"{medal} {display} \u2014 {formatter(value)}")
        return "\n".join(lines)

    sections = [
        "\U0001f3c6 *IELTS Study Leaderboard*\n",
        _format_ranking(by_words, "total_words", "Words Learned",
                       "\U0001f4d6"),
        "",
        _format_ranking(by_accuracy, "accuracy", "Quiz Accuracy",
                       "\U0001f3af", lambda v: f"{v}%"),
        "",
        _format_ranking(by_streak, "streak", "Current Streak",
                       "\U0001f525", lambda v: f"{v} days"),
        "",
        _format_ranking(by_challenge, "challenge_wins", "Challenge Wins",
                       "\u26a1", lambda v: f"{v} wins"),
    ]

    return "\n".join(sections)

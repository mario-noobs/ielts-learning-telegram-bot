import logging
import random

from services import ai_service, firebase_service
from services.srs_service import calculate_next_review

logger = logging.getLogger(__name__)


async def generate_quiz_question(telegram_id: int,
                                  quiz_type: str = None) -> dict | None:
    """Generate a quiz question from the user's vocabulary."""
    words = firebase_service.get_user_vocabulary(telegram_id, limit=100)
    if not words:
        return None

    word_data = random.choice(words)

    if not quiz_type:
        quiz_type = random.choice(["multiple_choice", "fill_blank"])

    question = await ai_service.generate_quiz(
        word=word_data["word"],
        definition=word_data.get("definition", ""),
        quiz_type=quiz_type
    )
    question["word_id"] = word_data["id"]

    # For fill_blank: add word options as buttons (correct + 3 distractors)
    if quiz_type == "fill_blank":
        correct_word = question.get("answer", word_data["word"])
        other_words = [w["word"] for w in words if w["word"] != correct_word]
        distractors = random.sample(other_words, min(3, len(other_words)))
        options = [correct_word] + distractors
        random.shuffle(options)
        question["options"] = options
        question["correct_index"] = options.index(correct_word)

    return question


async def generate_quiz_batch(telegram_id: int, count: int = 5,
                              types: list[str] = None,
                              word_ids: list[str] = None) -> list[dict] | None:
    """Generate all quiz questions in a single AI call.

    When word_ids is provided, generate questions for exactly those words
    (order preserved, capped at count). Otherwise sample randomly from the
    user's vocabulary.
    """
    words = firebase_service.get_user_vocabulary(telegram_id, limit=200)
    if not words:
        return None

    if word_ids:
        by_id = {w["id"]: w for w in words}
        selected = [by_id[wid] for wid in word_ids if wid in by_id][:count]
        if not selected:
            return None
    else:
        if len(words) < count:
            return None
        selected = random.sample(words, count)

    if not types:
        types = ["multiple_choice"] * 3 + ["fill_blank"] * 2
        random.shuffle(types)

    if len(types) < len(selected):
        types = (types * ((len(selected) // len(types)) + 1))[:len(selected)]

    # Prepare word data for batch generation
    word_inputs = [
        {
            "word": w["word"],
            "definition": w.get("definition", ""),
            "word_id": w["id"],
        }
        for w in selected
    ]

    questions = await ai_service.generate_quiz_batch(word_inputs, types)

    # Ensure word_id is set from our selected words
    for i, q in enumerate(questions):
        if i < len(selected):
            q["word_id"] = selected[i]["id"]
        q = shuffle_options(q)
        questions[i] = q

    return questions


async def generate_review_batch(words: list[dict]) -> list[dict]:
    """Generate review questions for specific due words in a single AI call."""
    types = []
    for _ in words:
        types.append(random.choice(["multiple_choice", "synonym_antonym"]))

    word_inputs = [
        {
            "word": w["word"],
            "definition": w.get("definition", ""),
            "word_id": w["id"],
        }
        for w in words
    ]

    questions = await ai_service.generate_quiz_batch(word_inputs, types)

    for i, q in enumerate(questions):
        if i < len(words):
            q["word_id"] = words[i]["id"]
        q = shuffle_options(q)
        questions[i] = q

    return questions


def shuffle_options(question: dict) -> dict:
    """Shuffle multiple choice options while tracking the correct index."""
    if question.get("type") not in ("multiple_choice", "synonym_antonym", "fill_blank"):
        return question

    options = question.get("options", [])
    correct_idx = question.get("correct_index", 0)
    if not options or correct_idx >= len(options):
        return question

    correct_answer = options[correct_idx]
    random.shuffle(options)
    question["options"] = options
    question["correct_index"] = options.index(correct_answer)
    return question


def format_question(question: dict, question_num: int = 1) -> str:
    """Format any question type. Plain text, no markdown."""
    q_type = question.get("type", "multiple_choice")
    q_text = question.get("question", "")

    if q_type in ("multiple_choice", "synonym_antonym"):
        options = question.get("options", [])
        lines = [f"Q{question_num}. {q_text}\n"]
        for i, opt in enumerate(options):
            label = chr(65 + i)
            lines.append(f"  {label}. {opt}")
        return "\n".join(lines)

    elif q_type == "fill_blank":
        options = question.get("options", [])
        text = f"Q{question_num}. Fill in the blank:\n\n{q_text}\n"
        for i, opt in enumerate(options):
            label = chr(65 + i)
            text += f"\n  {label}. {opt}"
        return text

    elif q_type == "paraphrase":
        text = f"Q{question_num}. Paraphrase:\n\n{q_text}"
        text += "\n\nType your rewrite:"
        return text

    return f"Q{question_num}. {q_text}"


async def check_answer(question: dict, user_answer: str,
                        telegram_id: int) -> tuple[bool, str]:
    """Check the user's answer and return (is_correct, feedback)."""
    q_type = question.get("type")
    is_correct = False
    feedback = ""

    if q_type in ("multiple_choice", "synonym_antonym"):
        correct_idx = question.get("correct_index", 0)
        options = question.get("options", [])
        correct_answer = options[correct_idx] if correct_idx < len(options) else "?"
        explanation = question.get("explanation", "")

        answer_upper = user_answer.strip().upper()
        if len(answer_upper) == 1 and answer_upper in "ABCD":
            user_idx = ord(answer_upper) - ord("A")
        else:
            user_idx = -1

        is_correct = user_idx == correct_idx

        if is_correct:
            feedback = f"\u2705 Correct! {explanation}"
        else:
            feedback = f"\u274c Wrong. Answer: {chr(65 + correct_idx)}. {correct_answer}\n{explanation}"

    elif q_type == "fill_blank":
        correct_idx = question.get("correct_index", 0)
        options = question.get("options", [])
        correct_word = options[correct_idx] if correct_idx < len(options) else question.get("answer", "?")
        explanation = question.get("explanation", "")

        answer_upper = user_answer.strip().upper()
        if len(answer_upper) == 1 and answer_upper in "ABCD":
            user_idx = ord(answer_upper) - ord("A")
        else:
            user_idx = -1

        is_correct = user_idx == correct_idx

        if is_correct:
            feedback = f"\u2705 Correct! {explanation}"
        else:
            feedback = f"\u274c Wrong. Answer: {chr(65 + correct_idx)}. {correct_word}\n{explanation}"

    elif q_type == "paraphrase":
        result = await ai_service.evaluate_paraphrase(
            original=question.get("question", ""),
            word=question.get("word", ""),
            student_answer=user_answer,
            sample_answer=question.get("sample_answer", "")
        )
        score = result.get("overall_score", 0)
        is_correct = score >= 3
        fb = result.get("feedback", "")
        improved = result.get("improved_version", "")

        feedback = f"Score: {score}/5 {'✅' if is_correct else '⚠️'}\n{fb}"
        if improved:
            feedback += f"\nBetter version: {improved}"

    # Update SRS
    word_id = question.get("word_id")
    if word_id:
        word_data = firebase_service.get_word_by_id(telegram_id, word_id)
        if word_data:
            srs_update = calculate_next_review(word_data, is_correct)
            firebase_service.update_word_srs(telegram_id, word_id, srs_update)

    # Save quiz history
    firebase_service.save_quiz_result(telegram_id, {
        "word_id": question.get("word_id", ""),
        "type": q_type,
        "question": question.get("question", ""),
        "correct_answer": str(question.get("correct_index", question.get("answer", ""))),
        "user_answer": user_answer,
        "is_correct": is_correct,
        "is_challenge": question.get("is_challenge", False),
    })

    return is_correct, feedback

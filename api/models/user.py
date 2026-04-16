from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    target_band: float = 7.0
    topics: list[str] = ["education", "environment", "technology"]


class UserProfile(BaseModel):
    id: str
    name: str
    email: str | None = None
    target_band: float
    topics: list[str]
    streak: int = 0
    total_words: int = 0
    total_quizzes: int = 0
    total_correct: int = 0
    challenge_wins: int = 0

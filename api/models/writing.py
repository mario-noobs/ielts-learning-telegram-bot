from datetime import datetime

from pydantic import BaseModel, Field


class WritingScores(BaseModel):
    task_achievement: float = 0.0
    coherence_cohesion: float = 0.0
    lexical_resource: float = 0.0
    grammatical_range_accuracy: float = 0.0


class CriterionFeedback(BaseModel):
    task_achievement: str = ""
    coherence_cohesion: str = ""
    lexical_resource: str = ""
    grammatical_range_accuracy: str = ""


class ParagraphAnnotation(BaseModel):
    paragraph_index: int = 0
    excerpt: str = ""
    issue_type: str = "grammar"
    issue: str = ""
    suggestion: str = ""
    explanation_vi: str = ""


class WritingFeedback(BaseModel):
    overall_band: float = 0.0
    scores: WritingScores = WritingScores()
    criterion_feedback: CriterionFeedback = CriterionFeedback()
    paragraph_annotations: list[ParagraphAnnotation] = []
    summary_vi: str = ""


class WritingSubmitRequest(BaseModel):
    text: str = Field(min_length=1)
    task_type: str = Field(default="task2", pattern=r"^(task1|task2)$")
    prompt: str = ""


class WritingSubmission(BaseModel):
    id: str
    text: str
    task_type: str
    prompt: str
    overall_band: float
    scores: WritingScores
    criterion_feedback: CriterionFeedback
    paragraph_annotations: list[ParagraphAnnotation]
    summary_vi: str
    word_count: int
    created_at: datetime | None = None
    original_id: str | None = None
    delta_band: float | None = None


class WritingHistoryItem(BaseModel):
    id: str
    task_type: str
    prompt_preview: str
    overall_band: float
    word_count: int
    created_at: datetime | None = None
    original_id: str | None = None


class WritingHistoryResponse(BaseModel):
    items: list[WritingHistoryItem]


class TaskPromptRequest(BaseModel):
    task_type: str = Field(default="task2", pattern=r"^(task1|task2)$")


class Task1Series(BaseModel):
    name: str
    values: list[float] = []


class Task1Slice(BaseModel):
    label: str
    value: float


class Task1Visualization(BaseModel):
    chart_type: str = "line"
    title: str = ""
    x_axis_label: str = ""
    y_axis_label: str = ""
    x_labels: list[str] = []
    series: list[Task1Series] = []
    slices: list[Task1Slice] = []
    table_headers: list[str] = []
    table_rows: list[list[str]] = []
    y_min: float | None = None
    y_max: float | None = None


class TaskPromptResponse(BaseModel):
    prompt: str
    visualization: Task1Visualization | None = None


class WritingReviseRequest(BaseModel):
    text: str = Field(min_length=1)

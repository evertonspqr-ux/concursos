import uuid
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    created_at: datetime

class ExamCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    organizing_body: str | None = Field(default=None, max_length=255)
    examining_board: str | None = Field(default=None, max_length=255)
    exam_date: date | None = None

class ExamRead(ExamCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class NoticeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam_id: uuid.UUID
    filename: str
    mime_type: str
    file_size_bytes: int | None
    extraction_metadata: dict
    parsed_at: datetime | None
    created_at: datetime


class ExamPaperCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    position_id: uuid.UUID | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    application_date: date | None = None
    source_url: str | None = Field(default=None, max_length=2048)


class ExamPaperRead(ExamPaperCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam_id: uuid.UUID
    created_at: datetime


class QuestionImport(BaseModel):
    statement: str = Field(min_length=3)
    options: list[dict] = Field(default_factory=list)
    correct_answer: str | None = Field(default=None, max_length=32)
    explanation: str | None = None
    subject_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    weight: float = Field(default=1, gt=0, le=100)


class QuestionImportRequest(BaseModel):
    questions: list[QuestionImport] = Field(min_length=1, max_length=500)


class AnswerKeyUpdate(BaseModel):
    answers: dict[int, str] = Field(min_length=1)


class AttemptAnswer(BaseModel):
    question_id: uuid.UUID
    selected_answer: str | None = Field(default=None, max_length=32)
    elapsed_seconds: int | None = Field(default=None, ge=0)


class PaperAttemptRequest(BaseModel):
    answers: list[AttemptAnswer] = Field(min_length=1, max_length=500)


class PaperAttemptResult(BaseModel):
    total_questions: int
    answered_questions: int
    correct_answers: int
    score: float


class QuestionClassificationResult(BaseModel):
    question_id: uuid.UUID
    subject_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    subject_name: str | None
    topic_name: str | None
    confidence: float | None
    method: str | None
    status: str
    needs_review: bool


class QuestionBatchClassifyRequest(BaseModel):
    question_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class QuestionBatchClassifyResult(BaseModel):
    results: list[QuestionClassificationResult]
    classified: int
    needs_review: int


class QuestionReviewItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    statement: str
    subject_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    classification_confidence: float | None
    classification_status: str
    classification_metadata: dict


class QuestionClassificationOverride(BaseModel):
    subject_id: uuid.UUID
    topic_id: uuid.UUID | None = None


class StudyPlanCreate(BaseModel):
    exam_id: uuid.UUID
    position_id: uuid.UUID | None = None
    title: str = Field(min_length=3, max_length=255)
    available_minutes_per_day: int = Field(gt=0, le=1440)
    starts_on: date
    ends_on: date | None = None


class StudyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam_id: uuid.UUID | None
    position_id: uuid.UUID | None
    title: str
    available_minutes_per_day: int
    starts_on: date
    ends_on: date | None
    is_active: bool
    created_at: datetime


class StudyPlanItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    subject_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    scheduled_for: datetime
    planned_minutes: int
    priority: float


class StudyScheduleItem(BaseModel):
    item: StudyPlanItemRead
    subject_name: str | None
    topic_name: str | None
    session_id: uuid.UUID | None
    session_status: str


class StudySessionOutcome(BaseModel):
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = Field(default=None, ge=0)


class CutoffScoreCreate(BaseModel):
    position_id: uuid.UUID | None = None
    category: str | None = Field(default=None, max_length=128)
    score: float = Field(gt=0, le=1000)
    source_url: str | None = Field(default=None, max_length=2048)


class CutoffScoreUpdate(BaseModel):
    score: float | None = Field(default=None, gt=0, le=1000)
    source_url: str | None = Field(default=None, max_length=2048)


class CutoffScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam_id: uuid.UUID
    position_id: uuid.UUID | None
    category: str | None
    score: float
    source_url: str | None
    created_at: datetime


class CutoffHistoricalPoint(BaseModel):
    exam_id: uuid.UUID
    exam_title: str
    exam_date: date | None
    position_id: uuid.UUID | None
    category: str | None
    score: float
    source_url: str | None


class CutoffTrend(BaseModel):
    status: str
    data_points: int
    trend_per_period: float | None
    projected_next_score: float | None


class UserScoreEstimate(BaseModel):
    status: str
    score: float | None
    coverage: float
    subjects_without_data: int


class CutoffMargin(BaseModel):
    status: str
    reference_type: str
    reference_value: float | None
    margin: float | None


class CompetitiveIndex(BaseModel):
    status: str
    method: str | None
    index: float | None
    historical_mean: float | None
    historical_stdev: float | None


class CutoffIntelligence(BaseModel):
    historical: list[CutoffHistoricalPoint]
    trend: CutoffTrend
    user_score_estimate: UserScoreEstimate
    margin: CutoffMargin
    competitive_index: CompetitiveIndex
    recommendations: list[str]

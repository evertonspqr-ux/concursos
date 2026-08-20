import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampedModel:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class QuestionType(str, enum.Enum):
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    essay = "essay"


class AttemptSource(str, enum.Enum):
    exam_paper = "exam_paper"
    simulation = "simulation"
    practice = "practice"


class StudySessionStatus(str, enum.Enum):
    planned = "planned"
    completed = "completed"
    skipped = "skipped"


class User(TimestampedModel, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/Sao_Paulo")


class Exam(TimestampedModel, Base):
    __tablename__ = "exams"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    organizing_body: Mapped[str | None] = mapped_column(String(255))
    examining_board: Mapped[str | None] = mapped_column(String(255), index=True)
    registration_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exam_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)


class Position(TimestampedModel, Base):
    __tablename__ = "positions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str | None] = mapped_column(String(64))
    vacancies: Mapped[int | None] = mapped_column(Integer)
    salary: Mapped[float | None] = mapped_column(Numeric(12, 2))
    requirements: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("exam_id", "name", name="uq_position_exam_name"),)


class Notice(TimestampedModel, Base):
    __tablename__ = "notices"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/pdf")
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subject(TimestampedModel, Base):
    __tablename__ = "subjects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)


class Topic(TimestampedModel, Base):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("subject_id", "parent_id", "normalized_name", name="uq_topic_path"),)


class ExamSubject(TimestampedModel, Base):
    __tablename__ = "exam_subjects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    expected_questions: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("exam_id", "position_id", "subject_id", name="uq_exam_subject_scope"),)


class ExamPaper(TimestampedModel, Base):
    __tablename__ = "exam_papers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    application_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    storage_key: Mapped[str | None] = mapped_column(String(1024))
    answer_key: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Question(TimestampedModel, Base):
    __tablename__ = "questions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="question_type"), nullable=False, default=QuestionType.multiple_choice)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    correct_answer: Mapped[str | None] = mapped_column(String(32))
    explanation: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[float | None] = mapped_column(Float)
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unclassified", index=True)
    classification_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    __table_args__ = (
        CheckConstraint("difficulty IS NULL OR (difficulty >= 0 AND difficulty <= 1)", name="ck_question_difficulty"),
        CheckConstraint(
            "classification_status IN ('unclassified', 'classified', 'needs_review')",
            name="ck_question_classification_status",
        ),
    )


class ExamPaperQuestion(Base):
    __tablename__ = "exam_paper_questions"
    exam_paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_papers.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    __table_args__ = (UniqueConstraint("exam_paper_id", "order", name="uq_exam_paper_question_order"),)


class Simulation(TimestampedModel, Base):
    __tablename__ = "simulations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exams.id", ondelete="SET NULL"), index=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Numeric(8, 2))


class SimulationQuestion(Base):
    __tablename__ = "simulation_questions"
    simulation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), primary_key=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("simulation_id", "order", name="uq_simulation_question_order"),)


class UserQuestionAttempt(TimestampedModel, Base):
    __tablename__ = "user_question_attempts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[AttemptSource] = mapped_column(Enum(AttemptSource, name="attempt_source"), nullable=False)
    simulation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("simulations.id", ondelete="CASCADE"), index=True)
    exam_paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exam_papers.id", ondelete="SET NULL"), index=True)
    selected_answer: Mapped[str | None] = mapped_column(String(32))
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer)


class StudyPlan(TimestampedModel, Base):
    __tablename__ = "study_plans"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exam_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("exams.id", ondelete="SET NULL"), index=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    available_minutes_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StudyPlanItem(TimestampedModel, Base):
    __tablename__ = "study_plan_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    study_plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    planned_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[float] = mapped_column(Float, nullable=False, default=0)


class StudySession(TimestampedModel, Base):
    __tablename__ = "study_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    study_plan_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("study_plan_items.id", ondelete="SET NULL"), index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[StudySessionStatus] = mapped_column(Enum(StudySessionStatus, name="study_session_status"), nullable=False, default=StudySessionStatus.planned)


class CutoffScore(TimestampedModel, Base):
    __tablename__ = "cutoff_scores"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    position_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("positions.id", ondelete="CASCADE"), index=True)
    category: Mapped[str | None] = mapped_column(String(128))
    score: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    __table_args__ = (UniqueConstraint("exam_id", "position_id", "category", name="uq_cutoff_score_scope"),)


class UserPerformance(TimestampedModel, Base):
    __tablename__ = "user_performances"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    questions_answered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accuracy: Mapped[float | None] = mapped_column(Float)
    last_calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "subject_id", "topic_id", name="uq_user_performance_scope"),)

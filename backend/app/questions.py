import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ai_provider import AnthropicClassifierProvider
from .classifier import ClassificationOutcome, SubjectCandidate, TopicCandidate, classify_question_statement
from .config import get_settings
from .database import get_session
from .dependencies import get_current_user
from .models import Question, Subject, Topic, User
from .schemas import (
    QuestionBatchClassifyRequest,
    QuestionBatchClassifyResult,
    QuestionClassificationOverride,
    QuestionClassificationResult,
    QuestionReviewItem,
)

router = APIRouter(prefix="/api/v1/questions", tags=["question classification"])
settings = get_settings()


def get_classifier_provider() -> AnthropicClassifierProvider:
    return AnthropicClassifierProvider(settings.anthropic_api_key, settings.classifier_model, settings.classifier_request_timeout_seconds)


async def load_candidates(session: AsyncSession) -> list[SubjectCandidate]:
    subjects = list(await session.scalars(select(Subject)))
    topics = list(await session.scalars(select(Topic)))
    topics_by_subject: dict[uuid.UUID, list[TopicCandidate]] = {}
    for topic in topics:
        topics_by_subject.setdefault(topic.subject_id, []).append(TopicCandidate(id=topic.id, name=topic.name))
    return [SubjectCandidate(id=subject.id, name=subject.name, topics=topics_by_subject.get(subject.id, [])) for subject in subjects]


def apply_outcome(question: Question, outcome: ClassificationOutcome) -> None:
    question.subject_id = outcome.subject_id
    question.topic_id = outcome.topic_id
    question.classification_confidence = outcome.confidence
    question.classification_status = "needs_review" if outcome.needs_review else "classified"
    question.classification_metadata = {
        "method": outcome.method,
        "rationale": outcome.rationale,
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }


def build_result(question: Question, candidates: list[SubjectCandidate]) -> QuestionClassificationResult:
    subject = next((item for item in candidates if item.id == question.subject_id), None)
    topic = next((item for item in subject.topics if item.id == question.topic_id), None) if subject else None
    return QuestionClassificationResult(
        question_id=question.id,
        subject_id=question.subject_id,
        topic_id=question.topic_id,
        subject_name=subject.name if subject else None,
        topic_name=topic.name if topic else None,
        confidence=question.classification_confidence,
        method=question.classification_metadata.get("method") if question.classification_metadata else None,
        status=question.classification_status,
        needs_review=question.classification_status == "needs_review",
    )


async def require_question(question_id: uuid.UUID, session: AsyncSession) -> Question:
    question = await session.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questão não encontrada")
    return question


@router.post("/{question_id}/classify", response_model=QuestionClassificationResult)
async def classify_question(
    question_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> QuestionClassificationResult:
    question = await require_question(question_id, session)
    candidates = await load_candidates(session)
    outcome = await classify_question_statement(question.statement, question.options, candidates, get_classifier_provider(), settings.classifier_review_threshold)
    apply_outcome(question, outcome)
    await session.commit()
    await session.refresh(question)
    return build_result(question, candidates)


@router.post("/classify:batch", response_model=QuestionBatchClassifyResult)
async def classify_questions_batch(
    payload: QuestionBatchClassifyRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> QuestionBatchClassifyResult:
    questions = list(await session.scalars(select(Question).where(Question.id.in_(payload.question_ids))))
    found_ids = {question.id for question in questions}
    missing = [str(question_id) for question_id in payload.question_ids if question_id not in found_ids]
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Questões inexistentes: {missing}")
    candidates = await load_candidates(session)
    provider = get_classifier_provider()
    for question in questions:
        outcome = await classify_question_statement(question.statement, question.options, candidates, provider, settings.classifier_review_threshold)
        apply_outcome(question, outcome)
    await session.commit()
    results = [build_result(question, candidates) for question in questions]
    needs_review = sum(1 for result in results if result.needs_review)
    return QuestionBatchClassifyResult(results=results, classified=len(results) - needs_review, needs_review=needs_review)


@router.get("/review-queue", response_model=list[QuestionReviewItem])
async def review_queue(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> list[Question]:
    return list(
        await session.scalars(
            select(Question).where(Question.classification_status == "needs_review").order_by(Question.updated_at.desc()).limit(limit)
        )
    )


@router.put("/{question_id}/classification", response_model=QuestionClassificationResult)
async def override_classification(
    question_id: uuid.UUID,
    payload: QuestionClassificationOverride,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> QuestionClassificationResult:
    question = await require_question(question_id, session)
    subject = await session.get(Subject, payload.subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assunto não encontrado")
    if payload.topic_id:
        topic = await session.get(Topic, payload.topic_id)
        if not topic or topic.subject_id != payload.subject_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tópico não pertence ao assunto informado")
    question.subject_id = payload.subject_id
    question.topic_id = payload.topic_id
    question.classification_confidence = 1.0
    question.classification_status = "classified"
    question.classification_metadata = {
        "method": "human",
        "reviewed_by": str(user.id),
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }
    await session.commit()
    await session.refresh(question)
    candidates = await load_candidates(session)
    return build_result(question, candidates)

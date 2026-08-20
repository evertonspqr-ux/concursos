import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .cutoff_intelligence import build_recommendations, compute_competitive_index, compute_margin, compute_trend
from .database import get_session
from .dependencies import get_current_user
from .models import CutoffScore, Exam, Position, Subject, User, UserPerformance
from .schemas import (
    CompetitiveIndex,
    CutoffHistoricalPoint,
    CutoffIntelligence,
    CutoffMargin,
    CutoffScoreCreate,
    CutoffScoreRead,
    CutoffScoreUpdate,
    CutoffTrend,
    UserScoreEstimate,
)
from .study_plans import load_exam_subjects

router = APIRouter(prefix="/api/v1/exams/{exam_id}", tags=["cutoff scores"])


async def require_exam(exam_id: uuid.UUID, session: AsyncSession) -> Exam:
    exam = await session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concurso não encontrado")
    return exam


async def require_cutoff_score(exam_id: uuid.UUID, cutoff_id: uuid.UUID, session: AsyncSession) -> CutoffScore:
    row = await session.scalar(select(CutoffScore).where(CutoffScore.id == cutoff_id, CutoffScore.exam_id == exam_id))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota de corte não encontrada")
    return row


@router.post("/cutoff-scores", response_model=CutoffScoreRead, status_code=status.HTTP_201_CREATED)
async def create_cutoff_score(
    exam_id: uuid.UUID,
    payload: CutoffScoreCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> CutoffScore:
    exam = await require_exam(exam_id, session)
    if payload.position_id:
        position = await session.get(Position, payload.position_id)
        if not position or position.exam_id != exam.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cargo não pertence ao concurso informado")
    conditions = [
        CutoffScore.exam_id == exam.id,
        CutoffScore.position_id == payload.position_id if payload.position_id else CutoffScore.position_id.is_(None),
        CutoffScore.category == payload.category if payload.category else CutoffScore.category.is_(None),
    ]
    existing = await session.scalar(select(CutoffScore).where(*conditions))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe nota de corte para este concurso/cargo/categoria; use o endpoint de atualização")
    cutoff = CutoffScore(exam_id=exam.id, position_id=payload.position_id, category=payload.category, score=payload.score, source_url=payload.source_url)
    session.add(cutoff)
    await session.commit()
    await session.refresh(cutoff)
    return cutoff


@router.get("/cutoff-scores", response_model=list[CutoffScoreRead])
async def list_cutoff_scores(exam_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> list[CutoffScore]:
    await require_exam(exam_id, session)
    return list(await session.scalars(select(CutoffScore).where(CutoffScore.exam_id == exam_id).order_by(CutoffScore.created_at.desc())))


@router.put("/cutoff-scores/{cutoff_id}", response_model=CutoffScoreRead)
async def update_cutoff_score(
    exam_id: uuid.UUID,
    cutoff_id: uuid.UUID,
    payload: CutoffScoreUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> CutoffScore:
    cutoff = await require_cutoff_score(exam_id, cutoff_id, session)
    if payload.score is not None:
        cutoff.score = payload.score
    if payload.source_url is not None:
        cutoff.source_url = payload.source_url
    await session.commit()
    await session.refresh(cutoff)
    return cutoff


async def load_series(session: AsyncSession, exam: Exam, position_id: uuid.UUID | None, category: str | None) -> list[tuple[CutoffScore, Exam]]:
    """Notas de corte comparáveis: as deste exame/cargo/categoria e, quando a banca é conhecida,
    as de outros concursos da mesma banca (`examining_board`) para um cargo de mesmo nome."""
    position_name = None
    if position_id:
        position = await session.get(Position, position_id)
        position_name = position.name.strip().lower() if position else None

    stmt = select(CutoffScore)
    stmt = stmt.where(CutoffScore.category == category) if category else stmt.where(CutoffScore.category.is_(None))
    rows = list(await session.scalars(stmt))

    series: list[tuple[CutoffScore, Exam]] = []
    for row in rows:
        if row.exam_id == exam.id:
            if row.position_id != position_id:
                continue
            series.append((row, exam))
            continue
        if not exam.examining_board:
            continue
        row_exam = await session.get(Exam, row.exam_id)
        if not row_exam or row_exam.examining_board != exam.examining_board:
            continue
        if position_name:
            row_position = await session.get(Position, row.position_id) if row.position_id else None
            if not row_position or row_position.name.strip().lower() != position_name:
                continue
        elif row.position_id is not None:
            continue
        series.append((row, row_exam))
    series.sort(key=lambda pair: pair[1].exam_date or date.min)
    return series


@router.get("/cutoff-intelligence", response_model=CutoffIntelligence)
async def cutoff_intelligence(
    exam_id: uuid.UUID,
    position_id: uuid.UUID | None = Query(default=None),
    category: str | None = Query(default=None, max_length=128),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> CutoffIntelligence:
    exam = await require_exam(exam_id, session)
    if position_id:
        position = await session.get(Position, position_id)
        if not position or position.exam_id != exam.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cargo não pertence ao concurso informado")

    series = await load_series(session, exam, position_id, category)
    historical = [
        CutoffHistoricalPoint(
            exam_id=row_exam.id,
            exam_title=row_exam.title,
            exam_date=row_exam.exam_date,
            position_id=row.position_id,
            category=row.category,
            score=float(row.score),
            source_url=row.source_url,
        )
        for row, row_exam in series
    ]
    scores_ordered = [float(row.score) for row, _ in series]
    trend_result = compute_trend(scores_ordered)

    exam_subjects = await load_exam_subjects(session, exam.id, position_id)
    weighted_sum = 0.0
    weight_with_data = 0.0
    subjects_without_data_ids: list[uuid.UUID] = []
    for exam_subject in exam_subjects:
        performance = await session.scalar(
            select(UserPerformance).where(
                UserPerformance.user_id == user.id,
                UserPerformance.subject_id == exam_subject.subject_id,
                UserPerformance.topic_id.is_(None),
            )
        )
        if performance and performance.accuracy is not None:
            weighted_sum += float(exam_subject.weight) * performance.accuracy
            weight_with_data += float(exam_subject.weight)
        else:
            subjects_without_data_ids.append(exam_subject.subject_id)

    total_weight = sum(float(exam_subject.weight) for exam_subject in exam_subjects)
    if weight_with_data > 0:
        user_score = round(100 * weighted_sum / weight_with_data, 2)
        coverage = round(weight_with_data / total_weight, 4) if total_weight else 0.0
        user_estimate = UserScoreEstimate(status="estimate", score=user_score, coverage=coverage, subjects_without_data=len(subjects_without_data_ids))
    else:
        user_score = None
        user_estimate = UserScoreEstimate(status="insufficient_data", score=None, coverage=0.0, subjects_without_data=len(subjects_without_data_ids))

    own_row = next((row for row, row_exam in series if row_exam.id == exam.id and row.position_id == position_id), None)
    if own_row is not None:
        reference_value, reference_type = float(own_row.score), "historical"
    elif trend_result.status == "estimate":
        reference_value, reference_type = trend_result.projected_next_score, "estimate"
    else:
        reference_value, reference_type = None, "insufficient_data"

    margin_result = compute_margin(user_score, reference_value, reference_type)
    competitive_result = compute_competitive_index(user_score, scores_ordered)

    subject_names: dict[uuid.UUID, str] = {}
    if subjects_without_data_ids:
        rows = list(await session.scalars(select(Subject).where(Subject.id.in_(subjects_without_data_ids))))
        subject_names = {row.id: row.name for row in rows}
    recommendations = build_recommendations(
        user_estimate.status,
        margin_result,
        competitive_result,
        [subject_names.get(subject_id, str(subject_id)) for subject_id in subjects_without_data_ids],
    )

    return CutoffIntelligence(
        historical=historical,
        trend=CutoffTrend(**trend_result.__dict__),
        user_score_estimate=user_estimate,
        margin=CutoffMargin(**margin_result.__dict__),
        competitive_index=CompetitiveIndex(**competitive_result.__dict__),
        recommendations=recommendations,
    )

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .dependencies import get_current_user
from .models import Exam, ExamSubject, Position, StudyPlan, StudyPlanItem, StudySession, StudySessionStatus, Subject, Topic, User, UserPerformance
from .planner import PlannedItem, StudyCandidate, build_schedule
from .schemas import StudyPlanCreate, StudyPlanRead, StudyScheduleItem, StudySessionOutcome

router = APIRouter(prefix="/api/v1/study-plans", tags=["study plans"])


async def require_plan(plan_id: uuid.UUID, user_id: uuid.UUID, session: AsyncSession) -> StudyPlan:
    plan = await session.scalar(select(StudyPlan).where(StudyPlan.id == plan_id, StudyPlan.user_id == user_id))
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano de estudos não encontrado")
    return plan


def resolve_end_date(ends_on: date | None, exam_date: date | None, starts_on: date) -> date:
    if ends_on:
        candidate = ends_on
    elif exam_date:
        candidate = exam_date - timedelta(days=1)
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Informe ends_on ou associe o plano a um concurso com data da prova definida")
    if candidate < starts_on:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A data final deve ser posterior à data inicial")
    return candidate


async def load_exam_subjects(session: AsyncSession, exam_id: uuid.UUID, position_id: uuid.UUID | None) -> list[ExamSubject]:
    base = select(ExamSubject).where(ExamSubject.exam_id == exam_id)
    if position_id:
        scoped = list(await session.scalars(base.where(ExamSubject.position_id == position_id)))
        if scoped:
            return scoped
    return list(await session.scalars(base.where(ExamSubject.position_id.is_(None))))


async def build_candidates(session: AsyncSession, user_id: uuid.UUID, exam_subjects: list[ExamSubject]) -> list[StudyCandidate]:
    subject_ids = [item.subject_id for item in exam_subjects]
    topics = list(await session.scalars(select(Topic).where(Topic.subject_id.in_(subject_ids)))) if subject_ids else []
    topics_by_subject: dict[uuid.UUID, list[Topic]] = {}
    for topic in topics:
        topics_by_subject.setdefault(topic.subject_id, []).append(topic)

    performances = list(await session.scalars(select(UserPerformance).where(UserPerformance.user_id == user_id, UserPerformance.subject_id.in_(subject_ids)))) if subject_ids else []
    accuracy_map = {(row.subject_id, row.topic_id): row.accuracy for row in performances}

    completed_sessions = (
        list(
            await session.scalars(
                select(StudySession).where(
                    StudySession.user_id == user_id,
                    StudySession.subject_id.in_(subject_ids),
                    StudySession.status == StudySessionStatus.completed,
                )
            )
        )
        if subject_ids
        else []
    )
    last_reviewed_map: dict[tuple[uuid.UUID, uuid.UUID | None], datetime] = {}
    for session_row in completed_sessions:
        key = (session_row.subject_id, session_row.topic_id)
        moment = session_row.ended_at or session_row.started_at
        if key not in last_reviewed_map or moment > last_reviewed_map[key]:
            last_reviewed_map[key] = moment

    def accuracy_for(subject_id: uuid.UUID, topic_id: uuid.UUID | None) -> float | None:
        if (subject_id, topic_id) in accuracy_map:
            return accuracy_map[(subject_id, topic_id)]
        if topic_id is not None:
            return accuracy_map.get((subject_id, None))
        return None

    candidates: list[StudyCandidate] = []
    for exam_subject in exam_subjects:
        weight = float(exam_subject.weight)
        subject_topics = topics_by_subject.get(exam_subject.subject_id, [])
        if not subject_topics:
            candidates.append(
                StudyCandidate(
                    subject_id=exam_subject.subject_id,
                    topic_id=None,
                    weight=weight,
                    accuracy=accuracy_for(exam_subject.subject_id, None),
                    last_reviewed_at=last_reviewed_map.get((exam_subject.subject_id, None)),
                )
            )
            continue
        for topic in subject_topics:
            candidates.append(
                StudyCandidate(
                    subject_id=exam_subject.subject_id,
                    topic_id=topic.id,
                    weight=weight,
                    accuracy=accuracy_for(exam_subject.subject_id, topic.id),
                    last_reviewed_at=last_reviewed_map.get((exam_subject.subject_id, topic.id)),
                )
            )
    return candidates


async def persist_items(session: AsyncSession, plan: StudyPlan, user_id: uuid.UUID, planned_items: list[PlannedItem]) -> None:
    """Gera os IDs no Python (Mapped[...] já usa default=uuid.uuid4, client-side) para não
    precisar de um flush de rede por item — evita ~2 round-trips por item gerado no plano,
    que em planos longos (dezenas de dias) tornava a criação perceptivelmente lenta."""
    for planned in planned_items:
        item_id = uuid.uuid4()
        session.add(
            StudyPlanItem(
                id=item_id,
                study_plan_id=plan.id,
                subject_id=planned.subject_id,
                topic_id=planned.topic_id,
                scheduled_for=planned.scheduled_for,
                planned_minutes=planned.planned_minutes,
                priority=planned.priority,
            )
        )
        session.add(
            StudySession(
                user_id=user_id,
                study_plan_item_id=item_id,
                subject_id=planned.subject_id,
                topic_id=planned.topic_id,
                started_at=planned.scheduled_for,
                status=StudySessionStatus.planned,
            )
        )


async def build_schedule_view(plan: StudyPlan, session: AsyncSession) -> list[StudyScheduleItem]:
    items = list(await session.scalars(select(StudyPlanItem).where(StudyPlanItem.study_plan_id == plan.id).order_by(StudyPlanItem.scheduled_for)))
    if not items:
        return []
    item_ids = [item.id for item in items]
    sessions = list(await session.scalars(select(StudySession).where(StudySession.study_plan_item_id.in_(item_ids))))
    session_by_item = {row.study_plan_item_id: row for row in sessions}
    subject_ids = {item.subject_id for item in items if item.subject_id}
    topic_ids = {item.topic_id for item in items if item.topic_id}
    subjects = {row.id: row for row in await session.scalars(select(Subject).where(Subject.id.in_(subject_ids)))} if subject_ids else {}
    topics = {row.id: row for row in await session.scalars(select(Topic).where(Topic.id.in_(topic_ids)))} if topic_ids else {}
    result = []
    for item in items:
        linked = session_by_item.get(item.id)
        result.append(
            StudyScheduleItem(
                item=item,
                subject_name=subjects[item.subject_id].name if item.subject_id in subjects else None,
                topic_name=topics[item.topic_id].name if item.topic_id in topics else None,
                session_id=linked.id if linked else None,
                session_status=linked.status.value if linked else StudySessionStatus.planned.value,
            )
        )
    return result


@router.post("", response_model=StudyPlanRead, status_code=status.HTTP_201_CREATED)
async def create_study_plan(payload: StudyPlanCreate, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> StudyPlan:
    exam = await session.get(Exam, payload.exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concurso não encontrado")
    if payload.position_id:
        position = await session.get(Position, payload.position_id)
        if not position or position.exam_id != exam.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cargo não pertence ao concurso informado")
    ends_on = resolve_end_date(payload.ends_on, exam.exam_date, payload.starts_on)
    exam_subjects = await load_exam_subjects(session, exam.id, payload.position_id)
    if not exam_subjects:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Concurso sem disciplinas configuradas; rode a análise do edital antes de gerar o plano")
    candidates = await build_candidates(session, user.id, exam_subjects)
    plan = StudyPlan(
        user_id=user.id,
        exam_id=exam.id,
        position_id=payload.position_id,
        title=payload.title,
        available_minutes_per_day=payload.available_minutes_per_day,
        starts_on=payload.starts_on,
        ends_on=ends_on,
    )
    session.add(plan)
    await session.flush()
    planned_items = build_schedule(candidates, payload.starts_on, ends_on, payload.available_minutes_per_day, datetime.now(timezone.utc))
    await persist_items(session, plan, user.id, planned_items)
    await session.commit()
    await session.refresh(plan)
    return plan


@router.get("", response_model=list[StudyPlanRead])
async def list_study_plans(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> list[StudyPlan]:
    return list(await session.scalars(select(StudyPlan).where(StudyPlan.user_id == user.id).order_by(StudyPlan.starts_on.desc())))


@router.get("/{plan_id}/schedule", response_model=list[StudyScheduleItem])
async def get_schedule(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> list[StudyScheduleItem]:
    plan = await require_plan(plan_id, user.id, session)
    return await build_schedule_view(plan, session)


@router.post("/{plan_id}/reschedule", response_model=list[StudyScheduleItem])
async def reschedule_plan(plan_id: uuid.UUID, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> list[StudyScheduleItem]:
    plan = await require_plan(plan_id, user.id, session)
    if not plan.exam_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Plano sem concurso vinculado não pode ser reagendado automaticamente")
    exam = await session.get(Exam, plan.exam_id)
    now = datetime.now(timezone.utc)
    today = now.date()
    items = list(await session.scalars(select(StudyPlanItem).where(StudyPlanItem.study_plan_id == plan.id)))
    item_ids = [item.id for item in items]
    sessions = list(await session.scalars(select(StudySession).where(StudySession.study_plan_item_id.in_(item_ids)))) if item_ids else []
    session_by_item = {row.study_plan_item_id: row for row in sessions}

    to_remove = []
    for item in items:
        linked = session_by_item.get(item.id)
        is_completed = linked is not None and linked.status == StudySessionStatus.completed
        is_past_or_today = item.scheduled_for.date() <= today
        if not is_completed and not is_past_or_today:
            to_remove.append(item)

    if to_remove:
        ends_on = resolve_end_date(plan.ends_on, exam.exam_date, plan.starts_on)
        horizon_start = max(plan.starts_on, today + timedelta(days=1))
        exam_subjects = await load_exam_subjects(session, plan.exam_id, plan.position_id)
        candidates = await build_candidates(session, user.id, exam_subjects)
        for item in to_remove:
            linked = session_by_item.get(item.id)
            if linked is not None:
                await session.delete(linked)
            await session.delete(item)
        await session.flush()
        if horizon_start <= ends_on and candidates:
            planned_items = build_schedule(candidates, horizon_start, ends_on, plan.available_minutes_per_day, now)
            await persist_items(session, plan, user.id, planned_items)
        await session.commit()

    return await build_schedule_view(plan, session)


async def require_item_session(plan_id: uuid.UUID, item_id: uuid.UUID, user_id: uuid.UUID, session: AsyncSession) -> tuple[StudyPlanItem, StudySession]:
    plan = await require_plan(plan_id, user_id, session)
    item = await session.scalar(select(StudyPlanItem).where(StudyPlanItem.id == item_id, StudyPlanItem.study_plan_id == plan.id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item do plano não encontrado")
    study_session = await session.scalar(select(StudySession).where(StudySession.study_plan_item_id == item.id, StudySession.user_id == user_id))
    if not study_session:
        study_session = StudySession(user_id=user_id, study_plan_item_id=item.id, subject_id=item.subject_id, topic_id=item.topic_id, started_at=item.scheduled_for, status=StudySessionStatus.planned)
        session.add(study_session)
        await session.flush()
    return item, study_session


@router.post("/{plan_id}/items/{item_id}/complete", response_model=StudyScheduleItem)
async def complete_item(
    plan_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: StudySessionOutcome,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudyScheduleItem:
    item, study_session = await require_item_session(plan_id, item_id, user.id, session)
    now = datetime.now(timezone.utc)
    study_session.started_at = payload.started_at or study_session.started_at or now
    study_session.ended_at = payload.ended_at or now
    study_session.duration_seconds = payload.duration_seconds
    study_session.status = StudySessionStatus.completed
    await session.commit()
    plan = await require_plan(plan_id, user.id, session)
    schedule = await build_schedule_view(plan, session)
    return next(entry for entry in schedule if entry.item.id == item.id)


@router.post("/{plan_id}/items/{item_id}/skip", response_model=StudyScheduleItem)
async def skip_item(
    plan_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: StudySessionOutcome,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudyScheduleItem:
    item, study_session = await require_item_session(plan_id, item_id, user.id, session)
    now = datetime.now(timezone.utc)
    study_session.started_at = payload.started_at or study_session.started_at or now
    study_session.ended_at = payload.ended_at or now
    study_session.duration_seconds = payload.duration_seconds
    study_session.status = StudySessionStatus.skipped
    await session.commit()
    plan = await require_plan(plan_id, user.id, session)
    schedule = await build_schedule_view(plan, session)
    return next(entry for entry in schedule if entry.item.id == item.id)

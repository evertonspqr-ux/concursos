from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .dependencies import get_current_user
from .models import Exam, User
from .schemas import ExamCreate, ExamRead

router = APIRouter(prefix="/api/v1/exams", tags=["exams"])

@router.get("", response_model=list[ExamRead])
async def list_exams(session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> list[Exam]:
    return list(await session.scalars(select(Exam).order_by(Exam.exam_date.asc().nulls_last(), Exam.created_at.desc())))

@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
async def create_exam(payload: ExamCreate, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> Exam:
    exam = Exam(**payload.model_dump())
    session.add(exam)
    await session.commit()
    await session.refresh(exam)
    return exam

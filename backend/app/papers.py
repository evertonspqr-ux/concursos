import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .dependencies import get_current_user
from .models import AttemptSource, Exam, ExamPaper, ExamPaperQuestion, Question, User, UserQuestionAttempt
from .schemas import AnswerKeyUpdate, ExamPaperCreate, ExamPaperRead, PaperAttemptRequest, PaperAttemptResult, QuestionImportRequest

router = APIRouter(prefix="/api/v1/exams/{exam_id}/papers", tags=["exam papers"])


async def require_paper(exam_id: uuid.UUID, paper_id: uuid.UUID, session: AsyncSession) -> ExamPaper:
    paper = await session.scalar(select(ExamPaper).where(ExamPaper.id == paper_id, ExamPaper.exam_id == exam_id))
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prova não encontrada")
    return paper


@router.post("", response_model=ExamPaperRead, status_code=status.HTTP_201_CREATED)
async def create_paper(exam_id: uuid.UUID, payload: ExamPaperCreate, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> ExamPaper:
    if not await session.get(Exam, exam_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concurso não encontrado")
    paper = ExamPaper(exam_id=exam_id, **payload.model_dump())
    session.add(paper)
    await session.commit()
    await session.refresh(paper)
    return paper


@router.get("", response_model=list[ExamPaperRead])
async def list_papers(exam_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> list[ExamPaper]:
    return list(await session.scalars(select(ExamPaper).where(ExamPaper.exam_id == exam_id).order_by(ExamPaper.year.desc())))


@router.post("/{paper_id}/questions:import", status_code=status.HTTP_201_CREATED)
async def import_questions(exam_id: uuid.UUID, paper_id: uuid.UUID, payload: QuestionImportRequest, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> dict:
    await require_paper(exam_id, paper_id, session)
    last_order = await session.scalar(select(ExamPaperQuestion.order).where(ExamPaperQuestion.exam_paper_id == paper_id).order_by(ExamPaperQuestion.order.desc()).limit(1)) or 0
    question_ids = []
    for offset, item in enumerate(payload.questions, start=1):
        data = item.model_dump(exclude={"weight"})
        question = Question(**data)
        session.add(question)
        await session.flush()
        session.add(ExamPaperQuestion(exam_paper_id=paper_id, question_id=question.id, order=last_order + offset, weight=item.weight))
        question_ids.append(str(question.id))
    await session.commit()
    return {"imported": len(question_ids), "question_ids": question_ids}


@router.put("/{paper_id}/answer-key")
async def update_answer_key(exam_id: uuid.UUID, paper_id: uuid.UUID, payload: AnswerKeyUpdate, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> dict:
    paper = await require_paper(exam_id, paper_id, session)
    links = list(await session.scalars(select(ExamPaperQuestion).where(ExamPaperQuestion.exam_paper_id == paper.id)))
    by_order = {link.order: link for link in links}
    missing = sorted(set(payload.answers) - set(by_order))
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Questões inexistentes na prova: {missing}")
    paper.answer_key = {str(order): answer.upper().strip() for order, answer in payload.answers.items()}
    for order, answer in payload.answers.items():
        question = await session.get(Question, by_order[order].question_id)
        question.correct_answer = answer.upper().strip()
    await session.commit()
    return {"updated": len(payload.answers)}


@router.post("/{paper_id}/attempts", response_model=PaperAttemptResult, status_code=status.HTTP_201_CREATED)
async def submit_attempt(exam_id: uuid.UUID, paper_id: uuid.UUID, payload: PaperAttemptRequest, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> PaperAttemptResult:
    paper = await require_paper(exam_id, paper_id, session)
    links = list(await session.scalars(select(ExamPaperQuestion).where(ExamPaperQuestion.exam_paper_id == paper.id)))
    questions = {link.question_id: (link, await session.get(Question, link.question_id)) for link in links}
    received = {answer.question_id: answer for answer in payload.answers}
    unknown = received.keys() - questions.keys()
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Há questões que não pertencem a esta prova")
    correct = 0
    score = 0.0
    for question_id, answer in received.items():
        link, question = questions[question_id]
        chosen = answer.selected_answer.upper().strip() if answer.selected_answer else None
        is_correct = bool(chosen and question.correct_answer and chosen == question.correct_answer.upper())
        correct += int(is_correct)
        score += float(link.weight) if is_correct else 0
        session.add(UserQuestionAttempt(user_id=user.id, question_id=question_id, source=AttemptSource.exam_paper, exam_paper_id=paper.id, selected_answer=chosen, is_correct=is_correct, elapsed_seconds=answer.elapsed_seconds))
    await session.commit()
    return PaperAttemptResult(total_questions=len(links), answered_questions=len(received), correct_answers=correct, score=score)

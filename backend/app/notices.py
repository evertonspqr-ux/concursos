import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_session
from .dependencies import get_current_user
from .models import Exam, ExamSubject, Notice, Position, Subject, User
from .notice_analysis import analyze_notice, normalized
from .notice_service import extract_pdf_async
from .schemas import NoticeRead

router = APIRouter(prefix="/api/v1/exams/{exam_id}/notices", tags=["notices"])
settings = get_settings()


def storage_path(storage_key: str) -> Path:
    root = Path(settings.upload_directory).resolve()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=500, detail="Chave de armazenamento inválida")
    return path


@router.post("", response_model=NoticeRead, status_code=status.HTTP_201_CREATED)
async def upload_notice(
    exam_id: uuid.UUID,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Notice:
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Envie um arquivo PDF")
    exam = await session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concurso não encontrado")

    filename = Path(file.filename or "edital.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="O arquivo deve ter extensão .pdf")
    storage_key = f"{exam_id}/{uuid.uuid4()}.pdf"
    destination = storage_path(storage_key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with destination.open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PDF excede o limite permitido")
                target.write(chunk)
        extracted_text, metadata = await extract_pdf_async(destination)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Não foi possível ler este PDF") from error
    finally:
        await file.close()

    notice = Notice(exam_id=exam.id, storage_key=storage_key, filename=filename, mime_type="application/pdf", file_size_bytes=size, extracted_text=extracted_text, extraction_metadata=metadata, parsed_at=datetime.now(timezone.utc))
    session.add(notice)
    await session.commit()
    await session.refresh(notice)
    return notice


@router.get("", response_model=list[NoticeRead])
async def list_notices(exam_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> list[Notice]:
    return list(await session.scalars(select(Notice).where(Notice.exam_id == exam_id).order_by(Notice.created_at.desc())))


@router.post("/{notice_id}/analyze")
async def analyze_and_apply_notice(exam_id: uuid.UUID, notice_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> dict:
    notice = await session.scalar(select(Notice).where(Notice.id == notice_id, Notice.exam_id == exam_id))
    exam = await session.get(Exam, exam_id)
    if not notice or not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital ou concurso não encontrado")
    if not notice.extracted_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="O edital não possui texto extraído")
    result = analyze_notice(notice.extracted_text)
    if result["examining_board"]:
        exam.examining_board = result["examining_board"]
    for name in result["positions"]:
        position = await session.scalar(select(Position).where(Position.exam_id == exam.id, Position.name == name))
        if not position:
            session.add(Position(exam_id=exam.id, name=name))
    for item in result["subjects"]:
        name = item["name"]
        subject = await session.scalar(select(Subject).where(Subject.normalized_name == normalized(name)))
        if not subject:
            subject = Subject(name=name, normalized_name=normalized(name))
            session.add(subject)
            await session.flush()
        link = await session.scalar(select(ExamSubject).where(ExamSubject.exam_id == exam.id, ExamSubject.subject_id == subject.id, ExamSubject.position_id.is_(None)))
        if not link:
            session.add(ExamSubject(exam_id=exam.id, subject_id=subject.id, weight=item["weight"]))
        else:
            link.weight = item["weight"]
    notice.extraction_metadata = {**notice.extraction_metadata, "analysis": result}
    await session.commit()
    return result


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(exam_id: uuid.UUID, notice_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> None:
    notice = await session.scalar(select(Notice).where(Notice.id == notice_id, Notice.exam_id == exam_id))
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital não encontrado")
    storage_path(notice.storage_key).unlink(missing_ok=True)
    await session.delete(notice)
    await session.commit()


@router.get("/{notice_id}/file")
async def download_notice(exam_id: uuid.UUID, notice_id: uuid.UUID, session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> FileResponse:
    notice = await session.scalar(select(Notice).where(Notice.id == notice_id, Notice.exam_id == exam_id))
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edital não encontrado")
    path = storage_path(notice.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado no armazenamento")
    return FileResponse(path, media_type=notice.mime_type, filename=notice.filename)

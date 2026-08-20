from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from .config import get_settings
from .cutoff import router as cutoff_router
from .database import engine, get_session
from .dependencies import get_current_user
from .exams import router as exams_router
from .models import Base, User
from .notices import router as notices_router
from .papers import router as papers_router
from .questions import router as questions_router
from .schemas import LoginRequest, Token, UserCreate, UserProfileUpdate, UserRead, UserSummary
from .security import create_access_token, hash_password, verify_password
from .study_plans import router as study_plans_router

settings = get_settings()

@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="Concursos API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(notices_router)
app.include_router(papers_router)
app.include_router(exams_router)
app.include_router(questions_router)
app.include_router(study_plans_router)
app.include_router(cutoff_router)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/api/v1/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: AsyncSession = Depends(get_session)) -> User:
    existing = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), full_name=payload.full_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@app.post("/api/v1/auth/token", response_model=Token)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> Token:
    user = await session.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    return Token(access_token=create_access_token(str(user.id)))

@app.get("/api/v1/auth/me", response_model=UserRead)
async def current_user(user: User = Depends(get_current_user)) -> User:
    return user

@app.put("/api/v1/auth/me", response_model=UserRead)
async def update_current_user(payload: UserProfileUpdate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> User:
    user.full_name = payload.full_name.strip()
    await session.commit()
    await session.refresh(user)
    return user

@app.get("/api/v1/users", response_model=list[UserSummary])
async def list_users(session: AsyncSession = Depends(get_session), _: User = Depends(get_current_user)) -> list[User]:
    return list(await session.scalars(select(User).order_by(User.full_name)))

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://concursos:concursos@db:5432/concursos"
    jwt_secret_key: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    backend_cors_origins: str = "http://localhost:3000"
    upload_directory: str = "/app/uploads"
    max_upload_size_bytes: int = 26_214_400
    anthropic_api_key: str | None = None
    classifier_model: str = "claude-haiku-4-5-20251001"
    classifier_review_threshold: float = 0.6
    classifier_request_timeout_seconds: float = 20.0

    @property
    def cors_origins(self) -> list[str]:
        return [value.strip() for value in self.backend_cors_origins.split(",") if value.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()

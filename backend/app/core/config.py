from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "Personalized Learning System"
    environment: str = "development"

    database_url: str
    alembic_database_url: str
    database_echo: bool = False

    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    cors_origins: str = "http://localhost:5173"

    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=180)

    uploads_dir: str = "uploads"
    document_max_upload_bytes: int = Field(default=150 * 1024 * 1024, gt=0)
    document_upload_chunk_bytes: int = Field(default=1024 * 1024, gt=0)
    document_analysis_input_chars: int = Field(default=120_000, gt=1000)
    document_analysis_output_chars: int = Field(default=200_000, gt=1000)
    document_ocr_enabled: bool = True
    document_ocr_languages: str = "vie+eng"
    document_ocr_dpi: int = Field(default=200, ge=72, le=300)
    document_ocr_max_pages: int = Field(default=400, ge=1, le=2000)
    document_ocr_min_text_chars: int = Field(default=40, ge=0, le=5000)
    document_ocr_min_confidence: int = Field(default=35, ge=0, le=100)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

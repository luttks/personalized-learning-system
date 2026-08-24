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
    llm_api_key2: str | None = None
    llm_api_key3: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=180)

    # Gemini AI for Exam OCR
    gemini_api_key: str | None = None
    gemini_api_key2: str | None = None
    gemini_api_key3: str | None = None
    # Model embedding cho RAG (chấm ngữ cảnh tài liệu gốc vào prompt sinh câu hỏi kiểm tra) —
    # xem app/core/llm_client.py: LLMClient.embed_texts, app/services/exam_service.py: chunk_document_text.
    gemini_embedding_model: str = "gemini-embedding-001"
    youtube_api_key: str | None = None
    github_token: str | None = None

    # SMTP — gửi email OTP xác thực tài khoản khi đăng ký. Nếu để trống smtp_host, hệ thống
    # không gửi email thật mà chỉ ghi mã OTP ra log (phù hợp môi trường dev chưa có SMTP thật).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_from_name: str = "Personalized Learning System"
    smtp_use_tls: bool = True
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5

    # Bài kiểm tra năng lực cuối giai đoạn — chặn/mở khóa giai đoạn tiếp theo của lộ trình
    phase_assessment_pass_threshold: float = Field(default=0.7, ge=0, le=1)
    phase_assessment_num_questions: int = Field(default=10, ge=3, le=15)
    phase_assessment_submit_rate_limit_max: int = 5
    phase_assessment_submit_rate_limit_window_seconds: int = 600

    # Bài thi chốt hạ cuối lộ trình — báo cáo, không phải cửa chặn nên không có ngưỡng đậu.
    final_exam_num_questions: int = Field(default=20, ge=5, le=30)
    final_exam_submit_rate_limit_max: int = 3
    final_exam_submit_rate_limit_window_seconds: int = 600

    # Giờ gửi email nhắc học hằng ngày (theo timezone Asia/Ho_Chi_Minh của Celery Beat)
    daily_reminder_email_hour: int = 7
    daily_reminder_email_minute: int = 0

    # Giờ gửi email nhắc nhở BUỔI 2 riêng cho người học đang bị khóa giai đoạn (locked_for_retry) —
    # độc lập với daily_reminder_email_hour/_minute (buổi sáng, gửi cho MỌI người có lịch học hôm
    # nay), không đụng tới digest bình thường.
    stuck_reminder_email_hour: int = 19
    stuck_reminder_email_minute: int = 0

    uploads_dir: str = "uploads"

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

    @property
    def llm_api_keys(self) -> list[str]:
        """Danh sách tất cả Groq/LLM key hợp lệ (loại bỏ rỗng)."""
        return [
            k for k in [
                self.llm_api_key,
                self.llm_api_key2,
                self.llm_api_key3,
            ]
            if k and k.strip()
        ]

    @property
    def gemini_api_keys(self) -> list[str]:
        """Danh sách tất cả Gemini key hợp lệ (loại bỏ rỗng)."""
        valid = []
        for k in [self.gemini_api_key, self.gemini_api_key2, self.gemini_api_key3]:
            if k and k.strip():
                valid.append(k)
        return valid


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

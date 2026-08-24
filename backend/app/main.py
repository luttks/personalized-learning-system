from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.temp_upload_service import sweep_stale_temp_files


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    print(
        f"Starting {settings.project_name} "
        f"in {settings.environment} mode"
    )
    removed = sweep_stale_temp_files()
    if removed:
        print(f"Đã dọn {removed} file tạm quá hạn.")

    yield

    print("Stopping application")


_is_dev = settings.environment == "development"

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description=(
        "API cho hệ thống xây dựng lộ trình học tập "
        "cá nhân hóa dành cho học sinh phổ thông."
    ),
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
    # Swagger UI/ReDoc/OpenAPI schema làm lộ toàn bộ bề mặt API cho bất kỳ ai truy cập được —
    # chỉ bật ở môi trường development, tắt hẳn khi ENVIRONMENT != "development".
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_router,
    prefix="/api/v1",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Personalized Learning API",
        "docs": "/docs",
    }

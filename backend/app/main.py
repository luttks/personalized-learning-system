from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    print(
        f"Starting {settings.project_name} "
        f"in {settings.environment} mode"
    )

    yield

    print("Stopping application")


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

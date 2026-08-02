import asyncio
import time
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.services.content_service import verify_document_job
from app.services.document_analysis_service import analyze_document_job
from app.services.document_storage import LocalDocumentStorage
from app.worker.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="system.health_check_task",
)
def health_check_task(
    self: Any,
    message: str = "Celery hoạt động",
) -> dict[str, str]:
    self.update_state(
        state="PROGRESS",
        meta={"progress": 50},
    )

    time.sleep(2)

    return {
        "status": "completed",
        "message": message,
    }


@celery_app.task(
    bind=True,
    name="content.verify_document_upload",
)
def verify_document_upload_task(
    self: Any,
    job_id: str,
) -> dict[str, str | int]:
    del self
    storage = LocalDocumentStorage(
        settings.uploads_dir,
        max_upload_bytes=settings.document_max_upload_bytes,
        chunk_bytes=settings.document_upload_chunk_bytes,
    )

    async def run_pipeline() -> dict[str, str | int]:
        try:
            result = await verify_document_job(AsyncSessionLocal, storage, UUID(job_id))
            if result.get("status") != "ready_for_analysis":
                return result
            return await analyze_document_job(
                AsyncSessionLocal,
                storage,
                settings,
                UUID(job_id),
            )
        finally:
            # Celery creates a fresh event loop for every synchronous task.
            # Dispose pooled asyncpg connections before that loop is closed.
            await engine.dispose()

    return asyncio.run(run_pipeline())

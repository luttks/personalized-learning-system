import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models.learner import LearnerProfile
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.user import User
from app.services.content_service import verify_document_job
from app.services.document_analysis_service import analyze_document_job
from app.services.document_storage import LocalDocumentStorage
from app.services.email_service import (
    send_daily_reminder_email,
    send_roadmap_created_email,
)
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


@celery_app.task(name="notifications.send_roadmap_created_email")
def send_roadmap_created_email_task(roadmap_id: str) -> dict[str, str]:
    async def run() -> dict[str, str]:
        async with AsyncSessionLocal() as session:
            row = await session.execute(
                select(PersonalizedRoadmap, LearnerProfile, User)
                .join(LearnerProfile, LearnerProfile.id == PersonalizedRoadmap.learner_id)
                .join(User, User.id == LearnerProfile.user_id)
                .where(PersonalizedRoadmap.id == UUID(roadmap_id))
            )
            record = row.one_or_none()
            if not record:
                return {"status": "not_found"}
            roadmap, _profile, user = record
            await send_roadmap_created_email(
                email=user.email,
                learner_name=user.full_name,
                course_name=roadmap.title,
                roadmap=roadmap.roadmap_data,
                created_at=roadmap.created_at,
            )
            return {"status": "sent"}
    return asyncio.run(run())


@celery_app.task(name="notifications.send_daily_study_reminders")
def send_daily_study_reminders_task() -> dict[str, int]:
    async def run() -> dict[str, int]:
        sent = 0
        today = datetime.now(UTC).date()
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(PersonalizedRoadmap, LearnerProfile, User)
                .join(LearnerProfile, LearnerProfile.id == PersonalizedRoadmap.learner_id)
                .join(User, User.id == LearnerProfile.user_id)
                .where(User.is_active.is_(True))
            )
            for roadmap, profile, user in rows.all():
                before = sent
                await send_daily_reminder_email(
                    email=user.email,
                    learner_name=user.full_name,
                    course_name=roadmap.title,
                    roadmap=roadmap.roadmap_data,
                    today=today,
                )
                # Count only records with a matching day; no email is sent otherwise.
                if before == sent and any(str(day.get("date", "")) == today.isoformat() for phase in roadmap.roadmap_data.get("phases", []) for day in phase.get("days", [])):
                    sent += 1
        return {"sent": sent}
    return asyncio.run(run())

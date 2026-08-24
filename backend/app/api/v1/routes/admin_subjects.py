from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_admin
from app.db.session import get_db_session
from app.models.user import User
from app.services.admin_subject_service import (
    add_user_subject,
    delete_user_subject,
    list_user_subjects,
    list_all_subjects,
    rename_user_subject,
)

router = APIRouter(prefix="/admin/users", tags=["Admin Subjects"])

CurrentAdmin = Annotated[User, Depends(get_current_admin)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


class SubjectSummaryResponse(BaseModel):
    user_id: UUID | None = None
    user_email: str | None = None
    subject: str
    count: int
    last_used: str | None = None


class AddSubjectRequest(BaseModel):
    subject: str
    mode: str = "onboarding"


class RenameSubjectRequest(BaseModel):
    new_subject: str


@router.get(
    "/subjects",
    response_model=list[SubjectSummaryResponse],
)
async def get_all_subjects(
    _: CurrentAdmin,
    session: DatabaseSession,
):
    results = await list_all_subjects(session)
    return [
        SubjectSummaryResponse(
            user_id=r.get("user_id"),
            user_email=r.get("user_email"),
            subject=r["subject"],
            count=r["count"],
            last_used=r["last_used"].isoformat() if r.get("last_used") else None,
        )
        for r in results
    ]


@router.get(
    "/{user_id}/subjects",
    response_model=list[SubjectSummaryResponse],
)
async def get_user_subjects(
    user_id: UUID,
    _: CurrentAdmin,
    session: DatabaseSession,
):
    results = await list_user_subjects(session, user_id)
    return [
        SubjectSummaryResponse(
            subject=r["subject"],
            count=r["count"],
            last_used=r["last_used"].isoformat() if r["last_used"] else None,
        )
        for r in results
    ]


@router.post(
    "/{user_id}/subjects",
    response_model=SubjectSummaryResponse,
)
async def create_user_subject(
    user_id: UUID,
    payload: AddSubjectRequest,
    _: CurrentAdmin,
    session: DatabaseSession,
):
    r = await add_user_subject(session, user_id, payload.subject, payload.mode)
    return SubjectSummaryResponse(
        subject=r["subject"],
        count=r["count"],
        last_used=r["last_used"].isoformat() if r["last_used"] else None,
    )


@router.put(
    "/{user_id}/subjects/{subject_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_user_subject(
    user_id: UUID,
    subject_name: str,
    payload: RenameSubjectRequest,
    _: CurrentAdmin,
    session: DatabaseSession,
):
    await rename_user_subject(session, user_id, subject_name, payload.new_subject)


@router.delete(
    "/{user_id}/subjects/{subject_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_user_subject(
    user_id: UUID,
    subject_name: str,
    _: CurrentAdmin,
    session: DatabaseSession,
):
    await delete_user_subject(session, user_id, subject_name)

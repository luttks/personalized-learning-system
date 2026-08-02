from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_student
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.diagnostic import (
    DiagnosticAttemptResponse,
    DiagnosticResultResponse,
    DiagnosticSubmitRequest,
)
from app.services.diagnostic_question_generator import (
    DiagnosticQuestionGenerationError,
)
from app.services.diagnostic_service import (
    DiagnosticConflictError,
    DiagnosticNotFoundError,
    DiagnosticUnavailableError,
    start_diagnostic,
    submit_diagnostic,
)

router = APIRouter(tags=["Diagnostic Assessment"])
CurrentStudent = Annotated[User, Depends(get_current_student)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/catalog/courses/{course_id}/diagnostics",
    response_model=DiagnosticAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_course_diagnostic(
    course_id: UUID,
    current_student: CurrentStudent,
    session: DatabaseSession,
) -> DiagnosticAttemptResponse:
    try:
        data = await start_diagnostic(session, current_student, course_id)
    except DiagnosticUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except DiagnosticQuestionGenerationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    return DiagnosticAttemptResponse.model_validate(data)


@router.post(
    "/diagnostic-attempts/{attempt_id}/submit",
    response_model=DiagnosticResultResponse,
)
async def submit_course_diagnostic(
    attempt_id: UUID,
    payload: DiagnosticSubmitRequest,
    current_student: CurrentStudent,
    session: DatabaseSession,
) -> DiagnosticResultResponse:
    try:
        data = await submit_diagnostic(
            session,
            current_student,
            attempt_id,
            payload.answers,
            payload.idempotency_key,
        )
    except DiagnosticNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except DiagnosticConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except DiagnosticUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    return DiagnosticResultResponse.model_validate(data)

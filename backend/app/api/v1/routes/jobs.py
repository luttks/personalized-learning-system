from typing import Annotated, Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_admin
from app.models.user import User
from app.worker.celery_app import celery_app
from app.worker.tasks import health_check_task

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)

CurrentAdmin = Annotated[User, Depends(get_current_admin)]


@router.post(
    "/test",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_test_job(
    _: CurrentAdmin,
) -> dict[str, str]:
    task = health_check_task.delay(
        "Backend đã gửi thành công tác vụ cho worker."
    )

    return {
        "job_id": task.id,
        "status": "queued",
    }


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    _: CurrentAdmin,
) -> dict[str, Any]:
    result = AsyncResult(
        job_id,
        app=celery_app,
    )

    response: dict[str, Any] = {
        "job_id": job_id,
        "status": result.status,
    }

    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    elif result.info:
        response["meta"] = result.info

    return response

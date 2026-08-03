from fastapi import APIRouter

from app.api import health
from app.api.v1 import auth
from app.api.v1.routes import (
    catalog,
    content,
    course_learning_paths,
    diagnostics,
    exam_workflow,
    jobs,
    learners,
    permissions,
    student_profiles,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(student_profiles.router)
api_router.include_router(permissions.router)
api_router.include_router(users.router)
api_router.include_router(jobs.router)
api_router.include_router(learners.router)
api_router.include_router(catalog.router)
api_router.include_router(course_learning_paths.router)
api_router.include_router(diagnostics.router)
api_router.include_router(content.router)
api_router.include_router(content.job_router)
api_router.include_router(exam_workflow.router)

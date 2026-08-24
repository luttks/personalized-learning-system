from fastapi import APIRouter

from app.api import health
from app.api.v1 import auth
from app.api.v1.routes import (
    admin_subjects,
    exam,
    personalized_roadmap,
    student_profiles,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(student_profiles.router)
api_router.include_router(users.router)
api_router.include_router(admin_subjects.router)
api_router.include_router(exam.router)
api_router.include_router(personalized_roadmap.router, prefix="/learners/me/roadmaps", tags=["Roadmaps"])

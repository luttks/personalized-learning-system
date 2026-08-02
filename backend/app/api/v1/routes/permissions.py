from fastapi import APIRouter, Depends

from app.api.dependencies.auth import (
    get_current_admin,
    get_current_student,
    get_current_teacher_or_admin,
)
from app.models.user import User

router = APIRouter(
    prefix="/permissions",
    tags=["Permissions"],
)


@router.get("/student-only")
async def student_only(
    current_user: User = Depends(
        get_current_student
    ),
) -> dict[str, str]:
    return {
        "message": "Bạn đang truy cập bằng quyền học sinh.",
        "user_id": str(current_user.id),
    }


@router.get("/teacher-or-admin")
async def teacher_or_admin(
    current_user: User = Depends(
        get_current_teacher_or_admin
    ),
) -> dict[str, str]:
    return {
        "message": (
            "Bạn đang truy cập bằng quyền "
            "giáo viên hoặc quản trị viên."
        ),
        "role": current_user.role.value,
    }


@router.get("/admin-only")
async def admin_only(
    current_user: User = Depends(
        get_current_admin
    ),
) -> dict[str, str]:
    return {
        "message": "Bạn đang truy cập bằng quyền admin.",
        "user_id": str(current_user.id),
    }
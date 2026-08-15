from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import delete, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.exam_analysis_model import ExamAnalysis
from app.models.learner import LearnerProfile
from app.models.personalized_roadmap import PersonalizedRoadmap
from app.models.user import User


async def ensure_learner_profile_for_admin(session: AsyncSession, user_id: UUID) -> LearnerProfile:
    statement = select(LearnerProfile).where(LearnerProfile.user_id == user_id)
    result = await session.execute(statement)
    learner = result.scalar_one_or_none()

    if not learner:
        learner = LearnerProfile(user_id=user_id)
        session.add(learner)
        await session.commit()
        await session.refresh(learner)

    return learner


async def list_user_subjects(
    session: AsyncSession,
    user_id: UUID,
) -> list[dict]:
    learner = await ensure_learner_profile_for_admin(session, user_id)

    result = await session.execute(
        select(ExamAnalysis)
        .where(ExamAnalysis.learner_id == learner.id)
        .order_by(ExamAnalysis.created_at.desc())
    )
    analyses = list(result.scalars().all())

    subject_map = {}
    for a in analyses:
        subj = a.subject or a.ai_recommendation_json.get("_goal", "Không xác định") or "Không xác định"
        if subj not in subject_map:
            subject_map[subj] = {
                "subject": subj,
                "count": 0,
                "last_used": a.created_at,
            }
        subject_map[subj]["count"] += 1

    return list(subject_map.values())


async def list_all_subjects(session: AsyncSession) -> list[dict]:
    statement = (
        select(ExamAnalysis, User.email)
        .join(LearnerProfile, ExamAnalysis.learner_id == LearnerProfile.id)
        .join(User, LearnerProfile.user_id == User.id)
        .order_by(ExamAnalysis.created_at.desc())
    )
    result = await session.execute(statement)
    rows = result.all()

    subject_map = {}
    for a, email in rows:
        subj = a.subject or a.ai_recommendation_json.get("_goal", "Không xác định") or "Không xác định"
        key = (str(a.learner_id), subj)
        if key not in subject_map:
            # We need the user_id, which is LearnerProfile.user_id. 
            # Since we joined User, and LearnerProfile.user_id == User.id, the user.id is what we need.
            # But wait, learner_id is NOT user_id. We need user_id to pass to the API.
            # Let's get user_id by looking up the User.
            subject_map[key] = {
                "user_id": None, # Will fill below
                "learner_id": str(a.learner_id),
                "user_email": email,
                "subject": subj,
                "count": 0,
                "last_used": a.created_at,
            }
        subject_map[key]["count"] += 1

    # Now fetch user_ids for these learners
    if subject_map:
        learner_ids = list(set([UUID(k[0]) for k in subject_map.keys()]))
        st = select(LearnerProfile.id, LearnerProfile.user_id).where(LearnerProfile.id.in_(learner_ids))
        res = await session.execute(st)
        l2u = {str(l_id): str(u_id) for l_id, u_id in res.all()}
        
        for k, v in subject_map.items():
            v["user_id"] = l2u.get(v["learner_id"])

    return list(subject_map.values())


async def add_user_subject(
    session: AsyncSession,
    user_id: UUID,
    subject_name: str,
    mode: str = "onboarding",
) -> dict:
    learner = await ensure_learner_profile_for_admin(session, user_id)
    
    # Tạo một ExamAnalysis rỗng đại diện cho môn học
    dummy_analysis = ExamAnalysis(
        learner_id=learner.id,
        filename=f"Khởi tạo {subject_name}",
        subject=subject_name,
        question_count=0,
        formula_count=0,
        ai_recommendation_json={"_mode": mode, "_goal": subject_name},
        created_at=datetime.now(UTC),
    )
    session.add(dummy_analysis)
    await session.commit()
    
    return {
        "subject": subject_name,
        "count": 1,
        "last_used": dummy_analysis.created_at,
    }


async def rename_user_subject(
    session: AsyncSession,
    user_id: UUID,
    old_subject_name: str,
    new_subject_name: str,
) -> None:
    learner = await ensure_learner_profile_for_admin(session, user_id)

    # Lấy tất cả ExamAnalysis của learner này
    result = await session.execute(
        select(ExamAnalysis).where(ExamAnalysis.learner_id == learner.id)
    )
    analyses = result.scalars().all()

    # Cập nhật những bản ghi có tên môn trùng khớp (cả subject field lẫn _goal trong JSON)
    ids_to_update = []
    for a in analyses:
        effective = a.subject or (a.ai_recommendation_json or {}).get("_goal", "") or ""
        if effective.strip() == old_subject_name.strip():
            ids_to_update.append(a.id)

    if ids_to_update:
        await session.execute(
            update(ExamAnalysis)
            .where(ExamAnalysis.id.in_(ids_to_update))
            .values(subject=new_subject_name)
        )

    # Cập nhật PersonalizedRoadmap
    await session.execute(
        update(PersonalizedRoadmap)
        .where(
            PersonalizedRoadmap.learner_id == learner.id,
            PersonalizedRoadmap.title == old_subject_name,
        )
        .values(title=new_subject_name)
    )

    await session.commit()


async def delete_user_subject(
    session: AsyncSession,
    user_id: UUID,
    subject_name: str,
) -> None:
    learner = await ensure_learner_profile_for_admin(session, user_id)

    # Lấy tất cả ExamAnalysis của learner này
    result = await session.execute(
        select(ExamAnalysis).where(ExamAnalysis.learner_id == learner.id)
    )
    analyses = result.scalars().all()

    # Xác định ID cần xóa (cả subject field lẫn _goal trong JSON)
    ids_to_delete = []
    for a in analyses:
        effective = a.subject or (a.ai_recommendation_json or {}).get("_goal", "") or ""
        if effective.strip() == subject_name.strip():
            ids_to_delete.append(a.id)

    if ids_to_delete:
        # Xóa PersonalizedRoadmap liên quan
        await session.execute(
            delete(PersonalizedRoadmap)
            .where(PersonalizedRoadmap.learner_id == learner.id)
            .where(PersonalizedRoadmap.title == subject_name)
        )
        # Xóa ExamAnalysis
        await session.execute(
            delete(ExamAnalysis)
            .where(ExamAnalysis.id.in_(ids_to_delete))
        )
        await session.commit()

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.auth.middleware import get_current_user
from core.dependencies import get_student_profile_repository
from core.entities.student_profile import DeliveryPreferences, TeacherProfile
from core.entities.user import User
from core.ports.student_profile_repository import StudentProfileRepository
from core.value_objects import GradeBand, TeacherRole

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


class ProfileCreateRequest(BaseModel):
    teacher_role: TeacherRole = TeacherRole.TEACHER
    subjects: list[str] = Field(default_factory=list)
    default_grade_band: GradeBand = GradeBand.HIGH_SCHOOL
    default_audience_description: str = ""
    curriculum_framework: str = ""
    classroom_context: str = ""
    planning_goals: str = ""
    school_or_org_name: str = ""
    delivery_preferences: DeliveryPreferences = Field(default_factory=DeliveryPreferences)


class ProfileUpdateRequest(BaseModel):
    teacher_role: TeacherRole | None = None
    subjects: list[str] | None = None
    default_grade_band: GradeBand | None = None
    default_audience_description: str | None = None
    curriculum_framework: str | None = None
    classroom_context: str | None = None
    planning_goals: str | None = None
    school_or_org_name: str | None = None
    delivery_preferences: DeliveryPreferences | None = None


@router.get("", response_model=TeacherProfile)
async def get_profile(
    current_user: User = Depends(get_current_user),
    profile_repo: StudentProfileRepository = Depends(get_student_profile_repository),
):
    profile = await profile_repo.find_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Complete onboarding first.",
        )
    return profile


@router.post("", response_model=TeacherProfile, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: ProfileCreateRequest,
    current_user: User = Depends(get_current_user),
    profile_repo: StudentProfileRepository = Depends(get_student_profile_repository),
):
    existing = await profile_repo.find_by_user_id(current_user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists. Use PATCH to update.",
        )

    now = datetime.now(timezone.utc)
    profile = TeacherProfile(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        teacher_role=body.teacher_role,
        subjects=body.subjects,
        default_grade_band=body.default_grade_band,
        default_audience_description=body.default_audience_description,
        curriculum_framework=body.curriculum_framework,
        classroom_context=body.classroom_context,
        planning_goals=body.planning_goals,
        school_or_org_name=body.school_or_org_name,
        delivery_preferences=body.delivery_preferences,
        created_at=now,
        updated_at=now,
    )
    return await profile_repo.create(profile)


@router.patch("", response_model=TeacherProfile)
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    profile_repo: StudentProfileRepository = Depends(get_student_profile_repository),
):
    existing = await profile_repo.find_by_user_id(current_user.id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    update_data = body.model_dump(exclude_none=True)
    updated = TeacherProfile.model_validate(
        {
            **existing.model_dump(mode="python"),
            **update_data,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    return await profile_repo.update(updated)

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.auth.middleware import get_current_user
from core.dependencies import get_student_profile_repository
from core.entities.student_profile import TeacherProfile
from core.entities.user import User


def _now() -> datetime:
    return datetime.now(timezone.utc)


TEST_USER = User(
    id="profile-user-id",
    email="profile@example.com",
    name="Teacher User",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


class InMemoryProfileRepo:
    def __init__(self) -> None:
        self.profile: TeacherProfile | None = None

    async def find_by_user_id(self, user_id: str) -> TeacherProfile | None:
        _ = user_id
        return self.profile

    async def create(self, profile: TeacherProfile) -> TeacherProfile:
        self.profile = profile
        return profile

    async def update(self, profile: TeacherProfile) -> TeacherProfile:
        self.profile = profile
        return profile


PROFILE_REPO = InMemoryProfileRepo()


async def override_current_user():
    return TEST_USER


async def override_profile_repo():
    return PROFILE_REPO


@pytest.fixture(autouse=True)
def _install_dependency_overrides():
    PROFILE_REPO.profile = None
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_student_profile_repository] = override_profile_repo
    yield
    app.dependency_overrides.clear()


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestProfileRoutes:
    async def test_create_and_get_teacher_profile(self):
        async with await _client() as client:
            create_response = await client.post(
                "/api/v1/profile",
                json={
                    "teacher_role": "teacher",
                    "subjects": ["mathematics", "physics"],
                    "default_grade_band": "high_school",
                    "default_audience_description": "Year 10 mixed-ability maths",
                    "curriculum_framework": "GCSE AQA",
                    "classroom_context": "Limited devices and mixed confidence.",
                    "planning_goals": "More scaffolded first drafts.",
                    "school_or_org_name": "Riverside High",
                    "delivery_preferences": {
                        "tone": "supportive",
                        "reading_level": "simple",
                        "explanation_style": "concrete-first",
                        "example_style": "everyday",
                        "brevity": "tight",
                        "use_visuals": True,
                        "print_first": True,
                        "more_practice": True,
                        "keep_short": False,
                    },
                },
            )

            fetch_response = await client.get("/api/v1/profile")

        assert create_response.status_code == 201
        payload = create_response.json()
        assert payload["teacher_role"] == "teacher"
        assert payload["subjects"] == ["mathematics", "physics"]
        assert payload["delivery_preferences"]["reading_level"] == "simple"
        assert "age" not in payload
        assert fetch_response.status_code == 200
        assert fetch_response.json()["default_grade_band"] == "high_school"

    async def test_patch_updates_teacher_profile_fields(self):
        PROFILE_REPO.profile = TeacherProfile(
            id="profile-1",
            user_id=TEST_USER.id,
            teacher_role="teacher",
            subjects=["mathematics"],
            default_grade_band="high_school",
            default_audience_description="Year 10 maths",
            curriculum_framework="GCSE",
            classroom_context="Mixed confidence.",
            planning_goals="Faster first drafts.",
            school_or_org_name="Riverside High",
            delivery_preferences={
                "tone": "supportive",
                "reading_level": "standard",
                "explanation_style": "balanced",
                "example_style": "everyday",
                "brevity": "balanced",
                "use_visuals": False,
                "print_first": False,
                "more_practice": False,
                "keep_short": False,
            },
            created_at=_now(),
            updated_at=_now(),
        )

        async with await _client() as client:
            response = await client.patch(
                "/api/v1/profile",
                json={
                    "default_grade_band": "adult",
                    "delivery_preferences": {
                        "tone": "rigorous",
                        "reading_level": "advanced",
                        "explanation_style": "concept-first",
                        "example_style": "academic",
                        "brevity": "expanded",
                        "use_visuals": True,
                        "print_first": True,
                        "more_practice": True,
                        "keep_short": True,
                    },
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["default_grade_band"] == "adult"
        assert payload["delivery_preferences"]["tone"] == "rigorous"

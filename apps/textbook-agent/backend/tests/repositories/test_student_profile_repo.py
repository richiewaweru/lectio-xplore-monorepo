import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import StudentProfileModel, UserModel
from core.entities.student_profile import TeacherProfile
from core.repositories.sql_student_profile_repo import SqlStudentProfileRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestSqlStudentProfileRepository:
    def test_to_entity_normalizes_legacy_profile_rows(self):
        model = SimpleNamespace(
            id="profile-1",
            user_id="user-1",
            teacher_role=None,
            subjects='{"not":"a-list"}',
            default_grade_band=None,
            default_audience_description=None,
            curriculum_framework=None,
            classroom_context=None,
            planning_goals=None,
            school_or_org_name=None,
            delivery_preferences='{"tone":"supportive","use_visuals":true,"keep_short":true}',
            created_at=_now(),
            updated_at=_now(),
        )

        entity = SqlStudentProfileRepository._to_entity(model)

        assert entity.teacher_role.value == "teacher"
        assert entity.subjects == []
        assert entity.default_grade_band.value == "high_school"
        assert entity.default_audience_description == ""
        assert entity.delivery_preferences.tone == "supportive"
        assert entity.delivery_preferences.use_visuals is True
        assert entity.delivery_preferences.keep_short is True

    def test_to_entity_falls_back_for_invalid_json_and_unknown_enums(self):
        model = SimpleNamespace(
            id="profile-2",
            user_id="user-2",
            teacher_role="legacy-role",
            subjects='{"broken"',
            default_grade_band="legacy-band",
            default_audience_description="",
            curriculum_framework="",
            classroom_context="",
            planning_goals="",
            school_or_org_name="",
            delivery_preferences='{"broken"',
            created_at=_now(),
            updated_at=_now(),
        )

        entity = SqlStudentProfileRepository._to_entity(model)

        assert entity.teacher_role.value == "teacher"
        assert entity.subjects == []
        assert entity.default_grade_band.value == "high_school"
        assert entity.delivery_preferences.tone == "supportive"

    @pytest.fixture
    async def session(self, db_session: AsyncSession):
        db_session.add(
            UserModel(
                id="test-user-001",
                email="teacher@example.com",
                name="Teacher Test",
            )
        )
        await db_session.commit()
        yield db_session

    @pytest.fixture
    def repo(self, session: AsyncSession) -> SqlStudentProfileRepository:
        return SqlStudentProfileRepository(session)

    async def test_create_populates_legacy_required_fields(
        self,
        repo: SqlStudentProfileRepository,
        session: AsyncSession,
    ):
        now = _now()
        profile = TeacherProfile(
            id=str(uuid.uuid4()),
            user_id="test-user-001",
            teacher_role="teacher",
            subjects=["math", "geography"],
            default_grade_band="high_school",
            default_audience_description="Year 10 mixed ability.",
            curriculum_framework="IGCSE",
            classroom_context="Mixed prior knowledge.",
            planning_goals="Faster lesson drafting.",
            school_or_org_name="Lectio High School",
            delivery_preferences={
                "tone": "supportive",
                "reading_level": "standard",
                "explanation_style": "balanced",
                "example_style": "everyday",
                "brevity": "balanced",
                "use_visuals": True,
                "print_first": False,
                "more_practice": False,
                "keep_short": False,
            },
            created_at=now,
            updated_at=now,
        )

        created = await repo.create(profile)
        result = await session.execute(
            select(StudentProfileModel).where(StudentProfileModel.id == created.id)
        )
        model = result.scalar_one()

        assert created.teacher_role.value == "teacher"
        assert model.age == 18
        assert model.education_level == "high_school"
        assert model.learning_style == "reading_writing"
        assert model.preferred_notation == "plain"
        assert model.preferred_depth == "standard"
        assert model.interests == "[]"

    async def test_update_repairs_missing_legacy_fields_before_commit(
        self,
        repo: SqlStudentProfileRepository,
        session: AsyncSession,
    ):
        now = _now()
        model = StudentProfileModel(
            id="profile-legacy",
            user_id="test-user-001",
            age=None,
            education_level=None,
            interests=None,
            learning_style=None,
            preferred_notation=None,
            prior_knowledge=None,
            goals=None,
            preferred_depth=None,
            learner_description=None,
            teacher_role="teacher",
            subjects='["math"]',
            default_grade_band="high_school",
            default_audience_description="Year 10 maths",
            curriculum_framework="IGCSE",
            classroom_context="Mixed prior knowledge.",
            planning_goals="Faster drafting.",
            school_or_org_name="Lectio High School",
            delivery_preferences='{"tone":"supportive"}',
            created_at=now,
            updated_at=now,
        )
        session.add(model)
        await session.commit()

        updated = TeacherProfile(
            id="profile-legacy",
            user_id="test-user-001",
            teacher_role="teacher",
            subjects=["math", "science"],
            default_grade_band="adult",
            default_audience_description="Adult mixed-attainment learners.",
            curriculum_framework="In-house",
            classroom_context="Evening classes.",
            planning_goals="Better reuse.",
            school_or_org_name="Community College",
            delivery_preferences={
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
            created_at=now,
            updated_at=now,
        )

        saved = await repo.update(updated)
        result = await session.execute(
            select(StudentProfileModel).where(StudentProfileModel.id == saved.id)
        )
        repaired = result.scalar_one()

        assert saved.default_grade_band.value == "adult"
        assert repaired.age == 18
        assert repaired.education_level == "high_school"
        assert repaired.learning_style == "reading_writing"
        assert repaired.preferred_notation == "plain"

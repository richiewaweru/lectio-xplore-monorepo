from datetime import datetime, timezone

from pydantic import ValidationError

from core.entities.student_profile import TeacherProfile
from core.entities.user import User
from core.value_objects import GradeBand, TeacherRole


class TestTeacherProfile:
    def test_valid_profile(self):
        now = datetime.now(timezone.utc)
        profile = TeacherProfile(
            id="sp-1",
            user_id="u-1",
            teacher_role=TeacherRole.TUTOR,
            subjects=["math", "physics"],
            default_grade_band=GradeBand.ADULT,
            default_audience_description="Adult learners returning to maths.",
            curriculum_framework="Functional Skills",
            classroom_context="Mixed confidence and limited devices.",
            planning_goals="Faster planning and better scaffolds.",
            created_at=now,
            updated_at=now,
        )
        assert profile.teacher_role == TeacherRole.TUTOR
        assert profile.default_grade_band == GradeBand.ADULT
        assert len(profile.subjects) == 2

    def test_defaults(self):
        now = datetime.now(timezone.utc)
        profile = TeacherProfile(
            id="sp-1",
            user_id="u-1",
            created_at=now,
            updated_at=now,
        )
        assert profile.subjects == []
        assert profile.teacher_role == TeacherRole.TEACHER
        assert profile.default_grade_band == GradeBand.HIGH_SCHOOL
        assert profile.delivery_preferences.tone == "supportive"
        assert profile.delivery_preferences.brevity == "balanced"

    def test_rejects_invalid_delivery_preferences(self):
        now = datetime.now(timezone.utc)
        try:
            TeacherProfile(
                id="sp-1",
                user_id="u-1",
                delivery_preferences={"tone": "chaotic"},
                created_at=now,
                updated_at=now,
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("Expected profile validation to fail for invalid tone")


class TestUser:
    def test_valid_user(self):
        now = datetime.now(timezone.utc)
        user = User(
            id="u-1",
            email="test@example.com",
            name="Test",
            created_at=now,
            updated_at=now,
        )
        assert user.email == "test@example.com"
        assert user.has_profile is False

    def test_user_with_profile(self):
        now = datetime.now(timezone.utc)
        user = User(
            id="u-1",
            email="test@example.com",
            has_profile=True,
            created_at=now,
            updated_at=now,
        )
        assert user.has_profile is True


class TestTeacherRole:
    def test_all_values(self):
        expected = {"teacher", "tutor", "homeschool", "instructor"}
        assert {e.value for e in TeacherRole} == expected


class TestGradeBand:
    def test_all_values(self):
        expected = {"primary", "middle", "high_school", "undergraduate", "adult"}
        assert {s.value for s in GradeBand} == expected

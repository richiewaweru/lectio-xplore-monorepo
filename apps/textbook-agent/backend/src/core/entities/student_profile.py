from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.value_objects import GradeBand, TeacherRole

Tone = Literal["supportive", "neutral", "rigorous"]
ReadingLevel = Literal["simple", "standard", "advanced"]
ExplanationStyle = Literal["concrete-first", "concept-first", "balanced"]
ExampleStyle = Literal["everyday", "academic", "exam"]
Brevity = Literal["tight", "balanced", "expanded"]


class DeliveryPreferences(BaseModel):
    tone: Tone = "supportive"
    reading_level: ReadingLevel = "standard"
    explanation_style: ExplanationStyle = "balanced"
    example_style: ExampleStyle = "everyday"
    brevity: Brevity = "balanced"
    use_visuals: bool = False
    print_first: bool = False
    more_practice: bool = False
    keep_short: bool = False


class TeacherProfile(BaseModel):
    """Persistent teacher profile for reusable account and classroom defaults."""

    id: str
    user_id: str
    teacher_role: TeacherRole = TeacherRole.TEACHER
    subjects: list[str] = Field(default_factory=list)
    default_grade_band: GradeBand = GradeBand.HIGH_SCHOOL
    default_audience_description: str = ""
    curriculum_framework: str = ""
    classroom_context: str = ""
    planning_goals: str = ""
    school_or_org_name: str = ""
    delivery_preferences: DeliveryPreferences = Field(default_factory=DeliveryPreferences)
    created_at: datetime
    updated_at: datetime


# Backward-compatible alias while the persistence/database names catch up.
# For the current product phase, this alias still represents the teacher
# profile model, and the legacy student naming remains only to avoid churn
# during rollout and external DB stabilization.
StudentProfile = TeacherProfile

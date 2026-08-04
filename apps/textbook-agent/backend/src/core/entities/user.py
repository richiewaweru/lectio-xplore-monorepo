from datetime import datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    """Authenticated user entity."""

    id: str
    email: str
    name: str | None = None
    picture_url: str | None = None
    created_at: datetime
    updated_at: datetime
    has_profile: bool = Field(
        default=False,
        description="Whether the user has completed onboarding",
    )

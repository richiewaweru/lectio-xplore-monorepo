from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PackStatus = Literal["pending", "running", "complete", "failed"]
ResourcePhase = Literal[
    "pending",
    "planning",
    "awaiting_review",
    "queued",
    "generating",
    "done",
    "failed",
]


class ResourceStatus(BaseModel):
    resource_id: str
    generation_id: str | None = None
    label: str
    resource_type: str
    status: str
    phase: ResourcePhase


class PackStatusResponse(BaseModel):
    pack_id: str
    status: PackStatus
    learning_job_type: str
    subject: str
    topic: str
    resource_count: int
    completed_count: int
    current_phase: str | None = None
    current_resource_label: str | None = None
    resources: list[ResourceStatus] = Field(default_factory=list)
    created_at: str
    completed_at: str | None = None

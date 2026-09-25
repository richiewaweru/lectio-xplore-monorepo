"""Domain-neutral contracts for durable generation runtime state."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    computed_field,
    field_validator,
    model_validator,
)


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    READY = "ready"
    FAILED_RECOVERABLE = "failed_recoverable"
    FAILED_TERMINAL = "failed_terminal"
    CANCELLED = "cancelled"


class WorkItemStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED_RECOVERABLE = "failed_recoverable"
    FAILED_TERMINAL = "failed_terminal"
    CANCELLED = "cancelled"


class RunType(StrEnum):
    PREPARATION = "preparation"
    SHARED_DOCUMENT = "shared_document"
    LEARN = "learn"
    PRINT = "print"
    PUBLISH = "publish"
    PDF = "pdf"


class ErrorClass(StrEnum):
    VALIDATION = "validation"
    PROVIDER_TRANSPORT = "provider_transport"
    PROVIDER_OUTPUT = "provider_output"
    SOURCE_CONFLICT = "source_conflict"
    LEASE_LOST = "lease_lost"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNSUPPORTED_CONTRACT = "unsupported_contract"
    INTERNAL_PROGRAMMING = "internal_programming"
    CANCELLED = "cancelled"


class RecoveryAction(StrEnum):
    RETRY = "retry"
    REVIEW = "review"
    REGENERATE = "regenerate"
    NONE = "none"


_RETRYABLE_ERROR_CLASSES = frozenset(
    {ErrorClass.VALIDATION, ErrorClass.PROVIDER_TRANSPORT, ErrorClass.PROVIDER_OUTPUT}
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class BuildContract(Contract):
    id: str
    path_lesson_id: str
    owner_user_id: str
    created_at: datetime


class RunContract(Contract):
    id: str
    build_id: str
    run_type: RunType
    owner_user_id: str
    status: RunStatus
    stage: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    source_artifact_type: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_revision: int = Field(ge=1)
    source_hash: str = Field(min_length=1)
    output_artifact_type: str | None = None
    output_artifact_id: str | None = None
    output_revision: int | None = Field(default=None, ge=1)
    output_hash: str | None = None
    request_key: str = Field(min_length=1)
    error_code: str | None = None
    error_class: ErrorClass | None = None
    error_summary: str | None = None
    recovery_action: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def ready_requires_complete_output(self) -> RunContract:
        output_identity = (
            self.output_artifact_type,
            self.output_artifact_id,
            self.output_revision,
            self.output_hash,
        )
        if any(value is not None for value in output_identity) and any(
            value is None or value == "" for value in output_identity
        ):
            raise ValueError("output identity must be complete or absent")
        if self.status == RunStatus.READY and any(value is None for value in output_identity):
            raise ValueError("ready runs require a complete output identity and hash")
        return self


class WorkItemContract(Contract):
    id: str
    run_id: str
    replaces_work_item_id: str | None = None
    item_key: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    status: WorkItemStatus
    attempt: int = Field(ge=1)
    max_attempts: int = Field(ge=1)
    input_hash: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    composition_identity: str | None = None
    lease_owner: str | None = None
    lease_token: int | None = Field(default=None, ge=1)
    lease_expires_at: datetime | None = None
    checkpoint_json: Any | None = None
    output_json: Any | None = None
    output_hash: str | None = None
    error_code: str | None = None
    error_class: ErrorClass | None = None
    error_summary: str | None = None
    recovery_action: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    updated_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def ready_requires_complete_output(self) -> WorkItemContract:
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")
        if self.status == WorkItemStatus.READY and (
            self.output_json is None or not self.output_hash
        ):
            raise ValueError("ready work items require output_json and output_hash")
        return self


class EventContract(Contract):
    id: str
    run_id: str
    work_item_id: str | None = None
    seq: int = Field(ge=1)
    event_type: str = Field(min_length=1)
    status: RunStatus
    stage: str = Field(min_length=1)
    attempt: int = Field(ge=1)
    error_code: str | None = None
    safe_payload_json: dict[str, Any]
    created_at: datetime


class RunAdmission(Contract):
    build_id: str
    owner_user_id: str
    run_type: RunType
    request_key: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    source_artifact_type: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_revision: int = Field(ge=1)
    source_hash: str = Field(min_length=1)


class WorkItemAdmission(Contract):
    run_id: str
    item_key: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    composition_identity: str | None = None
    max_attempts: int = Field(default=3, ge=1)


class WorkItemFailure(Contract):
    """Safe, closed failure input; only bounded output/transport classes retry."""

    error_code: str = Field(min_length=1, max_length=128)
    error_class: ErrorClass
    safe_summary: str = Field(min_length=1, max_length=512)
    recovery_action: RecoveryAction

    @model_validator(mode="after")
    def retry_action_requires_retryable_class(self) -> WorkItemFailure:
        if self.error_class == ErrorClass.CANCELLED:
            raise ValueError("cancellation uses the dedicated cancellation lifecycle")
        if (
            self.recovery_action == RecoveryAction.RETRY
            and self.error_class not in _RETRYABLE_ERROR_CLASSES
        ):
            raise ValueError("this error class cannot request a work-item retry")
        return self

    @computed_field
    @property
    def retryable(self) -> bool:
        """Whether this failure class is eligible for bounded work-item retry."""
        return self.error_class in _RETRYABLE_ERROR_CLASSES


class BuildAdmission(Contract):
    owner_user_id: str
    path_lesson_id: str


class SourceIdentity(Contract):
    """Freshly recomputed identity required before generic work can start."""

    source_artifact_type: str = Field(min_length=1)
    source_artifact_id: str = Field(min_length=1)
    source_revision: int = Field(ge=1)
    source_hash: str = Field(min_length=1)


class WorkItemReplacement(Contract):
    """Internal authorization to replace one item after bounded repair validation."""

    predecessor_work_item_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    source: SourceIdentity
    replacement: WorkItemAdmission


class RunFinalization(Contract):
    """Generic identity used by trusted runtime source/artifact verifiers."""

    source: SourceIdentity
    output_artifact_type: str = Field(min_length=1)
    output_artifact_id: str = Field(min_length=1)
    output_revision: int = Field(ge=1)


class VerifiedArtifact(Contract):
    """Trusted durable artifact row resolved by a Run finalization adapter."""

    artifact_type: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    output_json: JsonValue
    output_hash: str = Field(min_length=1)

    @field_validator("output_json")
    @classmethod
    def output_is_strict_json(cls, value: JsonValue) -> JsonValue:
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("verified artifact output must be strict JSON") from exc
        return value


class RuntimeCheckpointCompatibility(Contract):
    """All source and definition inputs that authorize checkpoint reuse."""

    schema_version: int = Field(ge=1)
    source_revision: int = Field(ge=1)
    source_hash: str = Field(min_length=1)
    input_hash: str = Field(min_length=1)
    definition_hash: str = Field(min_length=1)
    composition_identity: str | None = None


class RuntimeCheckpoint(Contract):
    compatibility: RuntimeCheckpointCompatibility
    payload: JsonValue
    payload_hash: str = Field(min_length=1)

    @field_validator("payload")
    @classmethod
    def payload_is_strict_json(cls, value: JsonValue) -> JsonValue:
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("checkpoint payload must be strict JSON") from exc
        return value

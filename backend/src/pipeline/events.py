"""
pipeline.events

Typed pipeline event models plus a compatibility bridge to the shared core bus.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

import core.events as core_events
from pipeline.api import PipelineSectionReport
from pipeline.reporting import (
    GenerationPlannerTraceSection,
    GenerationReportOutlineSection,
)
from pipeline.runtime_progress import RuntimeProgressSnapshot
from pipeline.state import NodeFailureDetail
from pipeline.types.section_content import SectionContent
from pipeline.types.requests import GenerationMode


class PipelineStartEvent(BaseModel):
    type: Literal["pipeline_start"] = "pipeline_start"
    generation_id: str
    section_count: int
    template_id: str
    preset_id: str
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SectionStartedEvent(BaseModel):
    type: Literal["section_started"] = "section_started"
    generation_id: str
    section_id: str
    title: str
    position: int


class CurriculumPlannedEvent(BaseModel):
    type: Literal["curriculum_planned"] = "curriculum_planned"
    generation_id: str
    path: Literal["fresh", "seeded_enrichment"]
    result: Literal["planned", "enriched", "fallback"]
    duplicate_term_warnings: list[str] = Field(default_factory=list)
    runtime_curriculum_outline: list[GenerationReportOutlineSection] = Field(
        default_factory=list
    )
    planner_trace_sections: list[GenerationPlannerTraceSection] = Field(
        default_factory=list
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SectionReadyEvent(BaseModel):
    type: Literal["section_ready"] = "section_ready"
    generation_id: str
    section_id: str
    section: SectionContent
    completed_sections: int
    total_sections: int


class SectionPartialEvent(BaseModel):
    type: Literal["section_partial"] = "section_partial"
    generation_id: str
    section_id: str
    section: SectionContent
    template_id: str
    status: str
    visual_mode: Literal["svg", "image"] | None = None
    pending_assets: list[str] = Field(default_factory=list)
    updated_at: str


class SectionAssetPendingEvent(BaseModel):
    type: Literal["section_asset_pending"] = "section_asset_pending"
    generation_id: str
    section_id: str
    pending_assets: list[str] = Field(default_factory=list)
    status: str
    visual_mode: Literal["svg", "image"] | None = None
    updated_at: str


class SectionAssetReadyEvent(BaseModel):
    type: Literal["section_asset_ready"] = "section_asset_ready"
    generation_id: str
    section_id: str
    ready_assets: list[str] = Field(default_factory=list)
    pending_assets: list[str] = Field(default_factory=list)
    visual_mode: Literal["svg", "image"] | None = None
    updated_at: str


class SectionFinalEvent(BaseModel):
    type: Literal["section_final"] = "section_final"
    generation_id: str
    section_id: str
    completed_sections: int
    total_sections: int


class QCCompleteEvent(BaseModel):
    type: Literal["qc_complete"] = "qc_complete"
    generation_id: str
    passed: int
    total: int


class RuntimePolicyEvent(BaseModel):
    type: Literal["runtime_policy"] = "runtime_policy"
    generation_id: str
    mode: GenerationMode
    generation_timeout_seconds: float
    generation_max_concurrent_per_user: int
    max_section_rerenders: int
    concurrency: dict[str, int]
    timeouts: dict[str, float]
    retries: dict[str, dict[str, float | int]]
    emitted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class RuntimeProgressEvent(BaseModel):
    type: Literal["runtime_progress"] = "runtime_progress"
    generation_id: str
    snapshot: RuntimeProgressSnapshot
    emitted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CompleteEvent(BaseModel):
    type: Literal["complete"] = "complete"
    generation_id: str
    final_status: Literal["completed", "partial", "failed"] = "completed"
    quality_passed: bool | None = None
    completed_sections: int | None = None
    total_sections: int | None = None
    document_url: str | None = None
    report_url: str | None = None
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    generation_id: str
    message: str
    report_url: str | None = None
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class GenerationFailedEvent(BaseModel):
    type: Literal["generation_failed"] = "generation_failed"
    generation_id: str
    message: str
    error_type: str | None = None
    error_code: str | None = None
    report_url: str | None = None
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SectionAttemptStartedEvent(BaseModel):
    type: Literal["section_attempt_started"] = "section_attempt_started"
    generation_id: str
    section_id: str
    attempt: int
    trigger: Literal["initial", "rerender"]
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class NodeStartedEvent(BaseModel):
    type: Literal["node_started"] = "node_started"
    generation_id: str
    node: str
    attempt: int | None = None
    section_id: str | None = None
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class NodeFinishedEvent(BaseModel):
    type: Literal["node_finished"] = "node_finished"
    generation_id: str
    node: str
    status: Literal["succeeded", "failed"]
    attempt: int | None = None
    section_id: str | None = None
    latency_ms: float | None = None
    error: str | None = None
    finished_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SectionReportUpdatedEvent(BaseModel):
    type: Literal["section_report_updated"] = "section_report_updated"
    generation_id: str
    section_id: str
    source: Literal["assembler", "qc_agent"]
    report: PipelineSectionReport
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SectionRetryQueuedEvent(BaseModel):
    type: Literal["section_retry_queued"] = "section_retry_queued"
    generation_id: str
    section_id: str
    reason: str
    block_type: str
    next_attempt: int
    max_attempts: int
    queued_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MediaPlanReadyEvent(BaseModel):
    type: Literal["media_plan_ready"] = "media_plan_ready"
    generation_id: str
    section_id: str
    slot_count: int
    planned_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class VisualPlacementsCommittedEvent(BaseModel):
    type: Literal["visual_placements_committed"] = "visual_placements_committed"
    generation_id: str
    section_id: str
    placements_count: int
    placements_summary: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SlotRenderModeResolvedEvent(BaseModel):
    type: Literal["slot_render_mode_resolved"] = "slot_render_mode_resolved"
    generation_id: str
    section_id: str
    slot_id: str
    render_mode: str
    decided_by: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SimulationTypeSelectedEvent(BaseModel):
    type: Literal["simulation_type_selected"] = "simulation_type_selected"
    generation_id: str
    section_id: str
    simulation_type: str
    simulation_goal: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class IntentResolvedEvent(BaseModel):
    type: Literal["intent_resolved"] = "intent_resolved"
    generation_id: str
    topic_type: str
    learning_outcome: str
    resolved_by: str
    template_override: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MediaFrameStartedEvent(BaseModel):
    type: Literal["media_frame_started"] = "media_frame_started"
    generation_id: str
    section_id: str
    slot_id: str
    slot_type: str
    frame_key: str
    frame_index: int
    render: str | None = None
    label: str | None = None
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MediaFrameReadyEvent(BaseModel):
    type: Literal["media_frame_ready"] = "media_frame_ready"
    generation_id: str
    section_id: str
    slot_id: str
    slot_type: str
    frame_key: str
    frame_index: int
    render: str | None = None
    label: str | None = None
    ready_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MediaFrameFailedEvent(BaseModel):
    type: Literal["media_frame_failed"] = "media_frame_failed"
    generation_id: str
    section_id: str
    slot_id: str
    slot_type: str
    frame_key: str
    frame_index: int
    render: str | None = None
    label: str | None = None
    error: str | None = None
    failed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MediaSlotReadyEvent(BaseModel):
    type: Literal["media_slot_ready"] = "media_slot_ready"
    generation_id: str
    section_id: str
    slot_id: str
    slot_type: str
    ready_frames: int
    total_frames: int
    ready_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MediaSlotFailedEvent(BaseModel):
    type: Literal["media_slot_failed"] = "media_slot_failed"
    generation_id: str
    section_id: str
    slot_id: str
    slot_type: str
    ready_frames: int
    total_frames: int
    error: str | None = None
    failed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SectionMediaBlockedEvent(BaseModel):
    type: Literal["section_media_blocked"] = "section_media_blocked"
    generation_id: str
    section_id: str
    slot_ids: list[str] = Field(default_factory=list)
    reason: str
    blocked_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SectionFailedEvent(BaseModel):
    type: Literal["section_failed"] = "section_failed"
    generation_id: str
    section_id: str
    title: str
    position: int
    failed_at_node: str
    error_type: str
    error_summary: str
    focus: str | None = None
    bridges_from: str | None = None
    bridges_to: str | None = None
    needs_diagram: bool = False
    visual_placements_count: int = 0
    needs_worked_example: bool = False
    attempt_count: int = 0
    can_retry: bool = False
    missing_components: list[str] = Field(default_factory=list)
    failure_detail: NodeFailureDetail | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ValidationRepairAttemptedEvent(BaseModel):
    type: Literal["validation_repair_attempted"] = "validation_repair_attempted"
    generation_id: str
    section_id: str
    node: str = "content_generator"
    attempt: int = 1
    error_summary: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ValidationRepairSucceededEvent(BaseModel):
    type: Literal["validation_repair_succeeded"] = "validation_repair_succeeded"
    generation_id: str
    section_id: str
    node: str = "content_generator"
    attempt: int = 1
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DiagramOutcomeEvent(BaseModel):
    type: Literal["diagram_outcome"] = "diagram_outcome"
    generation_id: str
    section_id: str
    outcome: Literal["success", "timeout", "error", "skipped"]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ImageOutcomeEvent(BaseModel):
    type: Literal["image_outcome"] = "image_outcome"
    generation_id: str
    section_id: str
    outcome: Literal["success", "timeout", "error", "skipped"]
    provider: str | None = None
    attempts: int = 1
    error_message: str | None = None
    duration_ms: float | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class InteractionOutcomeEvent(BaseModel):
    type: Literal["interaction_outcome"] = "interaction_outcome"
    generation_id: str
    section_id: str
    outcome: Literal["generated", "skipped"]
    skip_reason: Literal[
        "policy_disabled",
        "no_slot",
        "low_interaction_level",
        "no_plan",
    ] | None = None
    interaction_count: int = 0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class InteractionRetryQueuedEvent(BaseModel):
    type: Literal["interaction_retry_queued"] = "interaction_retry_queued"
    generation_id: str
    section_id: str
    next_attempt: int = 2
    reason: str = ""
    queued_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class FieldRegenOutcomeEvent(BaseModel):
    type: Literal["field_regen_outcome"] = "field_regen_outcome"
    generation_id: str
    section_id: str
    field_name: str
    outcome: Literal["success", "failed"]
    error_message: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


LLMCallStartedEvent = core_events.LLMCallStartedEvent
LLMCallSucceededEvent = core_events.LLMCallSucceededEvent
LLMCallFailedEvent = core_events.LLMCallFailedEvent

PipelineEvent = (
    PipelineStartEvent
    | CurriculumPlannedEvent
    | SectionStartedEvent
    | SectionPartialEvent
    | SectionAssetPendingEvent
    | SectionAssetReadyEvent
    | SectionFinalEvent
    | SectionReadyEvent
    | QCCompleteEvent
    | RuntimePolicyEvent
    | RuntimeProgressEvent
    | CompleteEvent
    | ErrorEvent
    | GenerationFailedEvent
    | LLMCallStartedEvent
    | LLMCallSucceededEvent
    | LLMCallFailedEvent
    | SectionAttemptStartedEvent
    | NodeStartedEvent
    | NodeFinishedEvent
    | SectionReportUpdatedEvent
    | SectionRetryQueuedEvent
    | MediaPlanReadyEvent
    | VisualPlacementsCommittedEvent
    | SlotRenderModeResolvedEvent
    | SimulationTypeSelectedEvent
    | IntentResolvedEvent
    | MediaFrameStartedEvent
    | MediaFrameReadyEvent
    | MediaFrameFailedEvent
    | MediaSlotReadyEvent
    | MediaSlotFailedEvent
    | SectionMediaBlockedEvent
    | SectionFailedEvent
    | ValidationRepairAttemptedEvent
    | ValidationRepairSucceededEvent
    | DiagramOutcomeEvent
    | ImageOutcomeEvent
    | InteractionOutcomeEvent
    | InteractionRetryQueuedEvent
    | FieldRegenOutcomeEvent
)


PipelineEventBus = core_events.EventBus
event_bus = core_events.event_bus


__all__ = [
    "CompleteEvent",
    "CurriculumPlannedEvent",
    "ErrorEvent",
    "GenerationFailedEvent",
    "PipelineEvent",
    "PipelineEventBus",
    "PipelineStartEvent",
    "QCCompleteEvent",
    "RuntimePolicyEvent",
    "RuntimeProgressEvent",
    "SectionAssetPendingEvent",
    "SectionAssetReadyEvent",
    "SectionFinalEvent",
    "SectionPartialEvent",
    "SectionReadyEvent",
    "SectionStartedEvent",
    "SectionAttemptStartedEvent",
    "SectionFailedEvent",
    "NodeStartedEvent",
    "NodeFinishedEvent",
    "SectionReportUpdatedEvent",
    "SectionRetryQueuedEvent",
    "MediaPlanReadyEvent",
    "VisualPlacementsCommittedEvent",
    "SlotRenderModeResolvedEvent",
    "SimulationTypeSelectedEvent",
    "IntentResolvedEvent",
    "MediaFrameStartedEvent",
    "MediaFrameReadyEvent",
    "MediaFrameFailedEvent",
    "MediaSlotReadyEvent",
    "MediaSlotFailedEvent",
    "SectionMediaBlockedEvent",
    "ValidationRepairAttemptedEvent",
    "ValidationRepairSucceededEvent",
    "DiagramOutcomeEvent",
    "ImageOutcomeEvent",
    "InteractionOutcomeEvent",
    "InteractionRetryQueuedEvent",
    "FieldRegenOutcomeEvent",
    "PipelineEventBus",
    "event_bus",
    "LLMCallStartedEvent",
    "LLMCallSucceededEvent",
    "LLMCallFailedEvent",
]

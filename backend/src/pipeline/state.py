"""
pipeline.state

The single state object that flows through the LangGraph pipeline.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field, field_validator

from pipeline.media.types import (
    MediaPlan,
    VisualFrameResult,
    VisualSlotResult,
)
from pipeline.types.composition import CompositionPlan
from pipeline.types.requests import PipelineRequest, SectionPlan
from pipeline.types.section_content import InteractionSpec, SectionContent
from pipeline.types.template_contract import TemplateContractSummary


def _merge_dicts(left: dict, right: dict) -> dict:
    return {**left, **right}


def _last_wins(existing: Any, new: Any) -> Any:
    """Allow concurrent scalar writes by taking the most recent value."""
    _ = existing
    return new


def _merge_rerender_requests(left: dict, right: dict) -> dict:
    merged = dict(left)
    for section_id, request in right.items():
        if request is None:
            merged.pop(section_id, None)
            continue
        merged[section_id] = request
    return merged


def merge_state_updates(state: dict[str, Any], output: dict[str, Any]) -> None:
    for key, value in output.items():
        if (
            key == "rerender_requests"
            and isinstance(value, dict)
            and isinstance(state.get(key), dict)
        ):
            state[key] = _merge_rerender_requests(state[key], value)
        elif isinstance(value, dict) and isinstance(state.get(key), dict):
            state[key] = {**state[key], **value}
        elif isinstance(value, list) and isinstance(state.get(key), list):
            state[key] = state[key] + value
        else:
            state[key] = value


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    FAILED = "failed"


class StyleContext(BaseModel):
    preset_id: str
    palette: str
    surface_style: str
    density: str
    typography: str
    template_id: str
    template_family: str
    interaction_level: str
    grade_band: str
    learner_fit: str

    def diagram_complexity(self) -> str:
        if self.grade_band == "primary" or self.learner_fit == "scaffolded":
            return "simplified"
        if self.grade_band == "advanced" or self.learner_fit == "advanced":
            return "detailed"
        return "standard"


class PipelineError(BaseModel):
    node: str
    message: str
    section_id: Optional[str] = None
    recoverable: bool = True


class RerenderRequest(BaseModel):
    section_id: str
    reason: str
    block_type: str
    auto_fix: Optional[str] = None


class MediaFrameRetryRequest(BaseModel):
    section_id: str
    slot_id: str
    slot_type: str
    frame_key: str
    frame_index: int
    executor_node: str
    reason: str | None = None


class QCReport(BaseModel):
    section_id: str
    passed: bool
    issues: list[dict]
    warnings: list[str]


class NodeFailureDetail(BaseModel):
    node: str
    section_id: str
    timestamp: str
    error_type: str
    error_message: str
    retry_attempt: int = 0
    will_retry: bool = False


class FailedSectionRecord(BaseModel):
    section_id: str
    title: str
    position: int
    focus: str | None = None
    bridges_from: str | None = None
    bridges_to: str | None = None
    needs_diagram: bool = False
    visual_placements_count: int = 0
    needs_worked_example: bool = False
    failed_at_node: str
    error_type: str
    error_summary: str
    attempt_count: int = 0
    can_retry: bool = False
    missing_components: list[str] = Field(default_factory=list)
    failure_detail: NodeFailureDetail


class PartialSectionRecord(BaseModel):
    section_id: str
    template_id: str
    content: SectionContent
    status: str = "partial"
    visual_mode: str | None = None
    pending_assets: list[str] = Field(default_factory=list)
    updated_at: str


class TextbookPipelineState(BaseModel):
    request: PipelineRequest
    contract: TemplateContractSummary

    curriculum_outline: Optional[list[SectionPlan]] = None
    style_context: Optional[StyleContext] = None
    current_section_id: Annotated[Optional[str], _last_wins] = None
    current_section_plan: Annotated[Optional[SectionPlan], _last_wins] = None

    generated_sections: Annotated[dict[str, SectionContent], _merge_dicts] = Field(
        default_factory=dict
    )
    media_plans: Annotated[dict[str, MediaPlan], _merge_dicts] = Field(default_factory=dict)
    media_slot_results: Annotated[dict[str, dict[str, VisualSlotResult]], _merge_dicts] = Field(
        default_factory=dict
    )
    media_frame_results: Annotated[
        dict[str, dict[str, dict[str, VisualFrameResult]]],
        _merge_dicts,
    ] = Field(
        default_factory=dict
    )
    media_retry_count: Annotated[dict[str, int], _merge_dicts] = Field(default_factory=dict)
    media_frame_retry_count: Annotated[
        dict[str, dict[str, dict[str, int]]],
        _merge_dicts,
    ] = Field(default_factory=dict)
    current_media_retry: Annotated[MediaFrameRetryRequest | None, _last_wins] = None
    media_lifecycle: Annotated[dict[str, str], _merge_dicts] = Field(default_factory=dict)
    composition_plans: Annotated[dict[str, CompositionPlan], _merge_dicts] = Field(
        default_factory=dict
    )
    interaction_specs: Annotated[dict[str, InteractionSpec], _merge_dicts] = Field(
        default_factory=dict
    )
    interaction_usage: Annotated[dict[str, int], _merge_dicts] = Field(
        default_factory=dict
    )
    partial_sections: Annotated[dict[str, PartialSectionRecord], _merge_dicts] = Field(
        default_factory=dict
    )
    section_pending_assets: Annotated[dict[str, list[str]], _merge_dicts] = Field(
        default_factory=dict
    )
    section_lifecycle: Annotated[dict[str, str], _merge_dicts] = Field(
        default_factory=dict
    )
    assembled_sections: Annotated[dict[str, SectionContent], _merge_dicts] = Field(
        default_factory=dict
    )
    qc_reports: Annotated[dict[str, QCReport], _merge_dicts] = Field(
        default_factory=dict
    )

    rerender_requests: Annotated[
        dict[str, RerenderRequest],
        _merge_rerender_requests,
    ] = Field(default_factory=dict)
    rerender_count: Annotated[dict[str, int], _merge_dicts] = Field(default_factory=dict)
    diagram_retry_count: Annotated[dict[str, int], _merge_dicts] = Field(
        default_factory=dict
    )
    interaction_retry_count: Annotated[dict[str, int], _merge_dicts] = Field(
        default_factory=dict
    )
    max_rerenders: int = 2

    completed_nodes: Annotated[list[str], operator.add] = Field(default_factory=list)
    errors: Annotated[list[PipelineError], operator.add] = Field(default_factory=list)
    node_failures: Annotated[list[NodeFailureDetail], operator.add] = Field(
        default_factory=list
    )
    failed_sections: Annotated[dict[str, FailedSectionRecord], _merge_dicts] = Field(
        default_factory=dict
    )
    diagram_outcomes: Annotated[dict[str, str], _merge_dicts] = Field(
        default_factory=dict
    )
    status: PipelineStatus = PipelineStatus.PENDING

    @classmethod
    def parse(cls, raw: "TextbookPipelineState | dict") -> "TextbookPipelineState":
        if isinstance(raw, cls):
            return raw
        return cls.model_validate(raw)

    @field_validator("rerender_requests", mode="before")
    @classmethod
    def _normalize_rerender_requests(cls, value: Any) -> dict[str, RerenderRequest]:
        if value is None:
            return {}
        if isinstance(value, list):
            normalized: dict[str, RerenderRequest] = {}
            for item in value:
                request = (
                    item
                    if isinstance(item, RerenderRequest)
                    else RerenderRequest.model_validate(item)
                )
                normalized[request.section_id] = request
            return normalized
        if isinstance(value, dict):
            normalized: dict[str, RerenderRequest] = {}
            for section_id, item in value.items():
                if item is None:
                    continue
                request = (
                    item
                    if isinstance(item, RerenderRequest)
                    else RerenderRequest.model_validate(item)
                )
                normalized[str(section_id)] = request
            return normalized
        raise TypeError("rerender_requests must be a dict, list, or None")

    @field_validator("media_slot_results", mode="before")
    @classmethod
    def _normalize_media_slot_results(
        cls,
        value: Any,
    ) -> dict[str, dict[str, VisualSlotResult]]:
        if value is None:
            return {}
        normalized: dict[str, dict[str, VisualSlotResult]] = {}
        for section_id, section_results in dict(value).items():
            normalized[str(section_id)] = {
                str(slot_id): (
                    slot_result
                    if isinstance(slot_result, VisualSlotResult)
                    else VisualSlotResult.model_validate(slot_result)
                )
                for slot_id, slot_result in dict(section_results).items()
            }
        return normalized

    @field_validator("media_frame_results", mode="before")
    @classmethod
    def _normalize_media_frame_results(
        cls,
        value: Any,
    ) -> dict[str, dict[str, dict[str, VisualFrameResult]]]:
        if value is None:
            return {}
        normalized: dict[str, dict[str, dict[str, VisualFrameResult]]] = {}
        for section_id, section_results in dict(value).items():
            normalized_slots: dict[str, dict[str, VisualFrameResult]] = {}
            for slot_id, slot_results in dict(section_results).items():
                normalized_slots[str(slot_id)] = {
                    str(frame_key): (
                        frame_result
                        if isinstance(frame_result, VisualFrameResult)
                        else VisualFrameResult.model_validate(frame_result)
                    )
                    for frame_key, frame_result in dict(slot_results).items()
                }
            normalized[str(section_id)] = normalized_slots
        return normalized

    @field_validator("media_frame_retry_count", mode="before")
    @classmethod
    def _normalize_media_frame_retry_count(
        cls,
        value: Any,
    ) -> dict[str, dict[str, dict[str, int]]]:
        if value is None:
            return {}
        normalized: dict[str, dict[str, dict[str, int]]] = {}
        for section_id, section_counts in dict(value).items():
            normalized_slots: dict[str, dict[str, int]] = {}
            for slot_id, frame_counts in dict(section_counts).items():
                normalized_slots[str(slot_id)] = {
                    str(frame_key): int(count)
                    for frame_key, count in dict(frame_counts).items()
                }
            normalized[str(section_id)] = normalized_slots
        return normalized

    @field_validator("current_media_retry", mode="before")
    @classmethod
    def _normalize_current_media_retry(
        cls,
        value: Any,
    ) -> MediaFrameRetryRequest | None:
        if value is None:
            return None
        if isinstance(value, MediaFrameRetryRequest):
            return value
        return MediaFrameRetryRequest.model_validate(value)

    def has_errors_for(self, section_id: str) -> bool:
        return any(error.section_id == section_id for error in self.errors)

    def rerender_count_for(self, section_id: str) -> int:
        return self.rerender_count.get(section_id, 0)

    def pending_rerender_for(self, section_id: str | None) -> RerenderRequest | None:
        if section_id is None:
            return None
        return self.rerender_requests.get(section_id)

    def pending_media_retry_for(self, section_id: str | None) -> MediaFrameRetryRequest | None:
        if section_id is None:
            return None
        if self.current_media_retry is None:
            return None
        retry = (
            self.current_media_retry
            if isinstance(self.current_media_retry, MediaFrameRetryRequest)
            else MediaFrameRetryRequest.model_validate(self.current_media_retry)
        )
        if retry.section_id != section_id:
            return None
        return retry

    def can_rerender(self, section_id: str) -> bool:
        return self.rerender_count_for(section_id) < self.max_rerenders

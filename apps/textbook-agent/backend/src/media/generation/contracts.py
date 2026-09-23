"""Visual generation contracts used by Learn and Print.

These types moved out of the retired execution package. The old module
re-exports them so existing tests keep a single class identity.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VisualMode = Literal["diagram", "diagram_series", "diagram_compare", "image", "simulation"]
VisualStyle = Literal["diagram_precision", "illustration"]
_VISUAL_STYLES = {"diagram_precision", "illustration"}
VisualDependency = Literal["blueprint_only", "section_text", "question_text"]


class GeneratedVisualBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visual_id: str
    attaches_to: str
    frame_index: int | None = None
    mode: VisualMode
    image_url: str | None = None
    html_content: str | None = None
    fallback_image_url: str | None = None
    caption: str | None = None
    alt_text: str | None = None
    source_work_order_id: str
    component_id: str | None = None
    parent_visual_id: str | None = None
    status: Literal[
        "ready",
        "ready_with_quality_warning",
        "failed",
        "omitted_quality",
        "flagged_quality",
    ] = "ready"
    error_message: str | None = None
    qc_reasons: list[str] = Field(default_factory=list)
    qc_correction_hint: str | None = None
    qc_trace_id: str | None = None


class ExecutorOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    blocks: list[Any] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    retried: bool = False
    retryable: bool = True


class SourceOfTruthEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    text: str
    unit_tokens: list[str] = Field(default_factory=list)


class VisualFrameSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    must_show: list[str] = Field(default_factory=list)


class VisualPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    attaches_to: str
    component_id: str | None = None
    mode: VisualMode = "diagram"
    visual_style: VisualStyle | None = None
    purpose: str = ""
    must_show: list[str] = Field(default_factory=list)
    must_not_show: list[str] = Field(default_factory=list)
    labels_required: list[str] = Field(default_factory=list)
    uses_anchor_id: str | None = None
    consistency_locks: list[str] = Field(default_factory=list)
    print_requirements: list[str] = Field(default_factory=list)
    frames: list[VisualFrameSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_closed_labels(self) -> VisualPlanItem:
        if self.visual_style != "diagram_precision":
            return self
        labels: list[str] = []
        seen: set[str] = set()
        for raw in self.labels_required:
            label = str(raw).strip()
            folded = label.casefold()
            if label and folded not in seen:
                labels.append(label)
                seen.add(folded)
        self.labels_required = labels
        return self

    @field_validator("visual_style", mode="before")
    @classmethod
    def normalize_visual_style(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value in _VISUAL_STYLES:
            return value
        return None


class VisualGeneratorWorkOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_order_id: str
    resource_type: str = "lesson"
    dependency: VisualDependency = "blueprint_only"
    visual: VisualPlanItem
    source_of_truth: list[SourceOfTruthEntry] = Field(default_factory=list)
    # Latest persisted QC correction to apply on the next attempt. This is
    # prompt metadata only and must never be rendered inside the image.
    qc_correction_hint: str | None = None
    prior_validation_errors: list[str] = Field(default_factory=list)


def _image_url_valid(url: str) -> bool:
    u = url.strip().lower()
    return u.startswith(("http://", "https://"))


def validate_visual_block(
    block: GeneratedVisualBlock,
    work_order: VisualGeneratorWorkOrder,
) -> list[str]:
    errors: list[str] = []
    valid_visual_id = block.visual_id == work_order.visual.id
    if (
        not valid_visual_id
        and block.frame_index is not None
        and work_order.visual.mode == "diagram_series"
    ):
        valid_visual_id = block.visual_id == f"{work_order.visual.id}_frame_{block.frame_index}"
    if not valid_visual_id:
        errors.append("visual_id mismatch")
    if (
        block.status not in {"failed", "omitted_quality"}
        and block.mode in {"diagram", "image", "diagram_series", "diagram_compare"}
    ) and (not block.image_url or not _image_url_valid(block.image_url)):
        errors.append("image_url not a valid hosted URL")
    if block.mode == "simulation" and not block.html_content and not block.fallback_image_url:
        errors.append("simulation requires html_content or fallback_image_url")
    return errors

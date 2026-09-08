"""Typed Learn activity authoring alongside approved-item consumption (P04)."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from curriculum.approved_items import approved_item_kind
from curriculum.teaching_plan.compatibility import (
    ActionSourceIncompatibleError,
    assert_action_compatible_with_sources,
    expected_source_kind_for_action,
)
from learn.generation.work_orders import LearnWorkOrder


class ActivityAuthoringPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    capability_id: str
    mode: Literal["new", "approved_item"]
    action: str | None = None
    evidence_purpose: str = ""
    task_brief: str = ""
    source_item_ids: list[str] = Field(default_factory=list)
    preserved_fields: list[str] = Field(default_factory=list)


def plan_activity_authoring(
    order: LearnWorkOrder,
    *,
    approved_items: Sequence[Any] | Mapping[str, Any] | None = None,
) -> ActivityAuthoringPlan:
    """Bind new-activity authoring or approved consumption; never silent rewrite."""
    if order.lane != "interaction":
        return ActivityAuthoringPlan(
            block_id=order.block_id,
            capability_id=order.capability_id,
            mode="new",
            action=order.action,
            evidence_purpose=order.evidence,
            task_brief=order.brief,
        )

    items_by_id: dict[str, Any]
    if isinstance(approved_items, Mapping):
        items_by_id = {str(k): v for k, v in approved_items.items()}
    else:
        items_by_id = {
            str(getattr(item, "id", "") or ""): item for item in (approved_items or [])
        }

    source_ids = list(order.approved_item_ids or order.source_refs or [])
    if not source_ids:
        return ActivityAuthoringPlan(
            block_id=order.block_id,
            capability_id=order.capability_id,
            mode="new",
            action=order.action,
            evidence_purpose=order.evidence,
            task_brief=order.brief,
        )

    if order.action is None:
        raise ActionSourceIncompatibleError(
            f"block {order.block_id!r} binds approved items without a learner action"
        )

    sources = []
    for item_id in source_ids:
        item = items_by_id.get(item_id)
        if item is None:
            raise ActionSourceIncompatibleError(
                f"approved item {item_id!r} missing for block {order.block_id!r}"
            )
        sources.append(item)

    expected = expected_source_kind_for_action(order.action)
    kinds = [approved_item_kind(item) for item in sources]
    if expected is not None and any(kind != expected for kind in kinds):
        raise ActionSourceIncompatibleError(
            f"approved task type {kinds} is incompatible with action "
            f"{order.action!r} / capability {order.capability_id!r}; "
            f"expected {expected!r}. Do not silently rewrite the assessment."
        )

    assert_action_compatible_with_sources(action=order.action, source_items=sources)
    return ActivityAuthoringPlan(
        block_id=order.block_id,
        capability_id=order.capability_id,
        mode="approved_item",
        action=order.action,
        evidence_purpose=order.evidence,
        task_brief=order.brief,
        source_item_ids=source_ids,
        preserved_fields=["stem", "options", "correct_key", "response_relationships"],
    )


__all__ = [
    "ActivityAuthoringPlan",
    "plan_activity_authoring",
]

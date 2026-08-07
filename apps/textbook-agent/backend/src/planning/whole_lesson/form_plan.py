"""Whole-lesson form plan schema — form-owned decisions only.

Teaching pedagogy (intent, brief, evidence, …) is owned by TeachingPlan.
Code joins the two into ResolvedBlockPlan for writers and assembly.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Placement = Literal["main", "margin"]


class FormDecision(BaseModel):
    """Form-planner owned fields for one teaching block."""

    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    object: str = Field(min_length=1)
    placement: Placement = "main"
    reason: str = ""
    escalation: str | None = None

    @field_validator("escalation", mode="before")
    @classmethod
    def _empty_escalation_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value


class FormPlanSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    forms: list[FormDecision] = Field(default_factory=list)


class FormPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[FormPlanSection] = Field(default_factory=list)

    def decision_map(self) -> dict[str, FormDecision]:
        return {
            decision.block_id: decision
            for section in self.sections
            for decision in section.forms
        }


def iter_form_decisions(
    form_plan: FormPlan | dict[str, Any],
) -> list[tuple[str, str]]:
    """Yield (slot_id, block_id) pairs from a typed or raw form plan."""
    if isinstance(form_plan, FormPlan):
        return [
            (section.slot_id, decision.block_id)
            for section in form_plan.sections
            for decision in section.forms
        ]
    pairs: list[tuple[str, str]] = []
    for section in form_plan.get("sections") or []:
        if not isinstance(section, dict):
            continue
        slot_id = str(section.get("slot_id") or "")
        for decision in section_decisions_raw(section):
            pairs.append((slot_id, str(decision.get("block_id") or "")))
    return pairs


def section_decisions_raw(section: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize section decisions from slim `forms` or legacy `blocks`."""
    if isinstance(section.get("forms"), list):
        return [item for item in section["forms"] if isinstance(item, dict)]
    legacy = section.get("blocks")
    if not isinstance(legacy, list):
        return []
    out: list[dict[str, Any]] = []
    for block in legacy:
        if not isinstance(block, dict):
            continue
        placement = block.get("placement") or "main"
        if placement == "spanning":
            placement = "main"
        out.append(
            {
                "block_id": block.get("block_id") or block.get("id"),
                "object": block.get("object"),
                "placement": placement,
                "reason": block.get("reason") or "",
                "escalation": block.get("escalation"),
            }
        )
    return out


def coerce_form_plan(raw: FormPlan | dict[str, Any] | None) -> FormPlan:
    """Load slim FormPlan; coerce legacy fat blocks → FormDecision."""
    if isinstance(raw, FormPlan):
        return raw
    if not isinstance(raw, dict):
        raise TypeError("form_plan must be a dict or FormPlan")
    sections: list[dict[str, Any]] = []
    for section in raw.get("sections") or []:
        if not isinstance(section, dict):
            continue
        forms = section_decisions_raw(section)
        sections.append(
            {
                "slot_id": section.get("slot_id"),
                "forms": forms,
            }
        )
    return FormPlan.model_validate({"sections": sections})


# Backward-compatible names used by older imports/tests during migration.
FormPlanBlock = FormDecision

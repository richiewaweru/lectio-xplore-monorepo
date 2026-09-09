"""Pinned Unit preparation context for Learn native production (R02/R03)."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field


class LearnPreparationContext(BaseModel):
    """Teaching context carried from shared preparation into Learn authoring."""

    model_config = ConfigDict(extra="forbid")

    objective: str = ""
    allowed_facts: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)
    learner_level: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    dependency_results: list[dict[str, Any]] = Field(default_factory=list)


def _fact_strings(values: Sequence[Any] | None) -> list[str]:
    out: list[str] = []
    for item in values or []:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
        elif isinstance(item, Mapping):
            text = str(item.get("statement") or item.get("text") or item.get("id") or "").strip()
            if text:
                out.append(text)
    return out


def learn_preparation_context_from_state(state: Mapping[str, Any]) -> LearnPreparationContext:
    """Build preparation context from pinned page-generation / shared-prep state."""
    packet = state.get("shared_preparation_packet")
    if not isinstance(packet, Mapping):
        packet = {}

    scope = packet.get("scope_contract")
    if not isinstance(scope, Mapping):
        scope = state.get("scope_contract") if isinstance(state.get("scope_contract"), Mapping) else {}

    teaching = state.get("teaching_plan")
    teaching_arc = ""
    if isinstance(teaching, Mapping):
        teaching_arc = str(teaching.get("arc") or "").strip()

    objective = str(
        packet.get("objective")
        or state.get("objective")
        or teaching_arc
        or packet.get("title")
        or state.get("title")
        or ""
    ).strip()

    prior = _fact_strings(packet.get("prior_established") or state.get("prior_established"))
    must_establish = _fact_strings(packet.get("must_establish") or state.get("must_establish"))
    allowed_facts = list(dict.fromkeys([*prior, *must_establish]))

    terminology = [
        str(term).strip()
        for term in (scope.get("terminology") or [])
        if str(term).strip()
    ]

    groups = packet.get("groups") or state.get("groups") or []
    learner_level: str | None = None
    if isinstance(groups, list) and groups:
        first = groups[0]
        if isinstance(first, Mapping):
            profile = str(first.get("profile") or "").strip()
            learner_level = profile or None

    constraints: dict[str, Any] = {}
    for key in ("exclusions", "external_prerequisites", "must_not_introduce"):
        value = packet.get(key) if key in packet else state.get(key)
        if value:
            constraints[key] = value
    secondary = packet.get("secondary_demand") or state.get("secondary_demand")
    if secondary:
        constraints["secondary_demand"] = secondary

    dependency_results: list[dict[str, Any]] = []
    for bucket in ("prerequisites", "lesson_actuals"):
        raw = packet.get(bucket) or state.get(bucket) or []
        if isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, Mapping):
                    dependency_results.append(dict(entry))

    return LearnPreparationContext(
        objective=objective,
        allowed_facts=allowed_facts,
        terminology=terminology,
        learner_level=learner_level,
        constraints=constraints,
        dependency_results=dependency_results,
    )


def lesson_context_from_preparation(
    preparation: LearnPreparationContext | None,
    *,
    title: str | None = None,
    subject: str = "science",
) -> dict[str, Any]:
    """Merge preparation fields into the engine lesson_context input."""
    ctx: dict[str, Any] = {
        "title": title or "Learn lesson",
        "subject": subject,
    }
    if preparation is None:
        return ctx
    if preparation.objective:
        ctx["objective"] = preparation.objective
    if preparation.learner_level:
        ctx["learner_level"] = preparation.learner_level
    if preparation.constraints:
        ctx["constraints"] = dict(preparation.constraints)
    if preparation.dependency_results:
        ctx["dependency_results"] = list(preparation.dependency_results)
    return ctx


__all__ = [
    "LearnPreparationContext",
    "learn_preparation_context_from_state",
    "lesson_context_from_preparation",
]

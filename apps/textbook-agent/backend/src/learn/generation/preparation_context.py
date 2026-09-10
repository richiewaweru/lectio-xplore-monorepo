"""Pinned Unit preparation context for Learn native production (R02/R03 + policy-v4)."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

InputAvailability = Literal[
    "supplied_statements",
    "intentionally_absent",
    "unresolved_references",
    "retrieval_failure",
    "legacy_unknown",
]


class LearnPreparationContext(BaseModel):
    """Teaching context carried from shared preparation into Learn authoring."""

    model_config = ConfigDict(extra="forbid")

    objective: str = ""
    allowed_facts: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)
    learner_level: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    dependency_results: list[dict[str, Any]] = Field(default_factory=list)
    input_availability: InputAvailability = "intentionally_absent"
    referenced_fact_ids: list[str] = Field(default_factory=list)
    unresolved_fact_ids: list[str] = Field(default_factory=list)
    input_revision: str | None = None
    retrieval_failed: bool = False
    legacy_absent: bool = False


def _statement_from_mapping(item: Mapping[str, Any]) -> str | None:
    """Extract a factual statement; never treat bare ids/titles as facts."""
    for key in ("statement", "text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _fact_strings(values: Any) -> tuple[list[str], list[str], list[str]]:
    """Return (statements, referenced_ids, unresolved_ids)."""
    statements: list[str] = []
    referenced: list[str] = []
    unresolved: list[str] = []
    if values is None or isinstance(values, (bool, int, float)):
        return statements, referenced, unresolved
    if isinstance(values, str):
        text = values.strip()
        if text:
            statements.append(text)
        return statements, referenced, unresolved
    if not isinstance(values, Sequence):
        return statements, referenced, unresolved
    for item in values:
        if isinstance(item, str):
            text = item.strip()
            if text:
                statements.append(text)
        elif isinstance(item, Mapping):
            fact_id = str(item.get("id") or "").strip()
            if fact_id:
                referenced.append(fact_id)
            statement = _statement_from_mapping(item)
            if statement:
                statements.append(statement)
            elif fact_id:
                unresolved.append(fact_id)
    return statements, referenced, unresolved


def learn_preparation_context_from_state(state: Mapping[str, Any]) -> LearnPreparationContext:
    """Build preparation context from pinned page-generation / shared-prep state."""
    if state.get("preparation_load_failed") or state.get("retrieval_failed"):
        return LearnPreparationContext(
            objective="",
            input_availability="retrieval_failure",
            retrieval_failed=True,
        )

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

    # Objective may fall back to arc/title for identity, but never enters allowed_facts.
    objective = str(
        packet.get("objective")
        or state.get("objective")
        or teaching_arc
        or packet.get("title")
        or state.get("title")
        or ""
    ).strip()

    referenced: list[str] = []
    unresolved: list[str] = []
    prior, ref_a, un_a = _fact_strings(packet.get("prior_established") or state.get("prior_established"))
    must_establish, ref_b, un_b = _fact_strings(packet.get("must_establish") or state.get("must_establish"))
    scope_must, ref_c, un_c = _fact_strings(scope.get("must_establish") if isinstance(scope, Mapping) else None)
    referenced.extend([*ref_a, *ref_b, *ref_c])
    unresolved.extend([*un_a, *un_b, *un_c])

    lesson_actuals = packet.get("lesson_actuals") or state.get("lesson_actuals") or []
    actual_facts: list[str] = []
    if isinstance(lesson_actuals, list):
        for entry in lesson_actuals:
            if not isinstance(entry, Mapping):
                continue
            fact_bucket = entry.get("must_establish")
            if fact_bucket is None:
                fact_bucket = entry.get("facts")
            if fact_bucket is None and isinstance(entry.get("established"), (list, tuple, str)):
                fact_bucket = entry.get("established")
            if fact_bucket is None and entry.get("statement"):
                fact_bucket = [entry.get("statement")]
            stmts, refs, uns = _fact_strings(fact_bucket)
            actual_facts.extend(stmts)
            referenced.extend(refs)
            unresolved.extend(uns)

    allowed_facts = list(dict.fromkeys([*prior, *must_establish, *scope_must, *actual_facts]))
    referenced = list(dict.fromkeys(referenced))
    unresolved = list(dict.fromkeys(unresolved))

    # Explicit references that cannot resolve are errors upstream; record them here.
    # Do NOT substitute objective/title/arc as facts.

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

    input_revision = None
    for key in ("preparation_revision", "shared_preparation_revision", "input_revision"):
        value = packet.get(key) or state.get(key)
        if value is not None and str(value).strip():
            input_revision = str(value).strip()
            break

    legacy_absent = bool(state.get("legacy_absent_policy"))
    if unresolved:
        availability: InputAvailability = "unresolved_references"
    elif allowed_facts:
        availability = "supplied_statements"
    elif legacy_absent:
        availability = "legacy_unknown"
    else:
        availability = "intentionally_absent"

    return LearnPreparationContext(
        objective=objective,
        allowed_facts=allowed_facts,
        terminology=terminology,
        learner_level=learner_level,
        constraints=constraints,
        dependency_results=dependency_results,
        input_availability=availability,
        referenced_fact_ids=referenced,
        unresolved_fact_ids=unresolved,
        input_revision=input_revision,
        retrieval_failed=False,
        legacy_absent=legacy_absent,
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
    ctx["input_availability"] = preparation.input_availability
    if preparation.input_revision:
        ctx["input_revision"] = preparation.input_revision
    if preparation.referenced_fact_ids:
        ctx["referenced_fact_ids"] = list(preparation.referenced_fact_ids)
    if preparation.unresolved_fact_ids:
        ctx["unresolved_fact_ids"] = list(preparation.unresolved_fact_ids)
    return ctx


def packet_fact_statements(packet: Any) -> list[str]:
    """Extract factual statements from an ImmutableLessonPacket-like object."""
    statements: list[str] = []
    scope = getattr(packet, "scope", None)
    if scope is not None:
        for entry in getattr(scope, "must_establish", None) or []:
            text = getattr(entry, "statement", None)
            if isinstance(text, str) and text.strip():
                statements.append(text.strip())
            elif isinstance(entry, Mapping):
                stmt = _statement_from_mapping(entry)
                if stmt:
                    statements.append(stmt)
    for entry in getattr(packet, "prior_established", None) or []:
        text = getattr(entry, "statement", None)
        if isinstance(text, str) and text.strip():
            statements.append(text.strip())
        elif isinstance(entry, Mapping):
            stmt = _statement_from_mapping(entry)
            if stmt:
                statements.append(stmt)
    return list(dict.fromkeys(statements))


__all__ = [
    "InputAvailability",
    "LearnPreparationContext",
    "learn_preparation_context_from_state",
    "lesson_context_from_preparation",
    "packet_fact_statements",
]

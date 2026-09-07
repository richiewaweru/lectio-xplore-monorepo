"""Strict, non-renderable topology contract for native visual figures.

The topology planner is deliberately only allowed to choose relationships between
persisted identifiers.  Labels, prose, and other renderable strings belong to the
persisted visual source and never cross this contract.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class TopologyValidationError(ValueError):
    """A topology output cannot be safely rendered."""

    code = "TOPOLOGY_INVALID"

    def __init__(self, message: str, *, issues: list[str] | None = None) -> None:
        self.issues = issues or [message]
        super().__init__(f"{message}: {'; '.join(self.issues)}")


class TopologyCueV1(StrEnum):
    ARROW = "arrow"
    ARROWHEADS = "arrowheads"
    CYCLE = "cycle"
    FLOW = "flow"
    COMPARE = "compare"
    HIGHLIGHT = "highlight"
    EMPHASIS = "emphasis"
    PART = "part"
    CENTER = "center"
    DASHED = "dashed"
    SOLID = "solid"
    NONE = "none"


class TopologyNodeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^n[0-9]+$")
    label_id: str | None = Field(default=None, pattern=r"^l[0-9]+$")
    evidence_keys: list[str] = Field(default_factory=list)

    @field_validator("evidence_keys")
    @classmethod
    def _keys_are_identifiers(cls, value: list[str]) -> list[str]:
        if any(not isinstance(key, str) or not key.strip() for key in value):
            raise ValueError("evidence_keys must contain non-empty identifiers")
        if len(set(value)) != len(value):
            raise ValueError("evidence_keys must not contain duplicates")
        return value


class TopologyEdgeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(pattern=r"^e[0-9]+$")
    from_ref: str = Field(
        validation_alias=AliasChoices("from_ref", "source", "from"),
        pattern=r"^n[0-9]+$",
    )
    to_ref: str = Field(
        validation_alias=AliasChoices("to_ref", "target", "to"),
        pattern=r"^n[0-9]+$",
    )
    direction: Literal["forward", "backward", "reverse", "bidirectional"]
    evidence_keys: list[str] = Field(default_factory=list)

    @field_validator("evidence_keys")
    @classmethod
    def _keys_are_identifiers(cls, value: list[str]) -> list[str]:
        if any(not isinstance(key, str) or not key.strip() for key in value):
            raise ValueError("evidence_keys must contain non-empty identifiers")
        if len(set(value)) != len(value):
            raise ValueError("evidence_keys must not contain duplicates")
        return value


class TopologyLabelV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(pattern=r"^l[0-9]+$")
    placement: Literal["node", "edge", "center"]
    ref: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ref", "target_ref", "target", "node_id", "edge_id"
        ),
    )

    @model_validator(mode="after")
    def _placement_ref(self) -> "TopologyLabelV1":
        if self.placement == "center" and self.ref is not None:
            raise ValueError("center labels cannot reference a node or edge")
        if self.placement != "center" and not self.ref:
            raise ValueError(f"{self.placement} labels require ref")
        if self.placement == "node" and not self.ref.startswith("n"):
            raise ValueError("node labels must reference a node")
        if self.placement == "edge" and not self.ref.startswith("e"):
            raise ValueError("edge labels must reference an edge")
        return self


class TopologyPlanV1(BaseModel):
    """The complete topology decision; it contains no renderable free text."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    layout: Literal["cycle", "flow", "comparison", "parts"]
    nodes: list[TopologyNodeV1] = Field(min_length=1)
    edges: list[TopologyEdgeV1] = Field(default_factory=list)
    labels: list[TopologyLabelV1] = Field(default_factory=list)
    cues: list[TopologyCueV1] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)

    @field_validator("cues", "exclusions")
    @classmethod
    def _unique_closed_values(cls, value: list[Any]) -> list[Any]:
        if len(value) != len(set(value)):
            raise ValueError("cues and exclusions must not contain duplicates")
        return value


def _source_ids(source: Any, *keys: str) -> set[str]:
    if not isinstance(source, dict):
        return set()
    for key in keys:
        value = source.get(key)
        if isinstance(value, dict):
            return {str(item) for item in value}
        if isinstance(value, (list, tuple, set, frozenset)):
            out: set[str] = set()
            for item in value:
                if isinstance(item, dict):
                    item_id = item.get("id") or item.get("key")
                    if item_id is not None:
                        out.add(str(item_id))
                elif item is not None:
                    out.add(str(item))
            return out
    return set()


def _reachable(plan: TopologyPlanV1) -> bool:
    if len(plan.nodes) <= 1:
        return True
    neighbors: dict[str, set[str]] = defaultdict(set)
    for edge in plan.edges:
        neighbors[edge.from_ref].add(edge.to_ref)
        neighbors[edge.to_ref].add(edge.from_ref)
    seen = {plan.nodes[0].id}
    queue = deque(seen)
    while queue:
        node = queue.popleft()
        for neighbor in neighbors[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return len(seen) == len(plan.nodes)


def _directed_cycle(plan: TopologyPlanV1) -> bool:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in plan.edges:
        if edge.direction == "forward":
            adjacency[edge.from_ref].add(edge.to_ref)
        elif edge.direction in {"reverse", "backward"}:
            adjacency[edge.to_ref].add(edge.from_ref)
        else:
            # A bidirectional relation is intentionally cyclic for a flow.
            adjacency[edge.from_ref].add(edge.to_ref)
            adjacency[edge.to_ref].add(edge.from_ref)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in adjacency[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node.id) for node in plan.nodes)


def validate_topology_plan(
    raw: TopologyPlanV1 | dict[str, Any],
    *,
    source: dict[str, Any] | None = None,
    label_ids: set[str] | None = None,
    evidence_keys: set[str] | None = None,
    cue_ids: set[str] | None = None,
    exclusion_keys: set[str] | None = None,
) -> TopologyPlanV1:
    """Validate structural safety and references, failing closed on any mismatch."""

    try:
        plan = raw if isinstance(raw, TopologyPlanV1) else TopologyPlanV1.model_validate(raw)
    except ValidationError as exc:
        detail = str(exc)
        hint = " cues" if "cues" in detail else ""
        raise TopologyValidationError(f"invalid topology schema{hint}", issues=[detail]) from exc

    source = source or {}
    expected_labels = label_ids or _source_ids(source, "label_ids", "labels", "label_map")
    allowed_evidence = evidence_keys or _source_ids(source, "evidence_keys", "evidence", "source_keys")
    allowed_cues = cue_ids or _source_ids(source, "cue_ids", "cues", "allowed_cues")
    allowed_exclusions = exclusion_keys or _source_ids(
        source, "exclusion_keys", "exclusions", "must_not_introduce"
    )

    issues: list[str] = []
    node_ids = [node.id for node in plan.nodes]
    edge_ids = [edge.id for edge in plan.edges]
    label_ids_out = [label.id for label in plan.labels]
    for kind, values in (("node", node_ids), ("edge", edge_ids), ("label", label_ids_out)):
        duplicates = [item for item, count in Counter(values).items() if count > 1]
        if duplicates:
            issues.append(f"duplicate {kind} IDs: {sorted(duplicates)}")
    node_set = set(node_ids)
    edge_set = set(edge_ids)
    if expected_labels:
        unknown = sorted(set(label_ids_out) - expected_labels)
        missing = sorted(expected_labels - set(label_ids_out))
        if unknown:
            issues.append(f"unknown label IDs: {unknown}")
        if missing:
            issues.append(f"missing label IDs: {missing}")
        if len(label_ids_out) != len(expected_labels):
            issues.append("each source label ID must occur exactly once")

    seen_edges: set[tuple[str, str]] = set()
    for edge in plan.edges:
        if edge.from_ref not in node_set or edge.to_ref not in node_set:
            issues.append(f"edge {edge.id} references an unknown node")
        if edge.from_ref == edge.to_ref:
            issues.append(f"edge {edge.id} is a self-edge")
        pair = tuple(sorted((edge.from_ref, edge.to_ref)))
        if pair in seen_edges:
            issues.append(f"duplicate edge between {pair[0]} and {pair[1]}")
        seen_edges.add(pair)
        if allowed_evidence:
            unknown = sorted(set(edge.evidence_keys) - allowed_evidence)
            if unknown:
                issues.append(f"edge {edge.id} has unknown evidence keys: {unknown}")
    for node in plan.nodes:
        if node.label_id and node.label_id not in set(label_ids_out):
            issues.append(f"node {node.id} references unknown label {node.label_id}")
        if allowed_evidence:
            unknown = sorted(set(node.evidence_keys) - allowed_evidence)
            if unknown:
                issues.append(f"node {node.id} has unknown evidence keys: {unknown}")
    for label in plan.labels:
        if label.placement == "node" and label.ref not in node_set:
            issues.append(f"label {label.id} references unknown node")
        if label.placement == "edge" and label.ref not in edge_set:
            issues.append(f"label {label.id} references unknown edge")
    if allowed_cues:
        unknown = sorted(set(str(cue) for cue in plan.cues) - allowed_cues)
        if unknown:
            issues.append(f"cues outside persisted allowlist: {unknown}")
    if allowed_exclusions:
        unknown = sorted(set(plan.exclusions) - allowed_exclusions)
        if unknown:
            issues.append(f"exclusions outside persisted allowlist: {unknown}")
    elif plan.exclusions:
        issues.append("exclusions require a persisted exclusion allowlist")

    if not _reachable(plan):
        issues.append("layout graph is disconnected")
    if plan.layout == "cycle":
        degrees = Counter()
        for edge in plan.edges:
            degrees[edge.from_ref] += 1
            degrees[edge.to_ref] += 1
        if len(plan.nodes) < 2 or len(plan.edges) != len(plan.nodes) or any(
            degrees[node.id] != 2 for node in plan.nodes
        ):
            issues.append("cycle layout must be one closed cycle")
    elif plan.layout == "flow":
        if len(plan.edges) < len(plan.nodes) - 1 or _directed_cycle(plan):
            issues.append("flow layout must be a connected directed acyclic graph")
    elif plan.layout == "comparison" and len(plan.nodes) < 2:
        issues.append("comparison layout requires at least two nodes")
    elif plan.layout == "parts" and len(plan.nodes) < 2:
        issues.append("parts layout requires at least two nodes")

    if issues:
        raise TopologyValidationError("topology validation failed", issues=issues)
    return plan


__all__ = [
    "TopologyCueV1",
    "TopologyEdgeV1",
    "TopologyLabelV1",
    "TopologyNodeV1",
    "TopologyPlanV1",
    "TopologyValidationError",
    "validate_topology_plan",
]

"""Build section writer sources from verified semantic WorkItem outputs.

This adapter is deliberately small and pure.  It does not ask a provider to
fill gaps or turn approved plan references into facts.  The approved plan
selects the sourcebook entries for a section; the durable semantic-input
loader supplies the exact entries that may be rendered into writer context.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from pydantic_core import PydanticSerializationError

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.runtime import SectionRuntimeError, verify_teaching_plan_source
from document.shared_lesson.semantic_inputs import VerifiedSemanticInputs
from document.shared_lesson.writer import SectionSource
from infra.execution.checkpoints import content_hash


class SectionSourceError(ValueError):
    """A section source cannot be trusted as an approved semantic input."""


def _canonical_json(value: Any, *, path: str = "content") -> str:
    """Return strict, UTF-8-safe canonical JSON for approved entry content."""

    def validate(node: Any, node_path: str) -> Any:
        if node is None or isinstance(node, (str, bool, int)):
            return node
        if isinstance(node, float):
            if not math.isfinite(node):
                raise SectionSourceError(f"sourcebook {node_path} contains a non-finite number")
            return node
        if isinstance(node, Mapping):
            normalized: dict[str, Any] = {}
            for key, child in node.items():
                if not isinstance(key, str):
                    raise SectionSourceError(
                        f"sourcebook {node_path} contains a non-string object key"
                    )
                normalized[key] = validate(child, f"{node_path}.{key}")
            return normalized
        if isinstance(node, list):
            return [validate(child, f"{node_path}[{index}]") for index, child in enumerate(node)]
        raise SectionSourceError(
            f"sourcebook {node_path} contains a non-JSON value {type(node).__name__}"
        )

    try:
        normalized = validate(value, path)
        return json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SectionSourceError):
            raise
        raise SectionSourceError("sourcebook content is not valid JSON") from exc


def _verify_semantic_source(inputs: VerifiedSemanticInputs) -> None:
    try:
        identity = verify_teaching_plan_source(inputs.source)
    except SectionRuntimeError as exc:
        raise SectionSourceError(
            "verified semantic inputs have an invalid approved source"
        ) from exc

    source_identity = (
        identity.source_artifact_id,
        identity.source_revision,
        identity.source_hash,
    )
    if (
        inputs.sourcebook.teaching_plan_id,
        inputs.sourcebook.teaching_plan_revision,
        inputs.sourcebook.teaching_plan_hash,
    ) != source_identity:
        raise SectionSourceError("sourcebook is stale for the approved Teaching Plan source")

    # The loader records the hash of the accepted durable output.  Recompute it
    # here so a caller cannot mutate a nested sourcebook after verification.
    try:
        sourcebook_payload = inputs.sourcebook.model_dump(mode="json")
    except PydanticSerializationError as exc:
        raise SectionSourceError("sourcebook contains non-JSON content") from exc
    observed_output_hash = content_hash(sourcebook_payload)
    if observed_output_hash != inputs.sourcebook_output_hash:
        raise SectionSourceError("verified sourcebook output hash does not match its content")


def _approved_section(
    inputs: VerifiedSemanticInputs, section: TeachingPlanSection
) -> TeachingPlanSection:
    if not isinstance(section, TeachingPlanSection):
        raise SectionSourceError("section source input must be a TeachingPlanSection")
    approved = tuple(
        candidate
        for candidate in inputs.source.plan.sections
        if candidate.slot_id == section.slot_id
    )
    if len(approved) != 1:
        raise SectionSourceError(
            f"section {section.slot_id!r} is not uniquely present in the approved Teaching Plan"
        )
    if approved[0].model_dump(mode="json") != section.model_dump(mode="json"):
        raise SectionSourceError(
            f"section {section.slot_id!r} differs from its approved Teaching Plan snapshot"
        )
    return approved[0]


def _entry_index(inputs: VerifiedSemanticInputs) -> dict[str, Any]:
    entries = tuple(inputs.sourcebook.entries)
    index: dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry.id, str) or not entry.id.strip():
            raise SectionSourceError("sourcebook entry IDs must be non-empty")
        if entry.id in index:
            raise SectionSourceError(f"sourcebook entry ID {entry.id!r} is duplicated")
        if not isinstance(entry.content, dict) or not entry.content:
            raise SectionSourceError(f"sourcebook entry {entry.id!r} has empty content")
        _canonical_json(entry.content, path=f"entry[{entry.id!r}].content")
        index[entry.id] = entry
    return index


def build_section_sources(
    inputs: VerifiedSemanticInputs,
    section: TeachingPlanSection,
) -> tuple[SectionSource, ...]:
    """Build ordered, deduplicated writer sources for one approved section.

    Repeated references inside a section emit one source in first-use order.
    The same sourcebook entry may still be emitted when this function is called
    for another approved section.
    """

    if not isinstance(inputs, VerifiedSemanticInputs):
        raise SectionSourceError("section sources require VerifiedSemanticInputs")
    _verify_semantic_source(inputs)
    approved_section = _approved_section(inputs, section)
    entries = _entry_index(inputs)

    sources: list[SectionSource] = []
    seen_refs: set[str] = set()
    for block in approved_section.blocks:
        for ref in block.sourcebook_refs:
            if not isinstance(ref, str) or not ref.strip():
                raise SectionSourceError(
                    f"section {approved_section.slot_id!r} contains an empty sourcebook reference"
                )
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            entry = entries.get(ref)
            if entry is None:
                raise SectionSourceError(
                    f"section {approved_section.slot_id!r} references missing sourcebook entry {ref!r}"
                )
            payload = {
                "type": entry.type,
                "purpose": entry.purpose,
                "content": json.loads(
                    _canonical_json(entry.content, path=f"entry[{entry.id!r}].content")
                ),
                "provenance_refs": list(entry.provenance_refs),
            }
            sources.append(
                SectionSource(
                    id=entry.id,
                    kind="sourcebook_entry",
                    text=_canonical_json(payload, path=f"entry[{entry.id!r}]"),
                )
            )
    return tuple(sources)


def section_sources_for_section(
    inputs: VerifiedSemanticInputs,
    section: TeachingPlanSection,
) -> tuple[SectionSource, ...]:
    """Named integration alias for callers assembling a writer request."""

    return build_section_sources(inputs, section)


__all__ = ["SectionSourceError", "build_section_sources", "section_sources_for_section"]

"""Section-early figure media contracts for SharedLessonDocument generation."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from document.shared_lesson.continuity import (
    ExpectedNodeShape,
    validate_section_continuity,
)
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import FigureNode, SharedLessonDocument, SharedSection
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from infra.generation_runtime.contracts import SourceIdentity
from media.generation.contracts import (
    GeneratedVisualBlock,
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
    validate_visual_block,
)


class SharedFigureMediaError(ValueError):
    """A figure cannot be safely bound to a media result."""


class SharedFigureWorkOrder(BaseModel):
    """Frozen section output and approved plan identity for one figure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_plan_id: str = Field(min_length=1)
    source_plan_revision: int = Field(ge=1)
    source_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_id: str = Field(min_length=1)
    section_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    figure_node_id: str = Field(min_length=1)
    figure_semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    required: bool = True
    work_order: VisualGeneratorWorkOrder


class ReadyFigureMediaResult(BaseModel):
    """A ready provider result still bound only to the accepted section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_plan_id: str = Field(min_length=1)
    source_plan_revision: int = Field(ge=1)
    source_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_id: str = Field(min_length=1)
    section_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    figure_node_id: str = Field(min_length=1)
    figure_semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    work_order_id: str = Field(min_length=1)
    visual_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_url: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    required: bool = True
    source_facts: tuple[SourceOfTruthEntry, ...] = ()
    status: str = "ready"


class FigureMediaResult(BaseModel):
    """A ready media result bound to one immutable assembled document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_plan_id: str = Field(min_length=1)
    source_plan_revision: int = Field(ge=1)
    source_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_document_id: str = Field(min_length=1)
    source_document_revision: int = Field(ge=1)
    source_document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_id: str = Field(min_length=1)
    section_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    figure_node_id: str = Field(min_length=1)
    figure_semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    work_order_id: str = Field(min_length=1)
    visual_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_url: str = Field(min_length=1)
    required: bool = True
    status: str = "ready"


class FigureMediaFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    figure_node_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    required: bool = True
    error_code: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class FigureMediaBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ready: bool
    results: tuple[ReadyFigureMediaResult, ...] = ()
    failures: tuple[FigureMediaFailure, ...] = ()


class FigureExecutor(Protocol):
    async def execute_figure(
        self, order: VisualGeneratorWorkOrder
    ) -> Sequence[GeneratedVisualBlock]:
        """Execute one work order through the existing media abstraction."""


def _hash_payload(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _verify_document(document: SharedLessonDocument) -> None:
    actual = shared_lesson_content_hash(document)
    if actual != document.content_hash:
        raise SharedFigureMediaError("SharedLessonDocument content_hash is stale or conflicting")


def _verify_source(source: TeachingPlanSource) -> SourceIdentity:
    try:
        return verify_teaching_plan_source(source)
    except Exception as exc:
        raise SharedFigureMediaError(f"approved Teaching Plan source is invalid: {exc}") from exc


def _fact_entries(
    approved_source_facts: Mapping[str, str] | Sequence[str],
) -> tuple[SourceOfTruthEntry, ...]:
    if isinstance(approved_source_facts, Mapping):
        raw_entries = sorted(approved_source_facts.items(), key=lambda item: str(item[0]))
        if any(not str(key).strip() for key, _ in raw_entries):
            raise SharedFigureMediaError("approved source fact keys must be meaningful")
        entries = [SourceOfTruthEntry(key=str(key), text=str(value)) for key, value in raw_entries]
    else:
        entries = [
            SourceOfTruthEntry(key=f"fact-{index}", text=str(value))
            for index, value in enumerate(approved_source_facts)
        ]
    if any(not entry.text.strip() for entry in entries):
        raise SharedFigureMediaError("approved source facts must be meaningful")
    if len({entry.key for entry in entries}) != len(entries):
        raise SharedFigureMediaError("approved source fact keys must be unique")
    return tuple(entries)


def _planned_section(
    source: TeachingPlanSource, section: SharedSection
) -> tuple[SourceIdentity, Any]:
    identity = _verify_source(source)
    planned = next((item for item in source.plan.sections if item.slot_id == section.id), None)
    if planned is None:
        raise SharedFigureMediaError(f"section {section.id!r} is not in the approved Teaching Plan")
    expected_position = source.plan.sections.index(planned)
    if section.position != expected_position:
        raise SharedFigureMediaError(
            f"section {section.id!r} position {section.position} does not match approved order"
        )
    if planned.display_title and section.title != planned.display_title:
        raise SharedFigureMediaError(
            f"section {section.id!r} title does not match the approved Teaching Plan"
        )
    return identity, planned


def _validate_section(
    *,
    source: TeachingPlanSource,
    section: SharedSection,
    expected_shape: Sequence[ExpectedNodeShape | Mapping[str, Any] | Any],
    approved_source_ids: Sequence[str],
    source_facts: Sequence[str],
) -> SourceIdentity:
    identity, planned = _planned_section(source, section)
    if not expected_shape:
        raise SharedFigureMediaError("accepted section requires a code-owned expected shape")
    issues = validate_section_continuity(
        section=section,
        teaching_plan_section=planned,
        expected_nodes=expected_shape,
        approved_source_ids=approved_source_ids,
        source_facts=source_facts,
    )
    if issues:
        raise SharedFigureMediaError(
            "accepted section failed deterministic validation: "
            + ", ".join(issue.issue_code for issue in issues)
        )
    return identity


def _figure_semantic_hash(
    *,
    source_plan_id: str,
    source_plan_revision: int,
    source_plan_hash: str,
    section_output_hash: str,
    section_id: str,
    figure_node_id: str,
    node: FigureNode,
    facts: Sequence[SourceOfTruthEntry],
    mode: str,
    required: bool,
) -> str:
    return _hash_payload(
        {
            "source_plan_id": source_plan_id,
            "source_plan_revision": source_plan_revision,
            "source_plan_hash": source_plan_hash,
            "section_output_hash": section_output_hash,
            "section_id": section_id,
            "figure_node_id": figure_node_id,
            "caption": node.display.caption,
            "alt_text": node.accessibility.alt_text,
            "source_facts": [fact.model_dump(mode="json") for fact in facts],
            "mode": mode,
            "required": required,
        }
    )


def build_figure_work_order(
    source: TeachingPlanSource,
    section: SharedSection,
    *,
    figure_node_id: str,
    expected_shape: Sequence[ExpectedNodeShape | Mapping[str, Any] | Any],
    approved_source_facts: Mapping[str, str] | Sequence[str] = (),
    approved_source_ids: Sequence[str] = (),
    required: bool = True,
    mode: str = "diagram",
) -> SharedFigureWorkOrder:
    """Freeze one validated accepted section into an early media work order."""
    facts = _fact_entries(approved_source_facts)
    identity = _validate_section(
        source=source,
        section=section,
        expected_shape=expected_shape,
        approved_source_ids=approved_source_ids,
        source_facts=tuple(fact.text for fact in facts),
    )
    node = next((item for item in section.nodes if item.id == figure_node_id), None)
    if not isinstance(node, FigureNode):
        raise SharedFigureMediaError(
            f"{figure_node_id!r} is not a FigureNode in section {section.id!r}"
        )
    if not node.accessibility.alt_text.strip():
        raise SharedFigureMediaError(f"figure {figure_node_id!r} requires meaningful alt text")
    if node.display.asset_id:
        raise SharedFigureMediaError(
            f"figure {figure_node_id!r} already has a bound asset; create a new revision to regenerate"
        )
    section_output_hash = _hash_payload(section.model_dump(mode="json"))
    semantic_hash = _figure_semantic_hash(
        source_plan_id=identity.source_artifact_id,
        source_plan_revision=identity.source_revision,
        source_plan_hash=identity.source_hash,
        section_output_hash=section_output_hash,
        section_id=section.id,
        figure_node_id=figure_node_id,
        node=node,
        facts=facts,
        mode=mode,
        required=required,
    )
    visual_id = f"shared-figure-{semantic_hash[:24]}"
    work_order_id = f"shared-media-{semantic_hash}"
    visual = VisualPlanItem(
        id=visual_id,
        attaches_to=figure_node_id,
        mode=mode,
        purpose=node.display.caption.strip() or node.accessibility.alt_text.strip(),
        must_show=[node.accessibility.alt_text.strip()],
    )
    order = VisualGeneratorWorkOrder(
        work_order_id=work_order_id,
        resource_type="shared_lesson_figure",
        dependency="section_text",
        visual=visual,
        source_of_truth=list(facts),
    )
    return SharedFigureWorkOrder(
        source_plan_id=identity.source_artifact_id,
        source_plan_revision=identity.source_revision,
        source_plan_hash=identity.source_hash,
        section_id=section.id,
        section_output_hash=section_output_hash,
        figure_node_id=figure_node_id,
        figure_semantic_hash=semantic_hash,
        required=required,
        work_order=order,
    )


def bind_generated_figure(
    work: SharedFigureWorkOrder,
    blocks: Sequence[GeneratedVisualBlock],
) -> ReadyFigureMediaResult:
    """Validate a hosted executor result while retaining section-only identity."""
    if not blocks:
        raise SharedFigureMediaError(f"figure {work.figure_node_id!r} returned no media block")
    block = blocks[0]
    if block.status not in {"ready", "ready_with_quality_warning"}:
        raise SharedFigureMediaError(
            f"figure {work.figure_node_id!r} media status is {block.status!r}"
        )
    errors = validate_visual_block(block, work.work_order)
    if errors:
        raise SharedFigureMediaError(
            f"figure {work.figure_node_id!r} returned invalid hosted media: {'; '.join(errors)}"
        )
    if not block.image_url or not block.image_url.strip():
        raise SharedFigureMediaError(f"figure {work.figure_node_id!r} has no hosted asset URL")
    if block.caption and block.caption != work.work_order.visual.purpose:
        raise SharedFigureMediaError("provider caption cannot replace shared figure semantics")
    if block.alt_text and block.alt_text != work.work_order.visual.must_show[0]:
        raise SharedFigureMediaError("provider alt text cannot replace shared figure semantics")
    return ReadyFigureMediaResult(
        source_plan_id=work.source_plan_id,
        source_plan_revision=work.source_plan_revision,
        source_plan_hash=work.source_plan_hash,
        section_id=work.section_id,
        section_output_hash=work.section_output_hash,
        figure_node_id=work.figure_node_id,
        figure_semantic_hash=work.figure_semantic_hash,
        work_order_id=work.work_order.work_order_id,
        visual_id=block.visual_id,
        asset_id=block.visual_id,
        asset_url=block.image_url,
        mode=work.work_order.visual.mode,
        required=work.required,
        source_facts=tuple(work.work_order.source_of_truth),
        status=block.status,
    )


def bind_figure_media_to_document(
    media: ReadyFigureMediaResult,
    document: SharedLessonDocument,
) -> FigureMediaResult:
    """Bind ready section media only after the assembled document is verified."""
    _verify_document(document)
    if (
        media.source_plan_id != document.teaching_plan_id
        or media.source_plan_revision != document.teaching_plan_revision
        or media.source_plan_hash != document.teaching_plan_hash
    ):
        raise SharedFigureMediaError("media source plan lineage does not match the document")
    section = next((item for item in document.sections if item.id == media.section_id), None)
    if section is None:
        raise SharedFigureMediaError("media section is absent from the assembled document")
    section_hash = _hash_payload(section.model_dump(mode="json"))
    if section_hash != media.section_output_hash:
        raise SharedFigureMediaError("media section output is stale or changed")
    node = next((item for item in section.nodes if item.id == media.figure_node_id), None)
    if not isinstance(node, FigureNode):
        raise SharedFigureMediaError("media figure is absent or has changed kind")
    if node.display.asset_id:
        raise SharedFigureMediaError("assembled figure already has a bound asset")
    semantic_hash = _figure_semantic_hash(
        source_plan_id=media.source_plan_id,
        source_plan_revision=media.source_plan_revision,
        source_plan_hash=media.source_plan_hash,
        section_output_hash=section_hash,
        section_id=section.id,
        figure_node_id=node.id,
        node=node,
        facts=media.source_facts,
        mode=media.mode,
        required=media.required,
    )
    if semantic_hash != media.figure_semantic_hash:
        raise SharedFigureMediaError("media figure semantic identity is stale or changed")
    expected_visual_id = f"shared-figure-{semantic_hash[:24]}"
    expected_work_order_id = f"shared-media-{semantic_hash}"
    if media.visual_id != expected_visual_id or media.work_order_id != expected_work_order_id:
        raise SharedFigureMediaError("media work-order identity is stale or changed")
    if media.asset_id != media.visual_id:
        raise SharedFigureMediaError("media asset identity does not match its visual")
    if media.status not in {"ready", "ready_with_quality_warning"}:
        raise SharedFigureMediaError("media result is not ready")
    if not media.asset_url.lower().startswith(("http://", "https://")):
        raise SharedFigureMediaError("media result is not a valid hosted URL")
    return FigureMediaResult(
        source_plan_id=media.source_plan_id,
        source_plan_revision=media.source_plan_revision,
        source_plan_hash=media.source_plan_hash,
        source_document_id=document.id,
        source_document_revision=document.revision,
        source_document_hash=document.content_hash,
        section_id=media.section_id,
        section_output_hash=media.section_output_hash,
        figure_node_id=media.figure_node_id,
        figure_semantic_hash=media.figure_semantic_hash,
        work_order_id=media.work_order_id,
        visual_id=media.visual_id,
        asset_id=media.asset_id,
        asset_url=media.asset_url,
        required=media.required,
        status=media.status,
    )


async def execute_figure_work_order(
    work: SharedFigureWorkOrder,
    *,
    executor: FigureExecutor,
) -> ReadyFigureMediaResult:
    try:
        blocks = await executor.execute_figure(work.work_order)
        return bind_generated_figure(work, blocks)
    except SharedFigureMediaError:
        raise
    except Exception as exc:
        raise SharedFigureMediaError(
            f"figure {work.figure_node_id!r} media executor failed: {type(exc).__name__}: {exc}"
        ) from exc


async def execute_figure_work_orders(
    works: Sequence[SharedFigureWorkOrder],
    *,
    executor: FigureExecutor,
    concurrency: int = 4,
) -> FigureMediaBatchResult:
    """Run independent figures concurrently and retain healthy siblings."""
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(work: SharedFigureWorkOrder) -> ReadyFigureMediaResult | FigureMediaFailure:
        async with semaphore:
            try:
                return await execute_figure_work_order(work, executor=executor)
            except SharedFigureMediaError as exc:
                return FigureMediaFailure(
                    figure_node_id=work.figure_node_id,
                    section_id=work.section_id,
                    required=work.required,
                    error_code="MEDIA_INVALID",
                    explanation=str(exc),
                )

    outcomes = await asyncio.gather(*(run_one(work) for work in works))
    results = tuple(item for item in outcomes if isinstance(item, ReadyFigureMediaResult))
    failures = tuple(item for item in outcomes if isinstance(item, FigureMediaFailure))
    return FigureMediaBatchResult(
        ready=not any(item.required for item in failures),
        results=results,
        failures=failures,
    )


def validate_reusable_figure_asset(
    work: SharedFigureWorkOrder,
    result: ReadyFigureMediaResult,
) -> None:
    """Reject section media reuse when any frozen identity is stale."""
    if (
        result.source_plan_id != work.source_plan_id
        or result.source_plan_revision != work.source_plan_revision
        or result.source_plan_hash != work.source_plan_hash
        or result.section_id != work.section_id
        or result.section_output_hash != work.section_output_hash
        or result.figure_node_id != work.figure_node_id
        or result.figure_semantic_hash != work.figure_semantic_hash
        or result.work_order_id != work.work_order.work_order_id
        or result.visual_id != work.work_order.visual.id
        or result.required != work.required
        or result.mode != work.work_order.visual.mode
    ):
        raise SharedFigureMediaError("stale or conflicting figure media binding")
    if not result.asset_url.lower().startswith(("http://", "https://")):
        raise SharedFigureMediaError("reusable figure asset is not a valid hosted URL")


__all__ = [
    "FigureExecutor",
    "FigureMediaBatchResult",
    "FigureMediaFailure",
    "FigureMediaResult",
    "ReadyFigureMediaResult",
    "SharedFigureMediaError",
    "SharedFigureWorkOrder",
    "bind_figure_media_to_document",
    "bind_generated_figure",
    "build_figure_work_order",
    "execute_figure_work_order",
    "execute_figure_work_orders",
    "validate_reusable_figure_asset",
]

"""Pure SharedLessonDocument figure media adapter.

The adapter freezes semantic figure input into the existing visual work-order
contract. Provider/executor errors stay in typed result diagnostics and never
become learner-facing captions or alternative text.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import FigureNode, SharedLessonDocument
from media.generation.contracts import (
    GeneratedVisualBlock,
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
    validate_visual_block,
)


class SharedFigureMediaError(ValueError):
    """A figure cannot be safely bound to a hosted media result."""


class SharedFigureWorkOrder(BaseModel):
    """Frozen source identity and semantic hash alongside the media work order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_document_id: str = Field(min_length=1)
    source_document_revision: int = Field(ge=1)
    source_document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_id: str = Field(min_length=1)
    figure_node_id: str = Field(min_length=1)
    figure_semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    required: bool = True
    work_order: VisualGeneratorWorkOrder


class FigureMediaResult(BaseModel):
    """Immutable media binding; the shared document remains unchanged."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_document_id: str = Field(min_length=1)
    source_document_revision: int = Field(ge=1)
    source_document_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_id: str = Field(min_length=1)
    figure_node_id: str = Field(min_length=1)
    figure_semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    visual_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_url: str = Field(min_length=1)
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
    results: tuple[FigureMediaResult, ...] = ()
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


def _fact_entries(
    approved_source_facts: Mapping[str, str] | Sequence[str],
) -> tuple[SourceOfTruthEntry, ...]:
    if isinstance(approved_source_facts, Mapping):
        entries = [
            SourceOfTruthEntry(key=str(key), text=str(value))
            for key, value in sorted(approved_source_facts.items(), key=lambda item: str(item[0]))
        ]
    else:
        entries = [
            SourceOfTruthEntry(key=f"fact-{index}", text=str(value))
            for index, value in enumerate(approved_source_facts)
        ]
    if any(not entry.text.strip() for entry in entries):
        raise SharedFigureMediaError("approved source facts must be meaningful")
    return tuple(entries)


def build_figure_work_order(
    document: SharedLessonDocument,
    *,
    section_id: str,
    figure_node_id: str,
    approved_source_facts: Mapping[str, str] | Sequence[str] = (),
    required: bool = True,
    mode: str = "diagram",
) -> SharedFigureWorkOrder:
    """Freeze one validated FigureNode into a deterministic visual work order."""
    _verify_document(document)
    section = next((item for item in document.sections if item.id == section_id), None)
    if section is None:
        raise SharedFigureMediaError(f"unknown SharedLessonDocument section {section_id!r}")
    node = next((item for item in section.nodes if item.id == figure_node_id), None)
    if not isinstance(node, FigureNode):
        raise SharedFigureMediaError(
            f"{figure_node_id!r} is not a FigureNode in section {section_id!r}"
        )
    if not node.accessibility.alt_text.strip():
        raise SharedFigureMediaError(f"figure {figure_node_id!r} requires meaningful alt text")
    if node.display.asset_id:
        raise SharedFigureMediaError(
            f"figure {figure_node_id!r} already has a bound asset; create a new revision to regenerate"
        )
    facts = _fact_entries(approved_source_facts)
    semantic_payload = {
        "document_id": document.id,
        "document_revision": document.revision,
        "document_hash": document.content_hash,
        "section_id": section_id,
        "figure_node_id": figure_node_id,
        "caption": node.display.caption,
        "alt_text": node.accessibility.alt_text,
        "source_facts": [entry.model_dump(mode="json") for entry in facts],
    }
    semantic_hash = _hash_payload(semantic_payload)
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
        source_document_id=document.id,
        source_document_revision=document.revision,
        source_document_hash=document.content_hash,
        section_id=section_id,
        figure_node_id=figure_node_id,
        figure_semantic_hash=semantic_hash,
        required=required,
        work_order=order,
    )


def bind_generated_figure(
    work: SharedFigureWorkOrder,
    blocks: Sequence[GeneratedVisualBlock],
) -> FigureMediaResult:
    """Validate a hosted executor result without mutating the source document."""
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
    return FigureMediaResult(
        source_document_id=work.source_document_id,
        source_document_revision=work.source_document_revision,
        source_document_hash=work.source_document_hash,
        section_id=work.section_id,
        figure_node_id=work.figure_node_id,
        figure_semantic_hash=work.figure_semantic_hash,
        visual_id=block.visual_id,
        asset_id=block.visual_id,
        asset_url=block.image_url,
        status=block.status,
    )


async def execute_figure_work_order(
    work: SharedFigureWorkOrder,
    *,
    executor: FigureExecutor,
) -> FigureMediaResult:
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

    async def run_one(work: SharedFigureWorkOrder) -> FigureMediaResult | FigureMediaFailure:
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
    results = tuple(item for item in outcomes if isinstance(item, FigureMediaResult))
    failures = tuple(item for item in outcomes if isinstance(item, FigureMediaFailure))
    return FigureMediaBatchResult(
        ready=not any(item.required for item in failures),
        results=results,
        failures=failures,
    )


def validate_reusable_figure_asset(
    work: SharedFigureWorkOrder,
    result: FigureMediaResult,
) -> None:
    """Reject reuse when source or figure semantics are stale."""
    if (
        result.source_document_id != work.source_document_id
        or result.source_document_revision != work.source_document_revision
        or result.source_document_hash != work.source_document_hash
        or result.section_id != work.section_id
        or result.figure_node_id != work.figure_node_id
        or result.figure_semantic_hash != work.figure_semantic_hash
    ):
        raise SharedFigureMediaError("stale or conflicting figure media binding")
    if not result.asset_url.lower().startswith(("http://", "https://")):
        raise SharedFigureMediaError("reusable figure asset is not a valid hosted URL")


__all__ = [
    "FigureExecutor",
    "FigureMediaBatchResult",
    "FigureMediaFailure",
    "FigureMediaResult",
    "SharedFigureMediaError",
    "SharedFigureWorkOrder",
    "bind_generated_figure",
    "build_figure_work_order",
    "execute_figure_work_order",
    "execute_figure_work_orders",
    "validate_reusable_figure_asset",
]

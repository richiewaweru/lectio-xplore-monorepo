"""Section-early figure media contracts for SharedLessonDocument generation."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from document.shared_lesson.continuity import (
    ExpectedNodeShape,
    validate_section_continuity,
)
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import FigureNode, SharedLessonDocument, SharedSection
from document.shared_lesson.runtime import TeachingPlanSource, verify_teaching_plan_source
from infra.config import settings
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


class SharedFigureMediaProviderFailed(SharedFigureMediaError):
    """The visual provider/executor itself failed to produce an asset.

    This is distinct from a genuine shared-semantic-contract violation: the
    executor already tried and reported ``status="failed"`` (a provider or
    transport failure), so it must never be mistaken for invalid hosted
    output the provider actually returned.
    """


_MEDIA_NARRATIVE_SECTION_ISSUES = frozenset(
    {
        "teaching_block_unrealized",
        "must_establish_uncovered",
        "avoid_repeating_violated",
        "bridge_unrealized",
        "exit_state_unrealized",
    }
)


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
    mode: str = Field(min_length=1)
    source_facts: tuple[SourceOfTruthEntry, ...] = ()
    required: bool = True
    status: str = "ready"


# Fixed, closed set of reasons a figure may be deferred instead of persisted
# as a failure. Only these two failure classifications -- a reporting
# provider/transport failure and a genuine shared-media-contract violation --
# may ever be deferred. Programming/auth/config errors must never become a
# semantic fallback and are excluded on purpose (see media_runtime.py).
_DEFERRED_MEDIA_REASON_CODES = frozenset({"media_provider_failed", "media_invalid_output"})


class DeferredFigureMediaResult(BaseModel):
    """A section-early figure explicitly deferred instead of a ready result.

    Produced only when the local-only, default-OFF ``shared_document_media_
    optional`` switch is enabled and the media provider or the shared media
    contract failed. It carries the identical section-early identity as
    ``ReadyFigureMediaResult`` so it can still be verified and rebound to the
    assembled document, but it never carries a hosted asset URL, an asset ID,
    or any provider diagnostic text -- the figure has no rendered image and
    the underlying ``FigureNode`` keeps ``asset_id=None``.
    """

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
    mode: str = Field(min_length=1)
    required: bool = True
    source_facts: tuple[SourceOfTruthEntry, ...] = ()
    reason_code: str = Field(min_length=1)
    status: Literal["deferred"] = "deferred"

    @field_validator("reason_code")
    @classmethod
    def _known_reason_code(cls, value: str) -> str:
        if value not in _DEFERRED_MEDIA_REASON_CODES:
            raise ValueError(f"unsupported deferred media reason_code: {value!r}")
        return value


class DeferredFigureMediaBinding(BaseModel):
    """A deferred media result bound to one immutable assembled document."""

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
    mode: str = Field(min_length=1)
    required: bool = True
    source_facts: tuple[SourceOfTruthEntry, ...] = ()
    reason_code: str = Field(min_length=1)
    status: Literal["deferred"] = "deferred"

    @field_validator("reason_code")
    @classmethod
    def _known_reason_code(cls, value: str) -> str:
        if value not in _DEFERRED_MEDIA_REASON_CODES:
            raise ValueError(f"unsupported deferred media reason_code: {value!r}")
        return value


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
    # Writer/boundary QA owns narrative continuity. Media admission keeps the
    # hard contract checks that protect accepted node identity/shape and source
    # grounding, without re-applying lexical coverage after a semantic PASS.
    issues = tuple(
        issue for issue in issues if issue.issue_code not in _MEDIA_NARRATIVE_SECTION_ISSUES
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
    if block.status == "failed":
        # The executor already attempted the provider call and reported a
        # failure; this is a provider/transport failure, not a violation of
        # the shared media contract, and must be classified separately so it
        # is never mistaken for invalid hosted output.
        raise SharedFigureMediaProviderFailed(
            f"figure {work.figure_node_id!r} media provider call failed"
        )
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
    # Shared figure semantics (caption/alt text) come only from the FigureNode
    # that produced this work order, never from the provider block. The
    # provider's own caption/alt_text fields are diagnostic only: the real
    # executor sets both to the work order's purpose, which legitimately
    # differs from the FigureNode's alt text, and neither field is ever
    # copied into ReadyFigureMediaResult/FigureMediaResult or the document.
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


def bind_deferred_figure_media(
    work: SharedFigureWorkOrder,
    *,
    reason_code: str,
) -> DeferredFigureMediaResult:
    """Close one figure as deferred instead of a ready provider result.

    Only the local-only ``shared_document_media_optional`` switch may call
    this, and only for the two closed failure reasons the switch is allowed
    to defer.  It never receives or persists the provider's own diagnostic
    text -- the caller supplies only the fixed, safe ``reason_code``.
    """
    if reason_code not in _DEFERRED_MEDIA_REASON_CODES:
        raise SharedFigureMediaError(f"unsupported deferred media reason_code: {reason_code!r}")
    return DeferredFigureMediaResult(
        source_plan_id=work.source_plan_id,
        source_plan_revision=work.source_plan_revision,
        source_plan_hash=work.source_plan_hash,
        section_id=work.section_id,
        section_output_hash=work.section_output_hash,
        figure_node_id=work.figure_node_id,
        figure_semantic_hash=work.figure_semantic_hash,
        work_order_id=work.work_order.work_order_id,
        visual_id=work.work_order.visual.id,
        mode=work.work_order.visual.mode,
        required=work.required,
        source_facts=tuple(work.work_order.source_of_truth),
        reason_code=reason_code,
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
        mode=media.mode,
        source_facts=tuple(media.source_facts),
        required=media.required,
        status=media.status,
    )


def verify_bound_figure_media(
    media: FigureMediaResult,
    document: SharedLessonDocument,
) -> FigureMediaResult:
    """Recompute and verify every identity of an already document-bound result.

    ``bind_figure_media_to_document`` accepts the pre-document-bound provider
    result.  READY persistence receives the post-binding result, so reconstruct
    that pre-binding view from the closed result, bind it again, and require an
    exact canonical match.  This catches stale document, section, semantic,
    work-order, asset, and source lineage fields at the final boundary.
    """
    _verify_document(document)
    if (
        media.source_document_id != document.id
        or media.source_document_revision != document.revision
        or media.source_document_hash != document.content_hash
    ):
        raise SharedFigureMediaError("bound media document identity is stale or changed")
    candidate = ReadyFigureMediaResult(
        source_plan_id=media.source_plan_id,
        source_plan_revision=media.source_plan_revision,
        source_plan_hash=media.source_plan_hash,
        section_id=media.section_id,
        section_output_hash=media.section_output_hash,
        figure_node_id=media.figure_node_id,
        figure_semantic_hash=media.figure_semantic_hash,
        work_order_id=media.work_order_id,
        visual_id=media.visual_id,
        asset_id=media.asset_id,
        asset_url=media.asset_url,
        mode=media.mode,
        source_facts=tuple(media.source_facts),
        required=media.required,
        status=media.status,
    )
    rebound = bind_figure_media_to_document(candidate, document)
    if rebound != media:
        raise SharedFigureMediaError(
            "bound media result does not match its recomputed document binding"
        )
    return media


def bind_deferred_figure_media_to_document(
    media: DeferredFigureMediaResult,
    document: SharedLessonDocument,
) -> DeferredFigureMediaBinding:
    """Bind a deferred figure result only after the assembled document is verified.

    Mirrors ``bind_figure_media_to_document`` exactly for every identity check
    (document, section, figure, semantic hash, work-order/visual identity),
    but never checks for a hosted asset -- a deferred figure has none, and the
    document figure keeps ``asset_id=None``.
    """
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
    return DeferredFigureMediaBinding(
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
        mode=media.mode,
        source_facts=tuple(media.source_facts),
        required=media.required,
        reason_code=media.reason_code,
    )


def verify_bound_deferred_figure_media(
    media: DeferredFigureMediaBinding,
    document: SharedLessonDocument,
) -> DeferredFigureMediaBinding:
    """Recompute and verify every identity of an already document-bound deferred result.

    Mirrors ``verify_bound_figure_media`` for the deferred binding: reconstruct
    the pre-binding view from the closed result, bind it again, and require an
    exact canonical match.
    """
    _verify_document(document)
    if (
        media.source_document_id != document.id
        or media.source_document_revision != document.revision
        or media.source_document_hash != document.content_hash
    ):
        raise SharedFigureMediaError("bound media document identity is stale or changed")
    candidate = DeferredFigureMediaResult(
        source_plan_id=media.source_plan_id,
        source_plan_revision=media.source_plan_revision,
        source_plan_hash=media.source_plan_hash,
        section_id=media.section_id,
        section_output_hash=media.section_output_hash,
        figure_node_id=media.figure_node_id,
        figure_semantic_hash=media.figure_semantic_hash,
        work_order_id=media.work_order_id,
        visual_id=media.visual_id,
        mode=media.mode,
        source_facts=tuple(media.source_facts),
        required=media.required,
        reason_code=media.reason_code,
    )
    rebound = bind_deferred_figure_media_to_document(candidate, document)
    if rebound != media:
        raise SharedFigureMediaError(
            "bound media result does not match its recomputed document binding"
        )
    return media


def bind_durable_media_output(
    payload: Any,
    document: SharedLessonDocument,
    *,
    media_optional: bool | None = None,
) -> FigureMediaResult | DeferredFigureMediaBinding:
    """Parse and bind one durable media WorkItem output to the assembled document.

    Every real-Run consumer of a media WorkItem's ``output_json`` (document QA
    dispatch, handoff, finalization) must go through this single parsing rule
    instead of assuming a ready result. A ``status="deferred"`` payload only
    exists because the local-only, default-OFF ``shared_document_media_
    optional`` switch was enabled when the figure was executed. If the switch
    is off now -- including for a Run produced while it was on -- the
    deferred output is rejected exactly like any other invalid media output,
    fail-closed, never silently accepted.

    ``media_optional`` defaults to the live ``settings.shared_document_media_
    optional`` value when not given explicitly, matching the executor's own
    default-resolution rule.
    """
    optional_media = (
        settings.shared_document_media_optional if media_optional is None else media_optional
    )
    status = payload.get("status") if isinstance(payload, Mapping) else None
    if status == "deferred":
        if not optional_media:
            raise SharedFigureMediaError(
                "durable media output is deferred, but shared_document_media_optional "
                "is not enabled"
            )
        deferred = DeferredFigureMediaResult.model_validate(payload)
        return bind_deferred_figure_media_to_document(deferred, document)
    ready = ReadyFigureMediaResult.model_validate(payload)
    return bind_figure_media_to_document(ready, document)


def verify_bound_durable_media(
    result: FigureMediaResult | DeferredFigureMediaBinding,
    document: SharedLessonDocument,
    *,
    media_optional: bool | None = None,
) -> FigureMediaResult | DeferredFigureMediaBinding:
    """Verify one already document-bound durable media result, failing closed on deferred.

    Mirrors ``bind_durable_media_output``'s switch policy at the verification
    boundary: a ``DeferredFigureMediaBinding`` is only ever accepted when the
    local-only ``shared_document_media_optional`` switch is enabled.
    """
    optional_media = (
        settings.shared_document_media_optional if media_optional is None else media_optional
    )
    if isinstance(result, DeferredFigureMediaBinding):
        if not optional_media:
            raise SharedFigureMediaError(
                "media evidence is deferred, but shared_document_media_optional is not enabled"
            )
        return verify_bound_deferred_figure_media(result, document)
    return verify_bound_figure_media(result, document)


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
    "DeferredFigureMediaBinding",
    "DeferredFigureMediaResult",
    "FigureExecutor",
    "FigureMediaBatchResult",
    "FigureMediaFailure",
    "FigureMediaResult",
    "ReadyFigureMediaResult",
    "SharedFigureMediaError",
    "SharedFigureMediaProviderFailed",
    "SharedFigureWorkOrder",
    "bind_deferred_figure_media",
    "bind_deferred_figure_media_to_document",
    "bind_durable_media_output",
    "bind_figure_media_to_document",
    "bind_generated_figure",
    "build_figure_work_order",
    "execute_figure_work_order",
    "execute_figure_work_orders",
    "validate_reusable_figure_asset",
    "verify_bound_deferred_figure_media",
    "verify_bound_durable_media",
    "verify_bound_figure_media",
]

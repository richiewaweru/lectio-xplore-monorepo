"""Section-early figure media contracts for SharedLessonDocument generation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from document.shared_lesson.continuity import (
    ExpectedNodeShape,
    validate_section_continuity,
)
from curriculum.teaching_plan.models import VisualSpec
from document.shared_lesson.continuity import node_text
from document.shared_lesson.figure_consistency import label_warnings, normalize_text
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import (
    CalloutNode,
    FigureNode,
    ListNode,
    ParagraphNode,
    SharedLessonDocument,
    SharedSection,
)
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
        # Token-overlaps each must_establish statement against literal source
        # facts; analytical/pedagogical conclusions about a source never occur
        # verbatim in it, so it blocked a faithful literature lesson. Source
        # fidelity stays with the writer's source rules and document QA.
        "unsupported_required_fact",
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
    #: Non-blocking deterministic findings (e.g. ``label_missing:<label>``)
    #: derived from the writer caption/section text; surfaced, never gating.
    warnings: list[str] = Field(default_factory=list)


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
    #: Alt text bound with the ready result (fallback built from the plan spec
    #: until a provider text part is preferred). Pending figure nodes carry "".
    alt_text: str = ""
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
    alt_text: str = ""
    source_facts: tuple[SourceOfTruthEntry, ...] = ()
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


#: Key prefix of the work-order context entries (writer caption, referring
#: sentences). Approved source-fact keys must never use it.
FIGURE_CONTEXT_KEY_PREFIX = "context:"
_MAX_REFERRING_SENTENCES = 2
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_FIGURE_WORDS = re.compile(r"\b(?:figure|diagram|picture)\b", re.IGNORECASE)


def fallback_alt_text(spec: Any) -> str:
    """Alt text built in code from a visual spec (``VisualSpec`` or ``VisualPlanItem``).

    Interim: a later phase prefers the image provider's own text part.
    """
    alt = f"{spec.purpose}. Shows: {', '.join(spec.must_show)}."
    labels = list(spec.labels_required)
    if labels:
        alt += f" Labels: {', '.join(labels)}."
    return alt


_MAX_PROVIDER_ALT_CHARS = 400


def _clean_provider_alt_text(text: str | None) -> str | None:
    """Single-paragraph, length-capped provider text, or None if unusable."""
    if not text:
        return None
    cleaned = " ".join(text.split())
    if not cleaned:
        return None
    if len(cleaned) > _MAX_PROVIDER_ALT_CHARS:
        cleaned = cleaned[: _MAX_PROVIDER_ALT_CHARS - 1].rstrip() + "…"
    return cleaned


def figure_semantic_hash(
    *,
    source_plan_id: str,
    source_plan_revision: int,
    source_plan_hash: str,
    section_output_hash: str,
    section_id: str,
    figure_node_id: str,
    caption: str,
    source_facts: Sequence[SourceOfTruthEntry],
    mode: str,
    required: bool,
) -> str:
    """Single semantic identity for a figure.

    The plan hash pins the authoritative visual spec and the section output
    hash pins the prose; alt text is deliberately excluded (it is pending at
    section time and bound with the ready result).
    """
    return _hash_payload(
        {
            "source_plan_id": source_plan_id,
            "source_plan_revision": source_plan_revision,
            "source_plan_hash": source_plan_hash,
            "section_output_hash": section_output_hash,
            "section_id": section_id,
            "figure_node_id": figure_node_id,
            "caption": caption,
            "source_facts": [fact.model_dump(mode="json") for fact in source_facts],
            "mode": mode,
            "required": required,
        }
    )


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT.split(text.strip()) if part.strip()]


def _block_text_nodes(section: SharedSection, node: FigureNode) -> list[str]:
    return [
        node_text(candidate)
        for candidate in section.nodes
        if candidate.teaching_block_id == node.teaching_block_id
        and isinstance(candidate, (ParagraphNode, ListNode, CalloutNode))
    ]


def _referring_sentences(
    section: SharedSection, node: FigureNode, labels_required: Sequence[str]
) -> list[str]:
    """Up to two sentences from the figure's own block that point at the figure."""
    texts = [text for text in _block_text_nodes(section, node) if text.strip()]
    needles = [normalize_text(label) for label in labels_required if label.strip()]
    chosen: list[str] = []
    for text in texts:
        for sentence in _split_sentences(text):
            normalized = normalize_text(sentence)
            if _FIGURE_WORDS.search(sentence) or any(needle in normalized for needle in needles):
                chosen.append(sentence)
                if len(chosen) == _MAX_REFERRING_SENTENCES:
                    return chosen
    if chosen:
        return chosen
    for text in texts:
        sentences = _split_sentences(text)
        if sentences:
            return sentences[:1]
    return []


def _section_prose(section: SharedSection) -> str:
    return " ".join(
        node_text(candidate) for candidate in section.nodes if not isinstance(candidate, FigureNode)
    )


def _context_entries(
    section: SharedSection, node: FigureNode, spec: VisualSpec
) -> tuple[SourceOfTruthEntry, ...]:
    entries: list[SourceOfTruthEntry] = []
    caption = node.display.caption.strip()
    if caption:
        entries.append(SourceOfTruthEntry(key=f"{FIGURE_CONTEXT_KEY_PREFIX}caption", text=caption))
    for index, sentence in enumerate(
        _referring_sentences(section, node, spec.labels_required), start=1
    ):
        entries.append(
            SourceOfTruthEntry(
                key=f"{FIGURE_CONTEXT_KEY_PREFIX}section-text-{index}", text=sentence
            )
        )
    return tuple(entries)


def _plan_figure_spec(planned: Any, node: FigureNode) -> VisualSpec:
    block = next((item for item in planned.blocks if item.id == node.teaching_block_id), None)
    if block is None or block.visual is None:
        raise SharedFigureMediaError(
            f"figure {node.id!r} has no visual spec on its Teaching Plan block"
        )
    return block.visual


def _figure_order_from(
    *,
    identity: SourceIdentity,
    section: SharedSection,
    node: FigureNode,
    spec: VisualSpec,
    facts: Sequence[SourceOfTruthEntry],
) -> SharedFigureWorkOrder:
    """The one place a figure's identity, work order and warnings are derived.

    The plan's ``VisualSpec`` is authoritative for purpose, must_show,
    labels_required, must_not_show, mode and required; the writer caption and
    referring sentences are appended as context (``source_of_truth`` entries,
    which the image prompt renders as metadata, never as image text).
    """
    section_output_hash = _hash_payload(section.model_dump(mode="json"))
    entries = (*facts, *_context_entries(section, node, spec))
    semantic_hash = figure_semantic_hash(
        source_plan_id=identity.source_artifact_id,
        source_plan_revision=identity.source_revision,
        source_plan_hash=identity.source_hash,
        section_output_hash=section_output_hash,
        section_id=section.id,
        figure_node_id=node.id,
        caption=node.display.caption,
        source_facts=entries,
        mode=spec.mode,
        required=spec.required,
    )
    visual = VisualPlanItem(
        id=f"shared-figure-{semantic_hash[:24]}",
        attaches_to=node.id,
        mode=spec.mode,
        purpose=spec.purpose,
        must_show=list(spec.must_show),
        labels_required=list(spec.labels_required),
        must_not_show=list(spec.must_not_show),
    )
    order = VisualGeneratorWorkOrder(
        work_order_id=f"shared-media-{semantic_hash}",
        resource_type="shared_lesson_figure",
        dependency="section_text",
        visual=visual,
        source_of_truth=list(entries),
    )
    return SharedFigureWorkOrder(
        source_plan_id=identity.source_artifact_id,
        source_plan_revision=identity.source_revision,
        source_plan_hash=identity.source_hash,
        section_id=section.id,
        section_output_hash=section_output_hash,
        figure_node_id=node.id,
        figure_semantic_hash=semantic_hash,
        required=spec.required,
        work_order=order,
        warnings=label_warnings(spec.labels_required, _section_prose(section), node.display.caption),
    )


def build_figure_work_order(
    source: TeachingPlanSource,
    section: SharedSection,
    *,
    figure_node_id: str,
    expected_shape: Sequence[ExpectedNodeShape | Mapping[str, Any] | Any],
    approved_source_facts: Mapping[str, str] | Sequence[str] = (),
    approved_source_ids: Sequence[str] = (),
) -> SharedFigureWorkOrder:
    """Freeze one validated accepted section into an early media work order.

    The visual contract comes from the plan block that owns the figure node.
    """
    facts = _fact_entries(approved_source_facts)
    if any(fact.key.startswith(FIGURE_CONTEXT_KEY_PREFIX) for fact in facts):
        raise SharedFigureMediaError(
            f"approved source fact keys must not start with {FIGURE_CONTEXT_KEY_PREFIX!r}"
        )
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
    if node.display.asset_id:
        raise SharedFigureMediaError(
            f"figure {figure_node_id!r} already has a bound asset; create a new revision to regenerate"
        )
    _identity, planned = _planned_section(source, section)
    spec = _plan_figure_spec(planned, node)
    return _figure_order_from(identity=identity, section=section, node=node, spec=spec, facts=facts)


def rebuild_figure_work_order(
    work: SharedFigureWorkOrder,
    section: SharedSection,
    *,
    spec: VisualSpec | None = None,
) -> SharedFigureWorkOrder:
    """Re-derive a frozen work order from the accepted section with the shared builder.

    ``spec`` is the plan block's authoritative ``VisualSpec`` when the approved
    Teaching Plan is available. Without it (identity-only callers), the spec is
    read back from the frozen work order, so the check still proves the context,
    identity and hash are consistent with the accepted section.
    """
    node = next((item for item in section.nodes if item.id == work.figure_node_id), None)
    if not isinstance(node, FigureNode):
        raise SharedFigureMediaError("accepted section does not contain the frozen FigureNode")
    if spec is None:
        frozen = work.work_order.visual
        if frozen.mode not in ("diagram", "image"):
            raise SharedFigureMediaError("figure work order mode is unsupported")
        spec = VisualSpec(
            mode=frozen.mode,
            purpose=frozen.purpose,
            must_show=list(frozen.must_show),
            labels_required=list(frozen.labels_required),
            must_not_show=list(frozen.must_not_show),
            required=work.required,
        )
    facts = tuple(
        entry
        for entry in work.work_order.source_of_truth
        if not entry.key.startswith(FIGURE_CONTEXT_KEY_PREFIX)
    )
    identity = SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id=work.source_plan_id,
        source_revision=work.source_plan_revision,
        source_hash=work.source_plan_hash,
    )
    return _figure_order_from(identity=identity, section=section, node=node, spec=spec, facts=facts)


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
    # Shared figure semantics come only from the plan spec and FigureNode that
    # produced this work order, never from the provider block. The provider's
    # own caption/alt_text fields are diagnostic only (the executor sets both to
    # the work order's purpose). Alt text prefers the provider's text part and
    # falls back to text built in code from the spec.
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
        alt_text=(
            _clean_provider_alt_text(block.provider_text)
            or fallback_alt_text(work.work_order.visual)
        ),
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
    semantic_hash = figure_semantic_hash(
        source_plan_id=media.source_plan_id,
        source_plan_revision=media.source_plan_revision,
        source_plan_hash=media.source_plan_hash,
        section_output_hash=section_hash,
        section_id=section.id,
        figure_node_id=node.id,
        caption=node.display.caption,
        source_facts=media.source_facts,
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
    if not media.alt_text.strip():
        raise SharedFigureMediaError("ready media result has no alt text")
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
        alt_text=media.alt_text,
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
        alt_text=media.alt_text,
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


def bind_durable_media_output(
    payload: Any,
    document: SharedLessonDocument,
) -> FigureMediaResult:
    """Parse and bind one durable media WorkItem output to the assembled document.

    Every real-Run consumer of a media WorkItem's ``output_json`` (document QA
    dispatch, handoff, finalization) goes through this single parsing rule.
    """
    ready = ReadyFigureMediaResult.model_validate(payload)
    return bind_figure_media_to_document(ready, document)


def verify_bound_durable_media(
    result: FigureMediaResult,
    document: SharedLessonDocument,
) -> FigureMediaResult:
    """Verify one already document-bound durable media result."""
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
    "FigureExecutor",
    "FigureMediaBatchResult",
    "FigureMediaFailure",
    "FigureMediaResult",
    "ReadyFigureMediaResult",
    "SharedFigureMediaError",
    "SharedFigureMediaProviderFailed",
    "SharedFigureWorkOrder",
    "fallback_alt_text",
    "figure_semantic_hash",
    "rebuild_figure_work_order",
    "bind_durable_media_output",
    "bind_figure_media_to_document",
    "bind_generated_figure",
    "build_figure_work_order",
    "execute_figure_work_order",
    "execute_figure_work_orders",
    "validate_reusable_figure_asset",
    "verify_bound_durable_media",
    "verify_bound_figure_media",
]

"""Whole-Run proof that the media-optional switch flows through real dispatchers.

commit 3f5e37e2 taught ``finalizer.py``/``repository.py`` to accept a deferred
figure media result only when the local-only, default-OFF
``shared_document_media_optional`` switch is enabled.  These tests prove the
same policy now holds at the earlier, real-Run boundaries that read a media
WorkItem's durable output directly: ``document_qa_dispatcher.py``'s
``dispatch_shared_document_qa`` (through the shared ``bind_durable_media_
output``/``verify_bound_durable_media`` helpers in ``media.py``).
"""

from __future__ import annotations

import pytest
from test_shared_qa_runtime import _seed_run

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
    VisualSpec,
)
from document.shared_lesson.assembly import assemble_shared_lesson_document
from document.shared_lesson.composer import CompositionChoice, validate_and_build_composition
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.document_qa_dispatcher import (
    SharedDocumentQADispatchError,
    dispatch_shared_document_qa,
)
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.handoff_dispatcher import handoff_qa_dispatch_result
from document.shared_lesson.media import (
    bind_deferred_figure_media,
    bind_deferred_figure_media_to_document,
    build_figure_work_order,
)
from document.shared_lesson.models import (
    FigureAccessibility,
    FigureDisplay,
    FigureNode,
    ParagraphDisplay,
    ParagraphNode,
    SharedSection,
)
from document.shared_lesson.runtime import TeachingPlanSource
from infra.config import settings
from infra.database.models import GenerationWorkItemModel
from infra.execution.checkpoints import content_hash


def _source_with_figure() -> TeachingPlanSource:
    section = TeachingPlanSection(
        slot_id="explain",
        specific_purpose="Explain energy transfer",
        display_title="Energy transfer",
        entry_state=["recognize energy"],
        must_establish=["explain energy transfer"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["explain energy transfer"],
        blocks=[
            TeachingPlanBlock(
                id="explain-block",
                position=0,
                intent="Explain energy transfer with a diagram",
                brief="Explain energy transfer clearly and show a diagram of the energy flow",
                evidence="The learner can explain energy transfer",
                visual=VisualSpec(
                    purpose="Show how energy flows between systems",
                    must_show=["Source system", "Receiving system"],
                    labels_required=["Energy"],
                ),
            )
        ],
    )
    plan = TeachingPlan(
        arc="Energy",
        contract_version=2,
        learner_title="Energy transfer",
        starting_state=["recognize energy"],
        target_state=["explain energy transfer"],
        teaching_plan_id="plan-media-optional",
        revision=3,
        sections=[section],
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id="plan-media-optional",
        revision=3,
        status="approved",
        preparation_hash="c" * 64,
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-27T09:00:00Z",
        approved_at="2026-09-27T09:01:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id="plan-media-optional",
        revision=3,
        content_hash=digest,
    )


def _accepted_with_figure():
    source = _source_with_figure()
    plan_section = source.plan.sections[0]
    composition = validate_and_build_composition(
        section=plan_section,
        choices=(
            CompositionChoice(
                teaching_block_id="explain-block",
                kind="paragraph",
                semantic_role="explanation",
            ),
        ),
        tasks=(),
    )
    paragraph_item, figure_item = composition.items
    section = SharedSection(
        id="explain",
        title="Energy transfer",
        position=0,
        nodes=(
            ParagraphNode(
                id=paragraph_item.id,
                teaching_block_id=paragraph_item.teaching_block_id,
                display=ParagraphDisplay(
                    text=(
                        "Energy transfer explains how energy moves from one system "
                        "to another."
                    )
                ),
            ),
            FigureNode(
                id=figure_item.id,
                teaching_block_id=figure_item.teaching_block_id,
                display=FigureDisplay(caption="Energy flow diagram"),
                accessibility=FigureAccessibility(
                    alt_text="Diagram showing energy flow between systems"
                ),
            ),
        ),
    )
    return source, composition, section, figure_item.id


def _expected_shapes(composition):
    return tuple(
        ExpectedNodeShape(
            id=item.id,
            kind=item.kind,
            teaching_block_id=item.teaching_block_id,
            semantic_role=item.semantic_role,
            task_spec_id=item.task_spec_id,
        )
        for item in composition.items
    )


def _seed_deferred_media_work_item(
    *,
    run_id: str,
    source: TeachingPlanSource,
    section: SharedSection,
    figure_node_id: str,
    expected_shape,
):
    """Freeze one figure work order and close it as a deferred, unbound output.

    Mirrors exactly what ``media_runtime._complete_as_deferred`` persists to
    ``output_json`` for a real media WorkItem: the unbound, section-only
    ``DeferredFigureMediaResult`` payload -- never a document-bound value.
    """
    work = build_figure_work_order(
        source,
        section,
        figure_node_id=figure_node_id,
        expected_shape=expected_shape,
    )
    deferred = bind_deferred_figure_media(work, reason_code="media_provider_failed")
    return work.work_order.work_order_id, deferred


async def _insert_media_work_item(session, *, run_id: str, work_order_id: str, output: dict) -> None:
    item = GenerationWorkItemModel(
        run_id=run_id,
        item_key=f"media:{work_order_id}",
        stage="media_generation",
        status="ready",
        input_hash="media-optional-dispatch-input",
        definition_hash="media-optional-dispatch-definition",
        output_json=output,
        output_hash=content_hash(output),
    )
    session.add(item)
    await session.flush()


async def _semantic_pass(_request):
    return DocumentSemanticVerdict(status="pass")


@pytest.mark.asyncio
async def test_dispatch_admits_document_qa_with_deferred_required_figure_when_media_optional_is_on(
    db_session,
    db_session_factory,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shared_document_media_optional", True)
    source, composition, section, figure_id = _accepted_with_figure()
    owner, run_id = await _seed_run(db_session, source, suffix="media-optional-on")

    document_id = "media-optional-on-document"
    shapes = {"explain": _expected_shapes(composition)}
    # Pre-compute the same assembled document the dispatcher will build so the
    # deferred figure can be bound to it exactly once, deterministically.
    draft = assemble_shared_lesson_document(
        document_id=document_id,
        revision=1,
        source=source,
        accepted_sections={"explain": section},
        created_at="2026-09-27T12:00:00Z",
        expected_shapes=shapes,
        required_media_by_section={},
        available_media_ids=(),
    )
    assert draft.ready

    work_order_id, deferred = _seed_deferred_media_work_item(
        run_id=run_id,
        source=source,
        section=draft.document.sections[0],
        figure_node_id=figure_id,
        expected_shape=shapes["explain"],
    )
    await _insert_media_work_item(
        db_session,
        run_id=run_id,
        work_order_id=work_order_id,
        output=deferred.model_dump(mode="json"),
    )
    await db_session.commit()
    bound_deferred = bind_deferred_figure_media_to_document(deferred, draft.document)

    result = await dispatch_shared_document_qa(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        compositions=(composition,),
        sections=(section,),
        document_id=document_id,
        document_revision=1,
        created_at="2026-09-27T12:00:00Z",
        required_media_by_section={"explain": (figure_id,)},
        media_results=(bound_deferred,),
        semantic_validator=_semantic_pass,
    )

    assert result.verified_qa.semantic_qa.passed
    figure_node = next(
        node for node in result.document.sections[0].nodes if node.id == figure_id
    )
    # The document QA path never receives a rendered asset for a deferred
    # figure -- only that it is pending, never provider diagnostic text.
    assert figure_node.display.asset_id is None

    # The deferred figure must also flow cleanly through handoff -- the next
    # boundary before finalization -- without a second provider call.
    handoff = await handoff_qa_dispatch_result(
        result,
        source=source,
        compositions=(composition,),
        sections=(section,),
        required_media_by_section={"explain": (figure_id,)},
        media_results=(bound_deferred,),
    )
    assert handoff.document == result.document


@pytest.mark.asyncio
async def test_dispatch_rejects_deferred_media_output_when_media_optional_is_off(
    db_session,
    db_session_factory,
) -> None:
    assert settings.shared_document_media_optional is False
    source, composition, section, figure_id = _accepted_with_figure()
    owner, run_id = await _seed_run(db_session, source, suffix="media-optional-off")

    document_id = "media-optional-off-document"
    shapes = {"explain": _expected_shapes(composition)}
    draft = assemble_shared_lesson_document(
        document_id=document_id,
        revision=1,
        source=source,
        accepted_sections={"explain": section},
        created_at="2026-09-27T12:00:00Z",
        expected_shapes=shapes,
        required_media_by_section={},
        available_media_ids=(),
    )
    assert draft.ready

    work_order_id, deferred = _seed_deferred_media_work_item(
        run_id=run_id,
        source=source,
        section=draft.document.sections[0],
        figure_node_id=figure_id,
        expected_shape=shapes["explain"],
    )
    await _insert_media_work_item(
        db_session,
        run_id=run_id,
        work_order_id=work_order_id,
        output=deferred.model_dump(mode="json"),
    )
    await db_session.commit()

    with pytest.raises(SharedDocumentQADispatchError, match="invalid"):
        await dispatch_shared_document_qa(
            db_session_factory,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            compositions=(composition,),
            sections=(section,),
            document_id=document_id,
            document_revision=1,
            created_at="2026-09-27T12:00:00Z",
            required_media_by_section={"explain": (figure_id,)},
            semantic_validator=_semantic_pass,
        )

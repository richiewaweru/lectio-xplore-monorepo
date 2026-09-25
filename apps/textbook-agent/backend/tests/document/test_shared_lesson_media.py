from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.media import (
    SharedFigureMediaError,
    bind_figure_media_to_document,
    bind_generated_figure,
    build_figure_work_order,
    execute_figure_work_orders,
    validate_reusable_figure_asset,
)
from document.shared_lesson.models import (
    SharedLessonDocument,
    SharedSection,
    build_shared_lesson_document,
)
from document.shared_lesson.runtime import TeachingPlanSource
from media.generation.contracts import GeneratedVisualBlock


def _section(section_id: str, position: int, *, caption: str | None = None) -> SharedSection:
    caption = caption or (
        "A leaf in sunlight" if section_id == "section-a" else "Energy moves from the source"
    )
    alt_text = (
        "A leaf receiving sunlight"
        if section_id == "section-a"
        else "Energy moving through a leaf from the source"
    )
    node_id = "figure-a" if section_id == "section-a" else "figure-b"
    block_id = "block-a" if section_id == "section-a" else "block-b"
    return SharedSection(
        id=section_id,
        title="The energy source" if section_id == "section-a" else "The process",
        position=position,
        nodes=(
            {
                "id": node_id,
                "kind": "figure",
                "teaching_block_id": block_id,
                "display": {"caption": caption},
                "accessibility": {"alt_text": alt_text},
            },
        ),
    )


def _source() -> TeachingPlanSource:
    plans = [
        TeachingPlanSection(
            slot_id="section-a",
            display_title="The energy source",
            specific_purpose="Introduce the source",
            entry_state=["The learner is ready"],
            must_establish=["leaf"],
            avoid_repeating=[],
            bridge_from_previous=None,
            exit_state=["leaf"],
            blocks=[
                TeachingPlanBlock(
                    id="block-a",
                    position=0,
                    intent="Show the leaf",
                    brief="Show a leaf",
                    evidence="The learner identifies the leaf",
                )
            ],
        ),
        TeachingPlanSection(
            slot_id="section-b",
            display_title="The process",
            specific_purpose="Explain the process",
            entry_state=["The learner knows the source"],
            must_establish=["energy"],
            avoid_repeating=[],
            bridge_from_previous="source",
            exit_state=["energy"],
            blocks=[
                TeachingPlanBlock(
                    id="block-b",
                    position=1,
                    intent="Show energy movement",
                    brief="Show energy movement",
                    evidence="The learner follows energy",
                )
            ],
        ),
    ]
    plan = TeachingPlan(
        arc="Plant energy",
        contract_version=2,
        learner_title="Plant energy",
        starting_state=["The learner is ready"],
        target_state=["The learner understands energy"],
        teaching_plan_id="plan-1",
        revision=3,
        sections=plans,
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id="plan-1",
        revision=3,
        status="approved",
        preparation_hash="preparation-hash",
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-24T00:00:00Z",
        approved_at="2026-09-24T00:01:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id="plan-1",
        revision=3,
        content_hash=digest,
    )


def _shape(section_id: str) -> tuple[ExpectedNodeShape, ...]:
    return (
        ExpectedNodeShape(
            id="figure-a" if section_id == "section-a" else "figure-b",
            kind="figure",
            teaching_block_id="block-a" if section_id == "section-a" else "block-b",
            semantic_role="explanation",
        ),
    )


def _work(section_id: str = "section-a", *, facts=None, required: bool = True):
    section = _section(section_id, 0 if section_id == "section-a" else 1)
    return build_figure_work_order(
        _source(),
        section,
        figure_node_id="figure-a" if section_id == "section-a" else "figure-b",
        expected_shape=_shape(section_id),
        approved_source_facts=facts or {"fact-leaf": "The leaf receives sunlight."},
        required=required,
    )


def _document(
    source: TeachingPlanSource | None = None, *, changed_caption: str | None = None
) -> SharedLessonDocument:
    source = source or _source()
    section_a = _section("section-a", 0, caption=changed_caption)
    section_b = _section("section-b", 1)
    return build_shared_lesson_document(
        {
            "id": "shared-media-lesson",
            "revision": 1,
            "teaching_plan_id": source.id,
            "teaching_plan_revision": source.revision,
            "teaching_plan_hash": source.content_hash,
            "title": source.plan.learner_title,
            "sections": [section_a.model_dump(mode="json"), section_b.model_dump(mode="json")],
            "created_at": "2026-09-24T09:00:00+03:00",
        }
    )


def _block(work, *, url: str = "https://cdn.example.test/image.png", status: str = "ready"):
    return GeneratedVisualBlock(
        visual_id=work.work_order.visual.id,
        attaches_to=work.figure_node_id,
        mode=work.work_order.visual.mode,
        image_url=url,
        caption=work.work_order.visual.purpose,
        alt_text=work.work_order.visual.must_show[0],
        source_work_order_id=work.work_order.work_order_id,
        status=status,
    )


def test_section_early_work_order_freezes_plan_section_and_figure_identity() -> None:
    work = _work()

    assert work.source_plan_id == "plan-1"
    assert work.source_plan_revision == 3
    assert work.section_output_hash
    assert work.work_order.visual.purpose == "A leaf in sunlight"
    assert work.work_order.visual.must_show == ["A leaf receiving sunlight"]
    assert work.work_order.source_of_truth[0].text == "The leaf receives sunlight."
    assert work.work_order.work_order_id.startswith("shared-media-")


def test_ready_media_binds_only_after_document_hash_and_semantics_are_verified() -> None:
    source = _source()
    work = _work()
    ready = bind_generated_figure(work, [_block(work)])
    result = bind_figure_media_to_document(ready, _document(source))

    assert result.source_document_id == "shared-media-lesson"
    assert result.source_document_hash == _document(source).content_hash
    assert result.asset_id == work.work_order.visual.id


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.model_copy(update={"source_plan_hash": "b" * 64}),
        lambda value: value.model_copy(update={"section_output_hash": "b" * 64}),
        lambda value: value.model_copy(update={"figure_node_id": "other-figure"}),
        lambda value: value.model_copy(update={"asset_id": "other-asset"}),
    ],
)
def test_changed_media_identity_is_rejected_at_document_binding(mutate) -> None:
    work = _work()
    ready = mutate(bind_generated_figure(work, [_block(work)]))
    with pytest.raises(SharedFigureMediaError):
        bind_figure_media_to_document(ready, _document())


def test_changed_section_and_stale_document_are_rejected() -> None:
    work = _work()
    ready = bind_generated_figure(work, [_block(work)])
    changed = _document(changed_caption="Changed caption")
    with pytest.raises(SharedFigureMediaError, match="stale or changed"):
        bind_figure_media_to_document(ready, changed)

    stale_payload = deepcopy(_document().model_dump(mode="json"))
    stale_payload["title"] = "Changed without recomputing hash"
    stale = SharedLessonDocument.model_validate(
        stale_payload, context={"skip_content_hash_validation": True}
    )
    with pytest.raises(SharedFigureMediaError, match="stale"):
        bind_figure_media_to_document(ready, stale)


def test_pending_source_and_invalid_shape_or_facts_fail_before_media_order() -> None:
    source = _source()
    pending = source.model_copy(
        update={"revision_record": source.revision_record.model_copy(update={"status": "pending"})}
    )
    section = _section("section-a", 0)
    with pytest.raises(SharedFigureMediaError, match="approved Teaching Plan"):
        build_figure_work_order(
            pending,
            section,
            figure_node_id="figure-a",
            expected_shape=_shape("section-a"),
        )
    with pytest.raises(SharedFigureMediaError, match="deterministic validation"):
        build_figure_work_order(
            source,
            section,
            figure_node_id="figure-a",
            expected_shape=(
                ExpectedNodeShape(
                    id="other",
                    kind="figure",
                    teaching_block_id="block-a",
                    semantic_role="explanation",
                ),
            ),
        )
    with pytest.raises(SharedFigureMediaError, match="unsupported_required_fact"):
        build_figure_work_order(
            source,
            section,
            figure_node_id="figure-a",
            expected_shape=_shape("section-a"),
            approved_source_facts={"fact": "Unrelated fact."},
        )


def test_provider_diagnostics_never_replace_learner_figure_fields() -> None:
    work = _work()
    block = _block(work)
    block = block.model_copy(
        update={"caption": "provider diagnostic", "alt_text": "provider diagnostic"}
    )
    with pytest.raises(SharedFigureMediaError, match="semantics"):
        bind_generated_figure(work, [block])


def test_independent_figures_run_concurrently_and_required_failure_preserves_sibling() -> None:
    work_a = _work("section-a")
    work_b = _work(
        "section-b", facts={"fact-energy": "Energy moves through the leaf."}, required=False
    )
    works = (work_a, work_b)

    class Executor:
        active = 0
        maximum = 0

        async def execute_figure(self, order):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            await asyncio.sleep(0.02)
            self.active -= 1
            work = next(item for item in works if item.work_order == order)
            if work is work_a:
                raise RuntimeError("provider unavailable")
            return [_block(work)]

    executor = Executor()
    batch = asyncio.run(execute_figure_work_orders(works, executor=executor, concurrency=2))

    assert not batch.ready
    assert [result.figure_node_id for result in batch.results] == ["figure-b"]
    assert batch.failures[0].figure_node_id == "figure-a"
    assert batch.failures[0].required
    assert executor.maximum == 2


def test_targeted_retry_preserves_healthy_sibling_output() -> None:
    work_a = _work("section-a")
    work_b = _work(
        "section-b", facts={"fact-energy": "Energy moves through the leaf."}, required=False
    )
    healthy = bind_generated_figure(work_b, [_block(work_b)])
    attempts = {"figure-a": 0}

    class Executor:
        async def execute_figure(self, order):
            if order.visual.attaches_to == "figure-a":
                attempts["figure-a"] += 1
                if attempts["figure-a"] == 1:
                    raise RuntimeError("temporary provider error")
                return [_block(work_a)]
            return [_block(work_b)]

    executor = Executor()
    first = asyncio.run(execute_figure_work_orders((work_a, work_b), executor=executor))
    retry = asyncio.run(execute_figure_work_orders((work_a,), executor=executor))

    assert first.results == (healthy,)
    assert retry.ready
    assert retry.results[0].figure_node_id == "figure-a"
    assert attempts["figure-a"] == 2


def test_stale_or_conflicting_figure_reuse_is_rejected() -> None:
    work = _work()
    result = bind_generated_figure(work, [_block(work)])
    with pytest.raises(SharedFigureMediaError, match="stale"):
        validate_reusable_figure_asset(
            work, result.model_copy(update={"figure_semantic_hash": "b" * 64})
        )
    with pytest.raises(SharedFigureMediaError, match="stale"):
        validate_reusable_figure_asset(
            work, result.model_copy(update={"source_plan_hash": "b" * 64})
        )
    with pytest.raises(SharedFigureMediaError, match="hosted URL"):
        validate_reusable_figure_asset(work, result.model_copy(update={"asset_url": "not-a-url"}))


def test_existing_asset_cannot_be_reused_for_new_work_order() -> None:
    section = _section("section-a", 0)
    payload = section.model_dump(mode="json")
    payload["nodes"][0]["display"]["asset_id"] = "asset-existing"
    with pytest.raises(SharedFigureMediaError, match="already has a bound asset"):
        build_figure_work_order(
            _source(),
            SharedSection.model_validate(payload),
            figure_node_id="figure-a",
            expected_shape=_shape("section-a"),
        )

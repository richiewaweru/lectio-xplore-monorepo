from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
    VisualSpec,
)
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.media import (
    SharedFigureMediaError,
    SharedFigureMediaProviderFailed,
    bind_figure_media_to_document,
    bind_generated_figure,
    build_figure_work_order,
    execute_figure_work_orders,
    fallback_alt_text,
    validate_reusable_figure_asset,
    verify_bound_figure_media,
)
from document.shared_lesson.models import (
    SharedProvenance,
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
                "accessibility": {"alt_text": ""},
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
                    visual=VisualSpec(
                        purpose="Show how sunlight reaches a leaf",
                        must_show=["Sun", "Leaf"],
                        labels_required=["Sunlight", "Leaf"],
                        must_not_show=["A person"],
                    ),
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
                    visual=VisualSpec(
                        purpose="Show energy moving through a leaf",
                        must_show=["Source", "Leaf"],
                        labels_required=["Energy"],
                    ),
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


def _source_with_second_section_bridge(statement: str) -> TeachingPlanSource:
    source = _source()
    plan = source.plan.model_copy(deep=True)
    plan.sections[1].bridge_from_previous = statement
    digest = teaching_plan_content_hash(plan)
    record = source.revision_record.model_copy(
        update={"content_hash": digest, "plan": plan.model_dump(mode="json")}
    )
    return source.model_copy(
        update={"plan": plan, "revision_record": record, "content_hash": digest}
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


def _work(section_id: str = "section-a", *, facts=None):
    section = _section(section_id, 0 if section_id == "section-a" else 1)
    return build_figure_work_order(
        _source(),
        section,
        figure_node_id="figure-a" if section_id == "section-a" else "figure-b",
        expected_shape=_shape(section_id),
        approved_source_facts=facts or {"fact-leaf": "The leaf receives sunlight."},
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


def _block(work, *, url: str | None = "https://cdn.example.test/image.png", status: str = "ready"):
    # Mirror the real executor's own output shape (media/generation/executor.py):
    # both caption and alt_text are set to the work order's purpose, which
    # legitimately differs from the spec-built fallback alt text.
    return GeneratedVisualBlock(
        visual_id=work.work_order.visual.id,
        attaches_to=work.figure_node_id,
        mode=work.work_order.visual.mode,
        image_url=url,
        caption=work.work_order.visual.purpose,
        alt_text=work.work_order.visual.purpose,
        source_work_order_id=work.work_order.work_order_id,
        status=status,
        error_message="provider RuntimeError: dead image API" if status == "failed" else None,
    )


def test_section_early_work_order_freezes_plan_section_and_figure_identity() -> None:
    work = _work()

    assert work.source_plan_id == "plan-1"
    assert work.source_plan_revision == 3
    assert work.section_output_hash
    # The plan block's visual spec is authoritative -- not the caption/alt.
    visual = work.work_order.visual
    assert visual.purpose == "Show how sunlight reaches a leaf"
    assert visual.must_show == ["Sun", "Leaf"]
    assert visual.labels_required == ["Sunlight", "Leaf"]
    assert visual.must_not_show == ["A person"]
    assert visual.mode == "diagram"
    assert visual.attaches_to == "figure-a"
    assert work.required
    entries = {entry.key: entry.text for entry in work.work_order.source_of_truth}
    assert entries["fact-leaf"] == "The leaf receives sunlight."
    assert entries["context:caption"] == "A leaf in sunlight"
    # Only facts and writer context reach source_of_truth, never alt text.
    assert set(entries) == {"fact-leaf", "context:caption"}
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
        lambda value: value.model_copy(update={"source_document_hash": "b" * 64}),
        lambda value: value.model_copy(update={"section_output_hash": "b" * 64}),
        lambda value: value.model_copy(update={"figure_semantic_hash": "b" * 64}),
        lambda value: value.model_copy(update={"asset_id": "other-asset"}),
    ],
)
def test_bound_media_verifier_rejects_stale_document_section_semantic_and_asset(
    mutate,
) -> None:
    work = _work()
    bound = bind_figure_media_to_document(bind_generated_figure(work, [_block(work)]), _document())
    with pytest.raises(SharedFigureMediaError):
        verify_bound_figure_media(mutate(bound), _document())


def test_bound_media_verifier_recomputes_an_unchanged_result() -> None:
    work = _work()
    document = _document()
    bound = bind_figure_media_to_document(bind_generated_figure(work, [_block(work)]), document)

    assert verify_bound_figure_media(bound, document) == bound


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
    # unsupported_required_fact is deferred to document QA at media admission:
    # analytical must_establish statements never occur verbatim in sources.
    build_figure_work_order(
            source,
            section,
            figure_node_id="figure-a",
            expected_shape=_shape("section-a"),
            approved_source_facts={"fact": "Unrelated fact."},
        )


def test_media_admission_keeps_hard_contract_but_leaves_bridge_to_boundary_qa() -> None:
    source = _source_with_second_section_bridge(
        "A source idea continues into the energy flow."
    )
    section = _section("section-b", 1)
    work = build_figure_work_order(
        source,
        section,
        figure_node_id="figure-b",
        expected_shape=_shape("section-b"),
        approved_source_facts={"fact-energy": "Energy moves through the leaf."},
    )
    assert work.section_id == "section-b"
    assert work.required

    forged_source_section = section.model_copy(
        update={"provenance": SharedProvenance(source_ids=("unapproved-source",))}
    )
    with pytest.raises(SharedFigureMediaError, match="source_lineage_mismatch"):
        build_figure_work_order(
            source,
            forged_source_section,
            figure_node_id="figure-b",
            expected_shape=_shape("section-b"),
            approved_source_ids=("approved-source",),
            approved_source_facts={"fact-energy": "Energy moves through the leaf."},
        )
    with pytest.raises(SharedFigureMediaError, match="not a FigureNode"):
        build_figure_work_order(
            source,
            section,
            figure_node_id="forged-figure",
            expected_shape=_shape("section-b"),
            approved_source_facts={"fact-energy": "Energy moves through the leaf."},
        )

    with pytest.raises(SharedFigureMediaError, match="deterministic validation"):
        build_figure_work_order(
            source,
            section,
            figure_node_id="figure-b",
            expected_shape=(
                ExpectedNodeShape(
                    id="forged-figure",
                    kind="figure",
                    teaching_block_id="block-b",
                    semantic_role="explanation",
                ),
            ),
            approved_source_facts={"fact-energy": "Energy moves through the leaf."},
        )

    # unsupported_required_fact is deferred to document QA at media admission:
    # analytical must_establish statements never occur verbatim in sources.
    build_figure_work_order(
            source,
            section,
            figure_node_id="figure-b",
            expected_shape=_shape("section-b"),
            approved_source_facts={"fact-energy": "The leaf is blue."},
        )


def test_media_admission_fails_closed_on_unknown_continuity_issue(monkeypatch) -> None:
    monkeypatch.setattr(
        "document.shared_lesson.media.validate_section_continuity",
        lambda **_kwargs: (SimpleNamespace(issue_code="future_hard_contract"),),
    )

    with pytest.raises(SharedFigureMediaError, match="future_hard_contract"):
        _work()


def test_real_executor_shape_binds_even_when_caption_and_alt_text_differ() -> None:
    # The real executor (media/generation/executor.py) sets both caption and
    # alt_text to the work order's purpose, which legitimately differs from
    # the FigureNode's own alt text (``must_show[0]``). Binding must accept
    # this real shape rather than rejecting a valid result.
    work = _work()
    block = _block(work)
    assert block.caption == work.work_order.visual.purpose
    assert block.alt_text == work.work_order.visual.purpose

    ready = bind_generated_figure(work, [block])

    assert ready.asset_url == block.image_url
    assert not hasattr(ready, "caption")
    # Alt is built in code from the spec, never taken from provider diagnostics.
    assert ready.alt_text == fallback_alt_text(work.work_order.visual)


def test_provider_diagnostics_never_replace_learner_figure_fields() -> None:
    # Even wildly different provider diagnostic text must never leak into the
    # bound media result or the assembled document: shared figure semantics
    # come only from the FigureNode.
    source = _source()
    work = _work()
    block = _block(work).model_copy(
        update={"caption": "provider diagnostic", "alt_text": "provider diagnostic"}
    )

    ready = bind_generated_figure(work, [block])
    bound = bind_figure_media_to_document(ready, _document(source))

    assert not hasattr(bound, "caption")
    assert bound.alt_text != "provider diagnostic"
    assert bound.alt_text == fallback_alt_text(work.work_order.visual)
    section = next(item for item in _document(source).sections if item.id == work.section_id)
    node = next(item for item in section.nodes if item.id == work.figure_node_id)
    assert node.display.caption != "provider diagnostic"
    assert node.accessibility.alt_text == ""  # pending until media binds


def test_failed_provider_block_raises_provider_failed_not_invalid_output() -> None:
    work = _work()
    failed_block = _block(work, url=None, status="failed")

    with pytest.raises(SharedFigureMediaProviderFailed) as excinfo:
        bind_generated_figure(work, [failed_block])
    # A provider/transport failure must be its own exception type, distinct
    # from (though still a subclass of) generic contract violations, so a
    # caller can classify it separately.
    assert isinstance(excinfo.value, SharedFigureMediaError)


def test_independent_figures_run_concurrently_and_required_failure_preserves_sibling() -> None:
    work_a = _work("section-a")
    work_b = _work("section-b", facts={"fact-energy": "Energy moves through the leaf."})
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
    work_b = _work("section-b", facts={"fact-energy": "Energy moves through the leaf."})
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
    payload["nodes"][0]["accessibility"]["alt_text"] = "Existing alt"
    with pytest.raises(SharedFigureMediaError, match="already has a bound asset"):
        build_figure_work_order(
            _source(),
            SharedSection.model_validate(payload),
            figure_node_id="figure-a",
            expected_shape=_shape("section-a"),
        )


def _section_with_prose(caption: str, paragraph: str) -> SharedSection:
    return SharedSection(
        id="section-a",
        title="The energy source",
        position=0,
        nodes=(
            {
                "id": "para-a",
                "kind": "paragraph",
                "teaching_block_id": "block-a",
                "display": {"text": paragraph},
                "accessibility": {},
            },
            {
                "id": "figure-a",
                "kind": "figure",
                "teaching_block_id": "block-a",
                "display": {"caption": caption},
                "accessibility": {"alt_text": ""},
            },
        ),
    )


def _prose_shape() -> tuple[ExpectedNodeShape, ...]:
    return (
        ExpectedNodeShape(
            id="para-a",
            kind="paragraph",
            teaching_block_id="block-a",
            semantic_role="explanation",
        ),
        ExpectedNodeShape(
            id="figure-a",
            kind="figure",
            teaching_block_id="block-a",
            semantic_role="visual_model",
        ),
    )


def test_work_order_carries_spec_caption_and_referring_sentences_not_caption_or_alt_only() -> None:
    section = _section_with_prose(
        "Sunlight reaches a leaf",
        "Plants grow slowly. The diagram shows Sunlight hitting a Leaf. "
        "Roots take in water. Each Leaf is flat.",
    )
    work = build_figure_work_order(
        _source(),
        section,
        figure_node_id="figure-a",
        expected_shape=_prose_shape(),
        approved_source_facts={"fact-leaf": "The leaf receives sunlight."},
    )

    visual = work.work_order.visual
    assert visual.purpose == "Show how sunlight reaches a leaf"
    assert visual.purpose != section.nodes[1].display.caption
    assert visual.must_show == ["Sun", "Leaf"]
    assert visual.labels_required == ["Sunlight", "Leaf"]
    assert visual.must_not_show == ["A person"]
    entries = {entry.key: entry.text for entry in work.work_order.source_of_truth}
    assert entries["context:caption"] == "Sunlight reaches a leaf"
    # Exactly two referring sentences (figure word or a required label), in order.
    assert entries["context:section-text-1"] == "The diagram shows Sunlight hitting a Leaf."
    assert entries["context:section-text-2"] == "Each Leaf is flat."
    assert "context:section-text-3" not in entries
    assert "Plants grow slowly." not in entries.values()
    assert entries["fact-leaf"] == "The leaf receives sunlight."


def test_work_order_falls_back_to_first_sentence_when_nothing_refers_to_the_figure() -> None:
    section = _section_with_prose("Sunlight reaches a leaf", "Plants grow slowly. Roots drink.")
    work = build_figure_work_order(
        _source(),
        section,
        figure_node_id="figure-a",
        expected_shape=_prose_shape(),
    )
    entries = {entry.key: entry.text for entry in work.work_order.source_of_truth}
    assert entries["context:section-text-1"] == "Plants grow slowly."
    assert "context:section-text-2" not in entries


def test_label_check_records_non_blocking_warnings_on_the_work_order() -> None:
    section = _section_with_prose("A picture", "Plants grow slowly.")
    work = build_figure_work_order(
        _source(),
        section,
        figure_node_id="figure-a",
        expected_shape=_prose_shape(),
    )
    assert work.warnings == ["label_missing:Sunlight", "label_missing:Leaf"]

    covered = _section_with_prose("Sunlight and the leaf", "Plants grow slowly.")
    work = build_figure_work_order(
        _source(),
        covered,
        figure_node_id="figure-a",
        expected_shape=_prose_shape(),
    )
    assert work.warnings == []


def test_figure_whose_plan_block_has_no_visual_is_rejected() -> None:
    source = _source()
    plan = source.plan.model_copy(deep=True)
    plan.sections[0].blocks[0].visual = None
    digest = teaching_plan_content_hash(plan)
    record = source.revision_record.model_copy(
        update={"content_hash": digest, "plan": plan.model_dump(mode="json")}
    )
    no_visual = source.model_copy(
        update={"plan": plan, "revision_record": record, "content_hash": digest}
    )
    with pytest.raises(SharedFigureMediaError, match="no visual spec"):
        build_figure_work_order(
            no_visual,
            _section("section-a", 0),
            figure_node_id="figure-a",
            expected_shape=_shape("section-a"),
        )


def test_fallback_alt_text_is_built_from_the_spec_and_binds_with_the_ready_result() -> None:
    spec = VisualSpec(
        purpose="Show the water cycle",
        must_show=["Evaporation", "Rain"],
        labels_required=["Water vapour"],
    )
    assert fallback_alt_text(spec) == (
        "Show the water cycle. Shows: Evaporation, Rain. Labels: Water vapour."
    )
    assert fallback_alt_text(VisualSpec(purpose="P", must_show=["A"])) == "P. Shows: A."

    work = _work()
    ready = bind_generated_figure(work, [_block(work)])
    assert ready.alt_text == fallback_alt_text(work.work_order.visual)
    bound = bind_figure_media_to_document(ready, _document())
    assert bound.alt_text == ready.alt_text
    with pytest.raises(SharedFigureMediaError, match="alt text"):
        bind_figure_media_to_document(ready.model_copy(update={"alt_text": " "}), _document())


def test_runtime_verifier_rederives_with_the_shared_builder_against_the_plan_spec() -> None:
    from document.shared_lesson.media_runtime import MediaSourceConflict, _verify_accepted_section

    source = _source()
    work = _work()
    section = _section("section-a", 0)
    _verify_accepted_section(work, section, source)  # honest order passes

    forged = work.model_copy(
        update={
            "work_order": work.work_order.model_copy(
                update={
                    "visual": work.work_order.visual.model_copy(
                        update={"purpose": "Forged", "labels_required": []}
                    )
                }
            )
        }
    )
    with pytest.raises(MediaSourceConflict, match="differs"):
        _verify_accepted_section(forged, section, source)


def test_image_prompt_renders_spec_labels_and_writer_context_for_the_non_precision_path() -> None:
    from media.generation.prompt import build_visual_prompt

    work = _work()
    assert work.work_order.visual.visual_style is None  # not diagram_precision
    prompt = build_visual_prompt(work.work_order)

    assert "PURPOSE: Show how sunlight reaches a leaf" in prompt
    assert "- Sun" in prompt and "- Leaf" in prompt  # MUST SHOW
    assert "- A person" in prompt  # MUST NOT SHOW
    assert "LABELS REQUIRED" in prompt and "Sunlight, Leaf" in prompt
    assert "[context:caption] A leaf in sunlight" in prompt


def test_bound_alt_text_prefers_cleaned_provider_text() -> None:
    work = _work()
    block = _block(work).model_copy(
        update={"provider_text": "  A leaf under the sun.\n\nArrows show light.  "}
    )

    ready = bind_generated_figure(work, [block])

    assert ready.alt_text == "A leaf under the sun. Arrows show light."


def test_bound_alt_text_caps_long_provider_text() -> None:
    work = _work()
    block = _block(work).model_copy(update={"provider_text": "word " * 300})

    ready = bind_generated_figure(work, [block])

    assert 0 < len(ready.alt_text) <= 400


@pytest.mark.parametrize("provider_text", [None, "", "   \n "])
def test_bound_alt_text_falls_back_to_spec_without_provider_text(provider_text) -> None:
    work = _work()
    block = _block(work).model_copy(update={"provider_text": provider_text})

    ready = bind_generated_figure(work, [block])

    assert ready.alt_text == fallback_alt_text(work.work_order.visual)

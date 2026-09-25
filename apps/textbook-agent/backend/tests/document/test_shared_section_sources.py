from __future__ import annotations

import json
from copy import deepcopy

import pytest

from curriculum.lesson_sourcebook import LessonSourcebook, SourcebookEntry
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson.runtime import TeachingPlanSource
from document.shared_lesson.section_sources import (
    SectionSourceError,
    build_section_sources,
)
from document.shared_lesson.semantic_inputs import VerifiedSemanticInputs
from infra.execution.checkpoints import content_hash


def _source() -> TeachingPlanSource:
    sections = [
        TeachingPlanSection(
            slot_id="first",
            display_title="First section",
            entry_state=["Learner is ready"],
            must_establish=["The first idea"],
            avoid_repeating=[],
            bridge_from_previous=None,
            exit_state=["Learner can state the first idea"],
            blocks=[
                TeachingPlanBlock(
                    id="block-a",
                    position=0,
                    intent="Introduce the first idea",
                    brief="Introduce the first idea",
                    evidence="Learner can state the first idea",
                    sourcebook_refs=["entry-a", "entry-b", "entry-a"],
                ),
                TeachingPlanBlock(
                    id="block-b",
                    position=1,
                    intent="Use the first idea",
                    brief="Use the first idea",
                    evidence="Learner can use the first idea",
                    sourcebook_refs=["entry-b"],
                ),
            ],
        ),
        TeachingPlanSection(
            slot_id="second",
            display_title="Second section",
            entry_state=["Learner recalls the first idea"],
            must_establish=["The second idea"],
            avoid_repeating=[],
            bridge_from_previous="Connect the first idea",
            exit_state=["Learner can state the second idea"],
            blocks=[
                TeachingPlanBlock(
                    id="block-c",
                    position=0,
                    intent="Extend the idea",
                    brief="Extend the idea",
                    evidence="Learner can state the second idea",
                    sourcebook_refs=["entry-b"],
                )
            ],
        ),
    ]
    plan = TeachingPlan(
        arc="Connect two ideas",
        contract_version=2,
        learner_title="Connected ideas",
        starting_state=["Learner is ready"],
        target_state=["Learner can connect the ideas"],
        teaching_plan_id="source-plan",
        revision=4,
        sections=sections,
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision,
        status="approved",
        preparation_hash="p" * 64,
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-25T00:00:00Z",
        approved_at="2026-09-25T00:00:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan.teaching_plan_id,
        revision=plan.revision,
        content_hash=digest,
    )


def _inputs(
    source: TeachingPlanSource | None = None,
    *,
    entries: list[SourcebookEntry] | None = None,
) -> VerifiedSemanticInputs:
    source = source or _source()
    sourcebook = LessonSourcebook(
        teaching_plan_id=source.id,
        teaching_plan_revision=source.revision,
        teaching_plan_hash=source.content_hash,
        entries=(
            entries
            if entries is not None
            else [
                SourcebookEntry(
                    id="entry-a",
                    type="definition",
                    purpose="Name the first idea",
                    content={
                        "unicode": "café π",
                        "numbers": [1, 2.5, -3],
                        "nested": {"items": ["one", {"value": 4}]},
                    },
                    provenance_refs=["approved-book-1"],
                ),
                SourcebookEntry(
                    id="entry-b",
                    type="quantitative_example",
                    purpose="Show the second idea",
                    content={"value": 12, "unit": "kg"},
                    provenance_refs=["approved-book-2"],
                ),
            ]
        ),
    )
    return VerifiedSemanticInputs(
        run_id="run-1",
        owner_user_id="owner-1",
        source=source,
        sourcebook=sourcebook,
        tasks=(),
        sourcebook_output_hash=content_hash(sourcebook.model_dump(mode="json")),
        task_output_hash="a" * 64,
        work_item_ids={"sourcebook": "item-sourcebook", "shared_tasks": "item-tasks"},
    )


def test_builds_canonical_ordered_sources_and_dedupes_within_section() -> None:
    inputs = _inputs()

    result = build_section_sources(inputs, inputs.source.plan.sections[0])

    assert [source.id for source in result] == ["entry-a", "entry-b"]
    assert all(source.kind == "sourcebook_entry" for source in result)
    assert result[0].text == (
        '{"content":{"nested":{"items":["one",{"value":4}]},'
        '"numbers":[1,2.5,-3],"unicode":"café π"},'
        '"provenance_refs":["approved-book-1"],"purpose":"Name the first idea",'
        '"type":"definition"}'
    )
    assert json.loads(result[0].text)["content"]["unicode"] == "café π"


def test_same_entry_can_be_scoped_to_another_approved_section() -> None:
    inputs = _inputs()

    first = build_section_sources(inputs, inputs.source.plan.sections[0])
    second = build_section_sources(inputs, inputs.source.plan.sections[1])

    assert [source.id for source in first] == ["entry-a", "entry-b"]
    assert [source.id for source in second] == ["entry-b"]
    assert second[0] == first[1]


def test_source_text_is_deterministic_and_changes_with_unicode_content() -> None:
    inputs = _inputs()
    section = inputs.source.plan.sections[0]

    first = build_section_sources(inputs, section)
    second = build_section_sources(inputs, section)
    assert first == second
    assert content_hash([source.model_dump(mode="json") for source in first]) == content_hash(
        [source.model_dump(mode="json") for source in second]
    )

    changed = deepcopy(inputs.sourcebook.entries[0])
    changed.content["unicode"] = "café π"
    changed_entries = [changed, inputs.sourcebook.entries[1]]
    changed_inputs = _inputs(entries=changed_entries)
    assert build_section_sources(changed_inputs, section)[0].text != first[0].text


@pytest.mark.parametrize(
    "entries, message",
    [
        ([], "missing sourcebook entry"),
        (
            [
                SourcebookEntry(
                    id="entry-a",
                    type="definition",
                    purpose="A",
                    content={},
                    provenance_refs=["book"],
                ),
                SourcebookEntry(
                    id="entry-b",
                    type="definition",
                    purpose="B",
                    content={"ok": True},
                    provenance_refs=["book"],
                ),
            ],
            "empty content",
        ),
        (
            [
                SourcebookEntry(
                    id="entry-a",
                    type="definition",
                    purpose="A",
                    content={"bad": float("nan")},
                    provenance_refs=["book"],
                ),
                SourcebookEntry(
                    id="entry-b",
                    type="definition",
                    purpose="B",
                    content={"ok": True},
                    provenance_refs=["book"],
                ),
            ],
            "non-finite",
        ),
    ],
)
def test_rejects_missing_empty_and_non_finite_content(
    entries: list[SourcebookEntry], message: str
) -> None:
    inputs = _inputs(entries=entries)

    with pytest.raises(SectionSourceError, match=message):
        build_section_sources(inputs, inputs.source.plan.sections[0])


def test_rejects_non_json_content_after_durable_validation() -> None:
    inputs = _inputs()
    inputs.sourcebook.entries[0].content["bad"] = object()

    with pytest.raises(SectionSourceError, match="non-JSON"):
        build_section_sources(inputs, inputs.source.plan.sections[0])


def test_rejects_duplicate_entry_ids() -> None:
    source = _source()
    entry = SourcebookEntry(
        id="entry-a",
        type="definition",
        purpose="Duplicate",
        content={"ok": True},
        provenance_refs=["book"],
    )
    inputs = _inputs(
        entries=[
            entry,
            entry.model_copy(),
            SourcebookEntry(
                id="entry-b",
                type="definition",
                purpose="B",
                content={"ok": True},
                provenance_refs=["book"],
            ),
        ]
    )

    with pytest.raises(SectionSourceError, match="duplicated"):
        build_section_sources(inputs, source.plan.sections[0])


def test_rejects_stale_sourcebook_lineage_and_output_hash() -> None:
    inputs = _inputs()
    inputs.sourcebook.teaching_plan_hash = "b" * 64
    with pytest.raises(SectionSourceError, match="stale"):
        build_section_sources(inputs, inputs.source.plan.sections[0])

    inputs = _inputs()
    object.__setattr__(inputs, "sourcebook_output_hash", "b" * 64)
    with pytest.raises(SectionSourceError, match="output hash"):
        build_section_sources(inputs, inputs.source.plan.sections[0])


def test_rejects_section_outside_or_different_from_approved_snapshot() -> None:
    inputs = _inputs()
    outside = inputs.source.plan.sections[0].model_copy(update={"slot_id": "other"})

    with pytest.raises(SectionSourceError, match="not uniquely present"):
        build_section_sources(inputs, outside)

    altered = inputs.source.plan.sections[0].model_copy(deep=True)
    altered.blocks[0].brief = "Changed after approval"
    with pytest.raises(SectionSourceError, match="differs"):
        build_section_sources(inputs, altered)

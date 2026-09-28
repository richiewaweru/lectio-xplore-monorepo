"""Shared fixture builder for P10C publish/runtime tests.

Builds a READY SharedLessonDocument with one task per Learn interaction kind
the adapter can emit (choice, classify, short-response/teacher-review,
match-pairs, sequence, fill-blank), realizes it through the real
``realize_shared_document_for_learn`` adapter (no HTTP/worker pipeline), and
seeds the minimum durable rows a publish/runtime test needs: the
SharedLessonDocument's owning PathLesson chain and a SharedDocument-stamped
``EditableLessonModel`` ready to publish.

Deliberately bypasses ``SharedDocumentWorker``/``run_post_section_pipeline``
(P10B's full admission pipeline) since publish/runtime tests only need a
durable, hash-verifiable shared document and a lesson stamped with its
identity — not a live generation run.
"""

from __future__ import annotations

from datetime import UTC, datetime

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.models import (
    ParagraphDisplay,
    ParagraphNode,
    SharedSection,
    TaskAnchor,
    build_shared_lesson_document,
)
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.database.models import (
    ConceptModel,
    EditableLessonModel,
    PathLessonModel,
    PathVersionModel,
    SharedLessonDocumentModel,
    UnitModel,
    UserModel,
)
from infra.execution.checkpoints import content_hash
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity,
    realize_shared_document_for_learn,
)

TEACHING_PLAN_ID = "p10c-plan"
TEACHING_PLAN_REVISION = 1
TEACHING_PLAN_HASH = "a" * 64


def _task(
    *,
    task_id: str,
    teaching_block_id: str,
    action: str,
    prompt: str,
    response: dict,
    evaluation: dict,
) -> SharedTaskSpec:
    return SharedTaskSpec(
        id=task_id,
        teaching_plan_id=TEACHING_PLAN_ID,
        teaching_plan_revision=TEACHING_PLAN_REVISION,
        teaching_plan_hash=TEACHING_PLAN_HASH,
        teaching_block_id=teaching_block_id,
        mode="assessment",
        action=action,
        purpose="Check understanding",
        prompt=prompt,
        difficulty="guided",
        expected_evidence="A supported response",
        response=response,
        evaluation=evaluation,
    )


def _all_tasks() -> list[SharedTaskSpec]:
    return [
        _task(
            task_id="task-choice",
            teaching_block_id="block-choice",
            action="select-one",
            prompt="Which option is supported?",
            response={
                "type": "single_choice",
                "options": [
                    {"id": "a", "text": "First"},
                    {"id": "b", "text": "Second"},
                ],
            },
            evaluation={"type": "exact_match", "correct_option_id": "b"},
        ),
        _task(
            task_id="task-classify",
            teaching_block_id="block-classify",
            action="classify-items",
            prompt="Place each example in its group.",
            response={
                "type": "classification",
                "items": ["a", "b"],
                "categories": ["g1", "g2"],
                "correct_placements": {"a": "g1", "b": "g2"},
            },
            evaluation={"type": "mapping", "correct_placements": {"a": "g1", "b": "g2"}},
        ),
        _task(
            task_id="task-review",
            teaching_block_id="block-review",
            action="enter-text",
            prompt="Explain your reasoning.",
            response={"type": "text", "min_length": 1},
            evaluation={"type": "teacher_review", "review_guidance": "Check the reasoning."},
        ),
        _task(
            task_id="task-match",
            teaching_block_id="block-match",
            action="match-pairs",
            prompt="Match each term to its definition.",
            response={"type": "matching", "pairs": [{"left": "Sun", "right": "Star"}]},
            evaluation={"type": "mapping", "pairs": [{"left": "Sun", "right": "Star"}]},
        ),
        _task(
            task_id="task-sequence",
            teaching_block_id="block-sequence",
            action="order-items",
            prompt="Put the stages in order.",
            response={
                "type": "ordered_items",
                "items": ["egg", "larva", "pupa", "adult"],
                "correct_order": ["egg", "larva", "pupa", "adult"],
            },
            evaluation={"type": "ordered_match", "correct_order": ["egg", "larva", "pupa", "adult"]},
        ),
        _task(
            task_id="task-fill-blank",
            teaching_block_id="block-fill-blank",
            action="complete-missing-values",
            prompt="Fill in the missing value.",
            response={"type": "missing_values", "values": ["Paris"]},
            evaluation={"type": "accepted_answers", "accepted_answers": ["Paris"]},
        ),
    ]


def build_rich_shared_document(document_id: str, *, revision: int = 1):
    """A READY SharedLessonDocument with one task per adapter interaction kind."""
    tasks = _all_tasks()
    nodes = [
        ParagraphNode(
            id="paragraph-1",
            teaching_block_id="block-intro",
            display=ParagraphDisplay(text="Shared authored prose."),
        ),
    ]
    for task in tasks:
        nodes.append(
            TaskAnchor(
                id=f"anchor-{task.id}",
                task_spec_id=task.id,
                teaching_block_id=task.teaching_block_id,
            )
        )
    sections = [SharedSection(id="section-1", title="Practice", position=0, nodes=tuple(nodes))]
    return build_shared_lesson_document(
        {
            "id": document_id,
            "revision": revision,
            "teaching_plan_id": TEACHING_PLAN_ID,
            "teaching_plan_revision": TEACHING_PLAN_REVISION,
            "teaching_plan_hash": TEACHING_PLAN_HASH,
            "title": "Rich practice lesson",
            "sections": sections,
            "tasks": [task.model_dump(mode="json") for task in tasks],
            "created_at": datetime(2026, 9, 28, 9, 0, tzinfo=UTC),
        }
    )


async def seed_ready_shared_document_lesson(
    db_session_factory,
    *,
    owner_id: str,
    suffix: str,
) -> dict:
    """Seed a READY SharedLessonDocument + a stamped, publishable EditableLessonModel.

    Returns identity/ids a test needs: ``lesson_id``, ``document_id``,
    ``revision``, ``content_hash``, and the interaction node id for every
    adapter interaction kind (keyed by ``interaction_type``).
    """
    document_id = f"p10c-shared-{suffix}"
    document = build_rich_shared_document(document_id)
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id=f"p10c-path-lesson-{suffix}",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )
    identity = SharedDocumentIdentity(
        id=document.id, revision=document.revision, content_hash=document.content_hash
    )
    lesson_id = f"p10c-lesson-{suffix}"
    realized = realize_shared_document_for_learn(
        stored,
        expected_identity=identity,
        subject="general",
        source_generation_id=None,
        learn_document_id=lesson_id,
    )
    learn_document = dict(realized.document.model_dump(mode="json"))
    now = datetime.now(UTC).replace(tzinfo=None)
    learn_document["id"] = lesson_id
    learn_document["created_at"] = now.isoformat() + "Z"
    learn_document["updated_at"] = now.isoformat() + "Z"

    interaction_ids: dict[str, str] = {
        node["interaction_type"]: node["id"]
        for node in learn_document["nodes"]
        if node.get("kind") == "interaction"
    }
    section_id = learn_document["sections"][0]["id"]

    async with db_session_factory() as session:
        rows_to_add: list[object] = []
        if await session.get(UserModel, owner_id) is None:
            rows_to_add.append(UserModel(id=owner_id, email=f"{owner_id}@example.invalid"))
        concept = ConceptModel(
            id=f"p10c-concept-{suffix}",
            canonical_slug=f"p10c.{suffix}",
            subject="Science",
            title="P10C fixture",
            created_by=owner_id,
        )
        unit = UnitModel(
            id=f"p10c-unit-{suffix}",
            owner_id=owner_id,
            title="P10C fixture",
            topic="Practice",
            subject="Science",
            grade_level="Grade 7",
            destination_objective="Practice every interaction kind.",
        )
        version = PathVersionModel(
            id=f"p10c-path-version-{suffix}",
            unit_id=unit.id,
            version=1,
            source_plan_json={},
        )
        path_lesson = PathLessonModel(
            id=stored.path_lesson_id,
            path_version_id=version.id,
            concept_id=concept.id,
            concept_slug=concept.canonical_slug,
            title="P10C fixture",
            objective="Practice every interaction kind.",
            objective_hash="p10c-objective",
            primary_knowledge_type="conceptual",
            position=0,
        )
        shared_row = SharedLessonDocumentModel(
            id=document.id,
            revision=document.revision,
            path_lesson_id=stored.path_lesson_id,
            teaching_plan_id=document.teaching_plan_id,
            teaching_plan_revision=document.teaching_plan_revision,
            teaching_plan_hash=document.teaching_plan_hash,
            content_hash=document.content_hash,
            document_json=document.model_dump(mode="json"),
            status="ready",
        )
        editable = EditableLessonModel(
            id=lesson_id,
            user_id=owner_id,
            source_generation_id=None,
            source_type="learn_document",
            title="Rich practice lesson",
            class_label=None,
            document_json=learn_document,
            created_at=now,
            updated_at=now,
            shared_document_run_id=f"p10c-run-{suffix}",
            shared_document_id=document.id,
            shared_document_revision=document.revision,
            shared_document_hash=document.content_hash,
        )
        rows_to_add.extend([concept, unit, version, path_lesson, shared_row, editable])
        session.add_all(rows_to_add)
        await session.commit()

    return {
        "lesson_id": lesson_id,
        "document_id": document.id,
        "revision": document.revision,
        "content_hash": document.content_hash,
        "learn_document": learn_document,
        "section_id": section_id,
        "interaction_ids": interaction_ids,
    }


__all__ = [
    "build_rich_shared_document",
    "seed_ready_shared_document_lesson",
]

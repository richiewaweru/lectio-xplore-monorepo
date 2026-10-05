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
from infra.execution.checkpoints import content_hash
from print.generation.shared_document_adapter import SharedDocumentIdentity, realize_shared_document_for_print


def _task(task_id: str, **overrides) -> SharedTaskSpec:
    base = dict(
        id=task_id,
        teaching_plan_id="plan-1",
        teaching_plan_revision=2,
        teaching_plan_hash="b" * 64,
        teaching_block_id="block-1",
        mode="formative",
        purpose="Check understanding",
        difficulty="guided",
        role="practice",
    )
    base.update(overrides)
    return SharedTaskSpec(**base)


PAIRS = [
    {"left": "water", "right": "comes up from the roots"},
    {"left": "carbon dioxide", "right": "enters from the air"},
    {"left": "light", "right": "is captured by the leaves"},
]


def _match_task() -> SharedTaskSpec:
    return _task(
        "t-match",
        action="match-pairs",
        prompt="Match each input to its route.",
        display_prompt="Match each input to its route.",
        expected_evidence="Each input is matched to its route",
        response={"type": "matching", "pairs": PAIRS},
        evaluation={"type": "mapping", "pairs": PAIRS},
        feedback={"correct": "Right.", "incorrect": "Look again."},
    )


def _text_task() -> SharedTaskSpec:
    return _task(
        "t-text",
        action="enter-text",
        prompt="Explain why the plant grew.",
        expected_evidence="The learner names light as the missing input.",
        response={"type": "text"},
        evaluation={"type": "teacher_review", "review_guidance": "Look for light."},
        feedback={"correct": "Good.", "incorrect": "Try again."},
    )


def _choice_task() -> SharedTaskSpec:
    return _task(
        "t-choice",
        mode="assessment",
        role="check",
        action="select-one",
        prompt="Which is right?",
        expected_evidence="Select the supported option",
        response={
            "type": "single_choice",
            "options": [{"id": "a", "text": "First"}, {"id": "opt-b", "text": "Second"}, {"id": "c", "text": "Third"}],
        },
        evaluation={"type": "exact_match", "correct_option_id": "a"},
        feedback={"correct": "Yes.", "incorrect": "No."},
        option_notes={
            "opt-b": "Treats water as the food, the soil/water misconception (m1).",
            "c": "Confuses (opt-b) with the answer (m2).",
        },
    )


def _realize() -> dict:
    tasks = [_match_task(), _text_task(), _choice_task()]
    nodes = [
        ParagraphNode(id="p-1", teaching_block_id="block-1", display=ParagraphDisplay(text="Intro.")),
        *[TaskAnchor(id=f"anchor-{i}", task_spec_id=t.id, teaching_block_id="block-1") for i, t in enumerate(tasks)],
    ]
    document = build_shared_lesson_document(
        {
            "id": "shared-proj",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 2,
            "teaching_plan_hash": "b" * 64,
            "title": "Projection lesson",
            "sections": [SharedSection(id="s-1", title="Section", position=0, nodes=tuple(nodes))],
            "tasks": [t.model_dump(mode="json") for t in tasks],
            "created_at": datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        }
    )
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id="path-proj",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )
    identity = SharedDocumentIdentity(document.id, document.revision, document.content_hash)
    return realize_shared_document_for_print(stored, expected_identity=identity).document


def _text(runs) -> str:
    return "".join(run.get("value", "") for run in runs)


def _entries(doc: dict) -> dict[str, dict]:
    return {e["question_id"]: e for g in doc["answer_key"]["content"]["groups"] for e in g["entries"]}


def test_match_pairs_print_as_numbered_and_lettered_columns() -> None:
    doc = _realize()
    block = next(b for b in doc["sections"][0]["blocks"] if b["id"] == "Q1")
    item = block["content"]["items"][0]
    assert item["answer_lines"] == 0
    assert [_text(x) for x in item["match"]["left"]] == [p["left"] for p in PAIRS]
    right = [_text(x) for x in item["match"]["right"]]
    assert sorted(right) == sorted(p["right"] for p in PAIRS)
    # The run-on prompt is gone: the prompt is the writer's wording only.
    assert _text(item["prompt"]) == "Match each input to its route."
    assert "Possible matches" not in str(item)
    # No row lines up with its own answer, so the columns do not give the key away.
    assert all(right[i] != PAIRS[i]["right"] for i in range(len(PAIRS)))


def test_match_pairs_teacher_answer_uses_displayed_numbers_and_letters() -> None:
    doc = _realize()
    item = next(b for b in doc["sections"][0]["blocks"] if b["id"] == "Q1")["content"]["items"][0]
    right = [_text(x) for x in item["match"]["right"]]
    answer = _text(_entries(doc)["Q1"]["answer"])
    for number, pair in enumerate(PAIRS, start=1):
        letter = chr(65 + right.index(pair["right"]))
        assert f"{number} ({pair['left']}) \u2192 {letter} ({pair['right']})" in answer


def test_teacher_rubric_is_omitted_when_it_repeats_the_answer() -> None:
    entry = _entries(_realize())["Q2"]
    assert _text(entry["answer"]) == "The learner names light as the missing input."
    assert "rubric" not in entry


def test_teacher_option_notes_show_displayed_labels_and_no_plan_ids() -> None:
    notes = _entries(_realize())["Q3"]["option_notes"]
    assert set(notes) == {"B", "C"}
    assert _text(notes["B"]) == "Treats water as the food, the soil/water misconception."
    assert _text(notes["C"]) == "Confuses (B) with the answer."
    assert "(m" not in str(notes)

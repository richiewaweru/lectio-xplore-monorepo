from document.shared_lesson.fixtures import load_shared_lesson_fixture
from document.shared_lesson.models import CompareDisplay, CompareItem, EquationDisplay


def test_golden_fixture_covers_every_phase_zero_node_and_task_shape() -> None:
    document = load_shared_lesson_fixture("golden")

    assert document.title == "How Plants Get the Energy to Grow"
    assert [section.id for section in document.sections] == ["orient", "explain", "contrast", "check"]
    kinds = {node.kind for section in document.sections for node in section.nodes}
    assert kinds == {
        "heading",
        "paragraph",
        "list",
        "quote",
        "compare",
        "task_anchor",
        "callout",
        "equation",
        "table",
        "figure",
    }
    assert {task.role for task in document.tasks} == {"predict", "check"}
    assert document.tasks[0].feedback == {"saved": "Prediction saved. Keep it in mind — Part 2 will test it."}
    assert document.tasks[0].option_notes == {"soil": "The evidence will test this idea."}


def test_overlong_fixture_is_loaded_without_truncation() -> None:
    document = load_shared_lesson_fixture("overlong")
    paragraph = next(
        node for node in document.sections[0].nodes if node.kind == "paragraph"
    )
    text = paragraph.display.text  # type: ignore[union-attr]

    assert len(text.split()) > 100
    assert text.count("This controlled comparison makes it possible") == 2
    assert text.count("Two pots are set up to be compared.") == 2
    assert {node.kind for section in document.sections for node in section.nodes} == {
        node.kind for section in load_shared_lesson_fixture("golden").sections for node in section.nodes
    }


def test_legacy_fixture_keeps_the_stored_content_hash() -> None:
    document = load_shared_lesson_fixture("legacy")

    assert document.content_hash == "44ab7dbe3e048881eda5d6fd15062b82a7a13394b87c66a9a63e2a4706fd3b6b"


def test_new_absent_defaults_are_omitted_from_serialization() -> None:
    document = load_shared_lesson_fixture("legacy")
    payload = document.model_dump(mode="json")
    callout_payloads = [
        node["display"]
        for section in payload["sections"]
        for node in section["nodes"]
        if node["kind"] == "callout"
    ]
    assert all("variant" not in callout for callout in callout_payloads)
    assert all("role" not in task and "display_prompt" not in task for task in payload["tasks"])


def test_shape_targets_are_advisory_and_preserve_oversized_content() -> None:
    equation = EquationDisplay(
        inputs=("one", "two", "three", "four", "five"),
        outputs=("a", "b", "c", "d"),
    )
    comparison = CompareDisplay(
        items=tuple(
            CompareItem(title=f"Option {index}", body="Preserve this card.")
            for index in range(1, 5)
        )
    )

    assert len(equation.inputs) == 5
    assert len(equation.outputs) == 4
    assert len(comparison.items) == 4

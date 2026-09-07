"""Phase 09/10: mocked Component Lectio E2E across four subjects."""

from __future__ import annotations

from learn.generation.component_lectio.pipeline import run_mocked_component_lectio_pipeline
from tests.v3_blueprint.planning.test_intent_plan import SUBJECT_FIXTURES, _intent_plan_for_subject


def test_mocked_e2e_four_subjects_no_studio() -> None:
    for fixture in SUBJECT_FIXTURES:
        intent = _intent_plan_for_subject(**fixture)
        result = run_mocked_component_lectio_pipeline(
            intent,
            title=f"{fixture['subject']}-{fixture['topic']}",
            generation_id=f"gen-{fixture['subject']}",
        )
        assert result.document["version"] == 1
        assert result.document["id"]
        assert result.document["blocks"]
        from v3_execution.runtime.lesson_document import lesson_is_partial

        assert lesson_is_partial(result.canonical, result.store) is False
        assert result.store.control.state == "complete"
        assert result.work_orders
        assert all(
            order.locked_component_id == order.component_id for order in result.work_orders
        )
        # No Studio artifacts.
        assert "v3_pack" not in result.document
        assert "studio" not in result.document


def test_mocked_e2e_injects_validation_failure_and_repairs() -> None:
    intent = _intent_plan_for_subject(**SUBJECT_FIXTURES[1])
    # Build first so we know block ids after selection.
    probe = run_mocked_component_lectio_pipeline(intent, title="probe", generation_id="probe")
    target = probe.work_orders[0].block_id

    def flaky_writer(order):
        if order.block_id == target and not getattr(flaky_writer, "_failed", False):
            flaky_writer._failed = True  # type: ignore[attr-defined]
            raise ValueError("lectio validation failed on comparison payload")
        from learn.generation.component_lectio.pipeline import mock_writer

        return mock_writer(order)

    result = run_mocked_component_lectio_pipeline(
        intent,
        title="science-repair",
        generation_id="gen-repair",
        writer=flaky_writer,
    )
    assert any(event.get("action") == "repair" for event in result.events if event["type"] == "failure")
    from v3_execution.runtime.lesson_document import lesson_is_partial

    assert lesson_is_partial(result.canonical, result.store) is False
    assert target in result.document["blocks"]


def test_phase09_canonical_path_does_not_import_studio_router() -> None:
    import learn.generation.component_lectio.pipeline as pipeline

    source = open(pipeline.__file__, encoding="utf-8").read()
    assert "from_generation" not in source

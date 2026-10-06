from __future__ import annotations

import pytest

from document.shared_lesson.media import (
    BoundUnavailableFigureMedia,
    FigureMediaResult,
    SharedFigureMediaError,
    UnavailableFigureMediaResult,
    bind_durable_media_outcome,
    bind_generated_figure,
    is_unavailable_media,
    parse_media_outcome,
    unavailable_figure_result,
    verify_bound_media_outcome,
)
from tests.document.test_shared_lesson_media import _block, _document, _work


def _unavailable(work=None) -> UnavailableFigureMediaResult:
    return unavailable_figure_result(
        work or _work(),
        error_code="render_spec_invalid",
        reason="Figure drawing failed: the figure description could not be made consistent.",
        attempts=3,
    )


def test_unavailable_result_keeps_figure_identity_and_a_teacher_safe_reason() -> None:
    work = _work()
    result = _unavailable(work)
    assert result.status == "unavailable"
    assert result.figure_node_id == work.figure_node_id
    assert result.figure_semantic_hash == work.figure_semantic_hash
    assert result.work_order_id == work.work_order.work_order_id
    assert result.alt_text.strip()
    assert result.attempts == 3


def test_durable_payload_round_trips_and_binds_to_the_document() -> None:
    document = _document()
    payload = _unavailable().model_dump(mode="json")
    assert isinstance(parse_media_outcome(payload), UnavailableFigureMediaResult)
    bound = bind_durable_media_outcome(payload, document)
    assert isinstance(bound, BoundUnavailableFigureMedia)
    assert bound.source_document_hash == document.content_hash
    assert verify_bound_media_outcome(bound, document) == bound
    assert is_unavailable_media(bound)


def test_ready_payload_still_binds_through_the_outcome_parser() -> None:
    work = _work()
    document = _document()
    ready = bind_generated_figure(work, [_block(work)])
    bound = bind_durable_media_outcome(ready.model_dump(mode="json"), document)
    assert isinstance(bound, FigureMediaResult)
    assert not is_unavailable_media(bound)
    assert verify_bound_media_outcome(bound, document) == bound


@pytest.mark.parametrize(
    "update",
    [
        {"figure_semantic_hash": "0" * 64},
        {"work_order_id": "shared-media-" + "0" * 64},
        {"section_output_hash": "1" * 64},
    ],
)
def test_unavailable_outcome_with_changed_identity_is_rejected(update) -> None:
    payload = _unavailable().model_copy(update=update).model_dump(mode="json")
    with pytest.raises(SharedFigureMediaError):
        bind_durable_media_outcome(payload, _document())


def test_bound_unavailable_outcome_rejects_a_stale_document() -> None:
    document = _document()
    bound = bind_durable_media_outcome(_unavailable().model_dump(mode="json"), document)
    tampered = bound.model_copy(update={"source_document_hash": "2" * 64})
    with pytest.raises(SharedFigureMediaError):
        verify_bound_media_outcome(tampered, document)


def test_unavailable_outcome_requires_reason_and_attempts() -> None:
    data = _unavailable().model_dump(mode="json")
    with pytest.raises(ValueError):
        UnavailableFigureMediaResult.model_validate({**data, "reason": ""})
    with pytest.raises(ValueError):
        UnavailableFigureMediaResult.model_validate({**data, "attempts": 0})
    with pytest.raises(ValueError):
        UnavailableFigureMediaResult.model_validate({**data, "asset_url": "https://x"})


def test_orders_admitted_before_numbered_labels_still_verify_on_resume() -> None:
    from document.shared_lesson.media_runtime import MediaSourceConflict, _verify_accepted_section
    from tests.document.test_shared_lesson_media import _section, _source

    work = _work()
    assert work.work_order.visual.visual_style == "diagram_numbered"
    visual = work.work_order.visual.model_copy(update={"visual_style": None})
    legacy = work.model_copy(
        update={"work_order": work.work_order.model_copy(update={"visual": visual})}
    )
    section = _section("section-a", 0)
    _verify_accepted_section(legacy, section, _source())  # tolerated
    _verify_accepted_section(work, section, _source())
    forged = work.model_copy(
        update={
            "work_order": work.work_order.model_copy(
                update={"visual": visual.model_copy(update={"purpose": "Something else"})}
            )
        }
    )
    with pytest.raises(MediaSourceConflict):
        _verify_accepted_section(forged, section, _source())

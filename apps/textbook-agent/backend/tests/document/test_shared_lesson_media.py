from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from document.shared_lesson.media import (
    SharedFigureMediaError,
    bind_generated_figure,
    build_figure_work_order,
    execute_figure_work_orders,
    validate_reusable_figure_asset,
)
from document.shared_lesson.models import build_shared_lesson_document
from media.generation.contracts import GeneratedVisualBlock


def _payload() -> dict[str, object]:
    return {
        "id": "shared-media-lesson",
        "revision": 1,
        "teaching_plan_id": "plan-1",
        "teaching_plan_revision": 1,
        "teaching_plan_hash": "a" * 64,
        "title": "Plant energy",
        "sections": [
            {
                "id": "section-a",
                "title": "The energy source",
                "position": 0,
                "nodes": [
                    {
                        "id": "figure-a",
                        "kind": "figure",
                        "display": {"caption": "A leaf in sunlight"},
                        "accessibility": {"alt_text": "A leaf receiving sunlight"},
                    }
                ],
            },
            {
                "id": "section-b",
                "title": "The process",
                "position": 1,
                "nodes": [
                    {
                        "id": "figure-b",
                        "kind": "figure",
                        "display": {"caption": "A simple process diagram"},
                        "accessibility": {"alt_text": "Arrows show energy moving through a leaf"},
                    }
                ],
            },
        ],
        "created_at": "2026-09-24T09:00:00+03:00",
    }


def _document():
    return build_shared_lesson_document(_payload())


def _works():
    document = _document()
    return document, (
        build_figure_work_order(
            document,
            section_id="section-a",
            figure_node_id="figure-a",
            approved_source_facts={"fact-light": "Light supplies energy."},
        ),
        build_figure_work_order(
            document,
            section_id="section-b",
            figure_node_id="figure-b",
            approved_source_facts=("Energy moves through the leaf.",),
        ),
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


def test_work_order_freezes_caption_alt_source_facts_and_identity() -> None:
    document, works = _works()
    work = works[0]

    assert work.source_document_id == document.id
    assert work.source_document_hash == document.content_hash
    assert work.work_order.visual.purpose == "A leaf in sunlight"
    assert work.work_order.visual.must_show == ["A leaf receiving sunlight"]
    assert work.work_order.source_of_truth[0].key == "fact-light"
    assert work.work_order.source_of_truth[0].text == "Light supplies energy."
    assert work.work_order.work_order_id.startswith("shared-media-")


def test_ready_media_binding_does_not_mutate_shared_document() -> None:
    document, works = _works()
    result = bind_generated_figure(works[0], [_block(works[0])])

    assert result.asset_id == works[0].work_order.visual.id
    assert result.asset_url == "https://cdn.example.test/image.png"
    assert document.sections[0].nodes[0].display.asset_id is None


def test_bad_hosted_asset_is_rejected() -> None:
    _, works = _works()

    with pytest.raises(SharedFigureMediaError, match="hosted media"):
        bind_generated_figure(works[0], [_block(works[0], url="file:///local.png")])


def test_independent_figures_run_concurrently() -> None:
    _, works = _works()

    class Executor:
        active = 0
        maximum = 0

        async def execute_figure(self, order):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            await asyncio.sleep(0.02)
            self.active -= 1
            work = next(item for item in works if item.work_order == order)
            return [_block(work)]

    executor = Executor()
    batch = asyncio.run(execute_figure_work_orders(works, executor=executor, concurrency=2))

    assert batch.ready
    assert len(batch.results) == 2
    assert not batch.failures
    assert executor.maximum == 2


def test_required_failure_blocks_media_ready_but_healthy_sibling_survives() -> None:
    _, works = _works()

    class Executor:
        async def execute_figure(self, order):
            if order.visual.attaches_to == "figure-a":
                raise RuntimeError("provider unavailable")
            work = works[1]
            return [_block(work)]

    batch = asyncio.run(execute_figure_work_orders(works, executor=Executor()))

    assert not batch.ready
    assert [result.figure_node_id for result in batch.results] == ["figure-b"]
    assert batch.failures[0].figure_node_id == "figure-a"
    assert batch.failures[0].required


def test_targeted_retry_preserves_healthy_sibling_output() -> None:
    _, works = _works()
    healthy = _block(works[1])
    attempts = {"figure-a": 0}

    class Executor:
        async def execute_figure(self, order):
            if order.visual.attaches_to == "figure-a":
                attempts["figure-a"] += 1
                if attempts["figure-a"] == 1:
                    raise RuntimeError("temporary provider error")
                return [_block(works[0])]
            return [healthy]

    executor = Executor()
    first = asyncio.run(execute_figure_work_orders(works, executor=executor))
    retry = asyncio.run(execute_figure_work_orders((works[0],), executor=executor))

    assert first.results == (bind_generated_figure(works[1], [healthy]),)
    assert retry.ready
    assert retry.results[0].figure_node_id == "figure-a"
    assert attempts["figure-a"] == 2


def test_stale_or_conflicting_figure_reuse_is_rejected() -> None:
    _, works = _works()
    result = bind_generated_figure(works[0], [_block(works[0])])
    stale = result.model_copy(update={"figure_semantic_hash": "b" * 64})

    with pytest.raises(SharedFigureMediaError, match="stale"):
        validate_reusable_figure_asset(works[0], stale)
    with pytest.raises(SharedFigureMediaError, match="stale"):
        validate_reusable_figure_asset(
            works[0],
            result.model_copy(update={"source_document_hash": "b" * 64}),
        )
    with pytest.raises(SharedFigureMediaError, match="hosted URL"):
        validate_reusable_figure_asset(
            works[0],
            result.model_copy(update={"asset_url": "not-a-url"}),
        )


def test_existing_asset_cannot_be_reused_for_new_work_order() -> None:
    payload = deepcopy(_payload())
    payload["sections"][0]["nodes"][0]["display"]["asset_id"] = "asset-existing"
    document = build_shared_lesson_document(payload)

    with pytest.raises(SharedFigureMediaError, match="already has a bound asset"):
        build_figure_work_order(
            document,
            section_id="section-a",
            figure_node_id="figure-a",
        )

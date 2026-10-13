"""Figure data integrity at the media boundary (doc 37, tests 1, 5, 6, 7, 12).

A figure whose plan carries series data is drawn from that data in code and is
never handed to the image model; a data figure that cannot be drawn fails with
``figure_data_not_rendered``; scalar-only data still goes to the image path.
"""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from application.unit_lesson.staged_teaching_planner import copy_backbone_figures
from curriculum.figure_progress import project_figures
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
    VisualSpec,
)
from document.shared_lesson import figure_executor_adapter
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.figure_executor_adapter import (
    RoutingFigureExecutor,
    SharedFigureExecutorAdapter,
)
from document.shared_lesson.media import (
    SharedFigureMediaProviderFailed,
    bind_generated_figure,
    build_figure_work_order,
)
from document.shared_lesson.media_runtime import execute_figure_media_work_item
from document.shared_lesson.models import SharedSection
from document.shared_lesson.runtime import TeachingPlanSource
from infra.database.models import GenerationWorkItemModel
from infra.generation_runtime.http import _RETRYABLE_ERROR_CLASSES
from media.generation.contracts import (
    GeneratedVisualBlock,
    SourceOfTruthEntry,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
)
from media.generation.prompt import build_visual_prompt
from media.render.contracts import BarChartSpec, RenderSpecResult, TableSpec
from media.storage.image_store import LocalImageStore
from tests.document.test_shared_lesson_media_runtime import _failed_provider_block
from tests.document.test_shared_lesson_media_runtime import _work as runtime_work
from tests.document.test_shared_lesson_unavailable_pipeline import _admit, _job
from tests.planning.test_backbone_figure_link import _packet

RUN_ID = "ec975a04-7adc-42b4-959b-79068ece697d"
ADAPTER_LOGGER = "document.shared_lesson.figure_executor_adapter"

FIG2 = {
    "id": "fig-2",
    "purpose": "Compare the growth of the two seedlings week by week.",
    "must_show": [
        "A table with rows Day 0, Day 7, Day 14, Day 21, Day 28 and columns for "
        "Seedling A and Seedling B height"
    ],
    "labels_required": ["Day", "Height of Seedling A (cm)", "Height of Seedling B (cm)"],
    "mode": "diagram",
    "data": {
        "days": [0, 7, 14, 21, 28],
        "height_seedling_a_cm": [5, 12, 22, 35, 48],
        "height_seedling_b_cm": [5, 6, 7, 8, 9],
    },
}
FIG1 = {
    "id": "fig-1",
    "purpose": "Show the two seedlings on day 0 and day 28.",
    "must_show": ["Seedling A and Seedling B at day 0 and at day 28"],
    "labels_required": ["Seedling A", "Seedling B", "Day 0: 5 cm", "Day 28: 48 cm"],
    "mode": "image",
    "data": {"day_0_height_cm": 5, "day_28_height_cm": 48},
}
EXPECTED_ROWS = [[0, 5, 5], [7, 12, 6], [14, 22, 7], [21, 35, 8], [28, 48, 9]]


class SpyBuilder:
    """Builder double: counts calls, returns ``built`` (or raises ``error``)."""

    def __init__(self, built: RenderSpecResult | None = None, error: Exception | None = None):
        self.built = built
        self.error = error
        self.build_calls = 0
        self.repair_calls = 0

    async def build(self, order):
        self.build_calls += 1
        if self.error is not None:
            raise self.error
        return self.built

    async def repair(self, order, previous, errors):
        self.repair_calls += 1
        return self.built


class ForbiddenBuilder(SpyBuilder):
    async def build(self, order):
        raise AssertionError("the LLM spec builder must not be called for this figure")


def _executor(monkeypatch, tmp_path, builder, *, mode: str = "auto"):
    monkeypatch.setenv("LECTIO_RENDER_FIGURES", mode)
    store = LocalImageStore(tmp_path, "https://img.example.test")
    monkeypatch.setattr("media.storage.image_store.get_image_store", lambda: store)
    delegate = SharedFigureExecutorAdapter(run_id=RUN_ID)
    delegated: list[VisualGeneratorWorkOrder] = []

    async def fake_execute(order):
        delegated.append(order)
        return [
            GeneratedVisualBlock(
                visual_id=order.visual.id,
                attaches_to=order.visual.attaches_to,
                mode=order.visual.mode,
                image_url="https://cdn.example.test/x.png",
                source_work_order_id=order.work_order_id,
            )
        ]

    object.__setattr__(delegate, "execute_figure", fake_execute)
    executor = RoutingFigureExecutor(delegate, builder_factory=lambda _t, _g: builder)

    outcomes: list = []
    real_render = figure_executor_adapter.render_figure

    async def spy_render(order, **kwargs):
        outcome = await real_render(order, **kwargs)
        outcomes.append(outcome)
        return outcome

    monkeypatch.setattr(figure_executor_adapter, "render_figure", spy_render)
    return executor, delegated, outcomes


def _routes(caplog) -> list:
    return [r for r in caplog.records if r.getMessage() == "figure_route"]


def _data_order(data, *, labels=None, must_show=None, mode="diagram") -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="wo-data",
        visual=VisualPlanItem(
            id="fig-x",
            attaches_to="s1",
            mode=mode,
            purpose="Show the measurements",
            must_show=must_show or ["the measurements"],
            labels_required=labels or [],
            data=data,
        ),
    )


# ---- test 1: the Lesson 1 regression, through the real copy and order paths


def _lesson_1_work_order(figure: dict, *, visual_mode: str):
    """Backbone figure -> copy into block explain-b1 -> the real media work order."""
    packet = _packet().model_copy(update={"backbone": {"figures": [figure]}})
    block = TeachingPlanBlock(
        id="explain-b1",
        position=0,
        intent="Explain growth",
        brief="Show how the seedlings grew",
        evidence="The learner reads the figure",
        visual=VisualSpec(
            figure_ref=figure["id"],
            mode=visual_mode,
            purpose="stale purpose",
            must_show=["stale"],
            labels_required=[],
        ),
    )
    section = TeachingPlanSection(
        slot_id="explain",
        display_title="Why plants need light",
        specific_purpose="Show growth",
        entry_state=["The learner is ready"],
        must_establish=["growth"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["growth"],
        blocks=[block],
    )
    changes = copy_backbone_figures(section, packet)
    assert changes and changes[0]["figure_id"] == figure["id"]
    assert section.blocks[0].visual.data == (figure["data"] or None)

    plan = TeachingPlan(
        arc="Plant growth",
        contract_version=2,
        learner_title="Plant growth",
        starting_state=["The learner is ready"],
        target_state=["The learner understands growth"],
        teaching_plan_id="plan-1",
        revision=1,
        sections=[section],
        approval_status="approved",
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id="plan-1",
        revision=1,
        status="approved",
        preparation_hash="preparation-hash",
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-10-13T00:00:00Z",
        approved_at="2026-10-13T00:01:00Z",
        reviewed_by="teacher-1",
        approval_hash_binding="submitted",
    )
    source = TeachingPlanSource(plan=plan, revision_record=record, id="plan-1", revision=1, content_hash=digest)
    shared = SharedSection(
        id="explain",
        title="Why plants need light",
        position=0,
        nodes=(
            {
                "id": "figure-a",
                "kind": "figure",
                "teaching_block_id": "explain-b1",
                "display": {"caption": "Seedling heights at each weekly check"},
                "accessibility": {"alt_text": ""},
            },
        ),
    )
    shape = (
        ExpectedNodeShape(
            id="figure-a", kind="figure", teaching_block_id="explain-b1", semantic_role="explanation"
        ),
    )
    return build_figure_work_order(
        source,
        shared,
        figure_node_id="figure-a",
        expected_shape=shape,
        approved_source_facts={"fact-1": "Seedling A got light; seedling B did not."},
    )


async def test_lesson_1_fig_2_is_drawn_as_the_backbone_table(monkeypatch, tmp_path, caplog) -> None:
    work = _lesson_1_work_order(FIG2, visual_mode="diagram")
    order = work.work_order
    assert order.visual.data == FIG2["data"]

    executor, delegated, outcomes = _executor(monkeypatch, tmp_path, ForbiddenBuilder())
    with caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
        blocks = await executor.execute_figure(order)

    assert delegated == []
    assert len(outcomes) == 1
    spec = outcomes[0].spec
    assert isinstance(spec, TableSpec)
    assert spec.columns == FIG2["labels_required"]
    assert spec.rows == EXPECTED_ROWS
    block = blocks[0]
    assert block.status in {"ready", "ready_with_quality_warning"}
    assert block.render_route == "data_table"
    assert block.image_url.endswith(".svg")
    # The ready media result keeps the route for the progress view.
    assert bind_generated_figure(work, blocks).render_route == "data_table"

    (event,) = _routes(caplog)
    assert (event.figure_id, event.route, event.data_present) == (
        order.visual.id,
        "data_table",
        True,
    )


async def test_data_table_ignores_the_render_flag_and_the_mode(monkeypatch, tmp_path) -> None:
    # An old plan may have mode "image"; the data still decides the route.
    work = _lesson_1_work_order(FIG2, visual_mode="image")
    executor, delegated, outcomes = _executor(
        monkeypatch, tmp_path, ForbiddenBuilder(), mode="off"
    )
    blocks = await executor.execute_figure(work.work_order)
    assert delegated == []
    assert isinstance(outcomes[0].spec, TableSpec)
    assert blocks[0].render_route == "data_table"


# ---- test 5: a data figure that cannot be drawn fails and never reaches the image model


@pytest.mark.parametrize(
    "builder",
    [
        SpyBuilder(RenderSpecResult(family="none", reason="no fit")),
        SpyBuilder(error=TimeoutError()),
    ],
    ids=["no-family", "builder-raises"],
)
async def test_data_figure_without_a_spec_fails_and_never_delegates(
    monkeypatch, tmp_path, caplog, builder
) -> None:
    # Unequal series: not a clean table, so only the LLM builder could draw it.
    order = _data_order({"x": [1, 2, 3], "y": [4, 5]})
    executor, delegated, _ = _executor(monkeypatch, tmp_path, builder)
    with caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
        blocks = await executor.execute_figure(order)

    assert delegated == []
    assert builder.build_calls == 1
    block = blocks[0]
    assert block.status == "failed"
    assert block.error_code == "figure_data_not_rendered"
    assert block.error_message
    assert block.image_url is None
    assert block.render_route == "failed"
    (event,) = _routes(caplog)
    assert event.route == "failed" and event.data_present is True
    assert "figure_data_not_rendered" in event.reason


async def test_labels_with_numbers_outside_the_data_fail_before_any_drawing(
    monkeypatch, tmp_path, caplog
) -> None:
    order = _data_order(FIG2["data"], labels=["Day", "Height (cm)", "Day 30: 61 cm"])
    executor, delegated, outcomes = _executor(monkeypatch, tmp_path, ForbiddenBuilder())
    with caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
        blocks = await executor.execute_figure(order)
    assert delegated == [] and outcomes == []
    assert blocks[0].error_code == "figure_data_not_rendered"
    assert "30" in blocks[0].error_message and "61" in blocks[0].error_message
    assert _routes(caplog)[0].route == "failed"


# ---- test 6: the number guard on the LLM-built spec


async def test_llm_spec_with_invented_values_is_rejected(monkeypatch, tmp_path) -> None:
    invented = RenderSpecResult(
        family="bar_chart",
        spec=BarChartSpec.model_validate(
            {
                "family": "bar_chart",
                "categories": ["Seedling A", "Seedling B"],
                "series": [{"name": "Height", "values": [19, 25]}],
                "x_label": "Seedling",
                "y_label": "Height (cm)",
            }
        ),
    )
    builder = SpyBuilder(invented)
    # Unequal series keep the deterministic table out of the way.
    order = _data_order({"day": [0, 7, 14, 21, 28], "a": [5, 12, 22, 35, 48, 52]})
    executor, delegated, outcomes = _executor(monkeypatch, tmp_path, builder)
    blocks = await executor.execute_figure(order)

    assert delegated == []
    assert outcomes[0].code == "render_spec_invalid"
    assert [e["code"] for e in outcomes[0].errors] == [
        "number_not_in_data:19",
        "number_not_in_data:25",
    ]
    assert builder.repair_calls == 2
    assert blocks[0].status == "failed"
    assert blocks[0].error_code == "figure_data_not_rendered"
    assert "number_not_in_data:19" in blocks[0].error_message


# ---- test 7: scalar-only data is a labelled picture for the image model


async def test_scalar_only_figure_goes_to_the_image_path(monkeypatch, tmp_path, caplog) -> None:
    work = _lesson_1_work_order(FIG1, visual_mode="image")
    order = work.work_order
    assert order.visual.data == FIG1["data"]

    executor, delegated, outcomes = _executor(monkeypatch, tmp_path, ForbiddenBuilder())
    with caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
        blocks = await executor.execute_figure(order)

    assert len(delegated) == 1 and outcomes == []
    assert blocks[0].render_route == "image_label_only"
    (event,) = _routes(caplog)
    assert (event.route, event.data_present) == ("image_label_only", True)

    prompt = build_visual_prompt(order, provider_renders_labels=True)
    assert "Use only the numbers in the label list. Add no other number, scale or axis value." in prompt
    assert '- "Day 28: 48 cm"' in prompt
    assert "no title, caption, or sentences." in prompt

    plain = build_visual_prompt(order, provider_renders_labels=False)
    assert "use only the numbers in the label list" in plain


async def test_figure_without_data_keeps_the_old_routes(monkeypatch, tmp_path, caplog) -> None:
    order = VisualGeneratorWorkOrder(
        work_order_id="wo-plain",
        visual=VisualPlanItem(id="v1", attaches_to="s1", mode="image", purpose="A leaf"),
        source_of_truth=[SourceOfTruthEntry(key="caption", text="A leaf")],
    )
    executor, delegated, _ = _executor(monkeypatch, tmp_path, ForbiddenBuilder())
    with caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
        blocks = await executor.execute_figure(order)
    assert len(delegated) == 1
    assert blocks[0].render_route == "image"
    event = _routes(caplog)[0]
    assert (event.route, event.data_present) == ("image", False)


# ---- failure plumbing: figure_data_not_rendered is a retryable, specific failure


def test_failed_data_block_binds_as_a_provider_failure_with_its_code() -> None:
    work = runtime_work(suffix="a")
    block = GeneratedVisualBlock(
        **{
            **_failed_provider_block(work).model_dump(),
            "error_code": "figure_data_not_rendered",
            "render_route": "failed",
        }
    )
    with pytest.raises(SharedFigureMediaProviderFailed) as raised:
        bind_generated_figure(work, [block])
    assert raised.value.error_code == "figure_data_not_rendered"


class _DataFailureExecutor:
    def __init__(self, work) -> None:
        self.work = work

    async def execute_figure(self, _order):
        block = _failed_provider_block(self.work)
        return [
            GeneratedVisualBlock(
                **{
                    **block.model_dump(),
                    "error_code": "figure_data_not_rendered",
                    "render_route": "failed",
                }
            )
        ]


@pytest.mark.asyncio
async def test_data_failure_is_recorded_retryable_with_its_code_and_route(db_session) -> None:
    _owner, run_id, work, item_id = await _admit(db_session, suffix="d")
    outcome = await execute_figure_media_work_item(
        _job(db_session, item_id, work, _DataFailureExecutor(work))
    )
    assert outcome.error_code == "figure_data_not_rendered"
    assert outcome.error_summary == "Figure could not be drawn from its data. Retry the figure."

    row = await db_session.get(GenerationWorkItemModel, item_id)
    assert row is not None
    assert row.status == "failed_recoverable"
    assert row.error_code == "figure_data_not_rendered"
    assert row.recovery_action == "retry"
    # Same predicate as infra.generation_runtime.http.retry_eligible.
    assert row.error_class in _RETRYABLE_ERROR_CLASSES
    assert row.attempt < row.max_attempts

    rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run_id)
            )
        ).all()
    )
    (figure,) = [f for f in project_figures([], rows) if f.figure_id == work.figure_node_id]
    assert figure.status == "failed"
    assert figure.error_code == "figure_data_not_rendered"
    assert figure.retryable is True
    assert figure.recovery_action == "retry"
    assert figure.route == "failed"


def test_progress_route_of_a_ready_figure_comes_from_its_output() -> None:
    from types import SimpleNamespace

    item = SimpleNamespace(
        id="i1",
        item_key="media:fig",
        stage="media_generation",
        status="ready",
        composition_identity='{"figure_node_id": "fig"}',
        output_json={"status": "ready", "render_route": "data_table"},
        attempt=1,
        max_attempts=3,
        error_code=None,
        error_summary=None,
        recovery_action=None,
        replaces_work_item_id=None,
    )
    (figure,) = project_figures([], [item])
    assert figure.status == "ready" and figure.route == "data_table"

    item.output_json = {"status": "ready"}
    (figure,) = project_figures([], [item])
    assert figure.route is None

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from test_shared_lesson_handoff import _accepted

from document.shared_lesson import post_section_pipeline as pipeline
from document.shared_lesson.assembly import assemble_shared_lesson_document
from document.shared_lesson.boundary_dispatcher import BoundaryDispatchResult
from document.shared_lesson.document_qa_dispatcher import SharedDocumentQADispatchResult
from document.shared_lesson.document_semantic import DocumentSemanticQAResult
from document.shared_lesson.finalization_dispatcher import SharedLessonFinalizationDispatchOutcome
from document.shared_lesson.media import SharedFigureMediaError
from document.shared_lesson.media_runtime import MediaReadiness
from document.shared_lesson.qa_runtime import VerifiedDocumentQA


def _run(run_id: str = "7d3c5b1e-4f2a-4c8e-9b6d-2a1f0e9c8b7a") -> SimpleNamespace:
    return SimpleNamespace(
        id=run_id,
        created_at=datetime(2026, 9, 26, 12, tzinfo=UTC),
        run_type="shared_document",
    )


@pytest.mark.asyncio
async def test_one_section_pipeline_reaches_ready_without_a_second_qa_call(
    db_session_factory,
    monkeypatch,
) -> None:
    source, composition, section = _accepted()
    assembled = assemble_shared_lesson_document(
        document_id="shared-document:7d3c5b1e-4f2a-4c8e-9b6d-2a1f0e9c8b7a:revision:1",
        revision=1,
        source=source,
        accepted_sections={section.id: section},
        expected_shapes=pipeline._expected_shapes({section.id: composition}),
        approved_source_ids=(),
        created_at=datetime(2026, 9, 26, 12, tzinfo=UTC),
    )
    semantic = DocumentSemanticQAResult(
        document_id=assembled.document.id,
        document_revision=assembled.document.revision,
        document_hash=assembled.document.content_hash,
        status="pass",
        semantic_calls=1,
    )
    qa_result = SharedDocumentQADispatchResult(
        run_id="7d3c5b1e-4f2a-4c8e-9b6d-2a1f0e9c8b7a",
        work_item_id="qa-item",
        document=assembled.document,
        deterministic_qa=assembled.qa,
        verified_qa=VerifiedDocumentQA(
            work_item_id="qa-item",
            output_hash="a" * 64,
            semantic_qa=semantic,
        ),
    )
    handoff = SimpleNamespace(document=assembled.document)
    captured_executor: dict[str, object] = {}
    stage_calls: list[str] = []

    class FakeMediaDispatcher:
        def __init__(self, *_args, **_kwargs):
            captured_executor["value"] = _kwargs["executor"]

        async def run_one(self, **_kwargs):
            return SimpleNamespace(
                readiness=MediaReadiness(ready=True, required_count=0, ready_count=0)
            )

    async def passed_boundaries(*_args, **_kwargs):
        return _passed_boundaries()

    async def set_stage(*_args, **kwargs):
        stage_calls.append(kwargs["stage"])

    monkeypatch.setattr(pipeline, "dispatch_shared_document_boundaries", passed_boundaries)
    monkeypatch.setattr(pipeline, "_set_run_stage", set_stage)
    monkeypatch.setattr(pipeline, "SharedMediaDispatcher", FakeMediaDispatcher)
    monkeypatch.setattr(
        pipeline,
        "load_current_approved_teaching_plan_source",
        lambda **_kwargs: _source(source),
    )
    monkeypatch.setattr(
        pipeline,
        "_load_post_section_inputs",
        lambda *_args, **_kwargs: _inputs(_run(), source, composition, section),
    )

    async def active_run_items(*_args, **_kwargs):
        return (), ()

    monkeypatch.setattr(pipeline, "_active_run_items", active_run_items)
    monkeypatch.setattr(pipeline, "_durable_media_results", lambda **_kwargs: ((), {}))

    async def dispatch_qa(*_args, **_kwargs):
        return qa_result

    async def dispatch_handoff(*_args, **_kwargs):
        return handoff

    monkeypatch.setattr(pipeline, "dispatch_shared_document_qa", dispatch_qa)
    monkeypatch.setattr(pipeline, "handoff_qa_dispatch_result", dispatch_handoff)

    async def finalize(*_args, **_kwargs):
        return _ready_finalization()

    monkeypatch.setattr(
        pipeline,
        "finalize_shared_lesson_document_for_run",
        finalize,
    )

    outcome = await pipeline.run_post_section_pipeline(
        db_session_factory,
        run_id="7d3c5b1e-4f2a-4c8e-9b6d-2a1f0e9c8b7a",
        owner_user_id="owner",
        path_lesson_id="lesson",
        preparation_generation_id="prep",
    )
    assert outcome.state == "ready"
    assert outcome.document_id == assembled.document.id
    assert isinstance(captured_executor["value"], pipeline.SharedFigureExecutorAdapter)
    assert stage_calls == [
        "continuity_validation",
        "media_generation",
        "document_qa",
        "document_finalization",
    ]


@pytest.mark.asyncio
async def test_pipeline_stops_pending_before_media_or_qa(db_session_factory, monkeypatch) -> None:
    called = False

    async def unexpected_media(*_args, **_kwargs):
        nonlocal called
        called = True

    async def pending_boundaries(*_args, **_kwargs):
        return BoundaryDispatchResult(run_id="run", state="pending")

    async def set_stage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline, "dispatch_shared_document_boundaries", pending_boundaries)
    monkeypatch.setattr(pipeline, "_set_run_stage", set_stage)
    monkeypatch.setattr(pipeline, "SharedMediaDispatcher", unexpected_media)

    outcome = await pipeline.run_post_section_pipeline(
        db_session_factory,
        run_id="run",
        owner_user_id="owner",
        path_lesson_id="lesson",
        preparation_generation_id="prep",
    )
    assert outcome.state == "pending"
    assert outcome.stage == "boundaries"
    assert called is False


@pytest.mark.asyncio
async def test_invalid_accepted_figure_section_returns_blocked_outcome(
    db_session_factory,
    monkeypatch,
) -> None:
    source, _composition, _section = _accepted()

    class InvalidMediaDispatcher:
        def __init__(self, *_args, **_kwargs):
            pass

        async def run_one(self, **_kwargs):
            raise SharedFigureMediaError(
                "accepted section failed deterministic validation: avoid_repeating_violated"
            )

    async def passed_boundaries(*_args, **_kwargs):
        return _passed_boundaries()

    async def set_stage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(pipeline, "dispatch_shared_document_boundaries", passed_boundaries)
    monkeypatch.setattr(pipeline, "_set_run_stage", set_stage)
    monkeypatch.setattr(pipeline, "SharedMediaDispatcher", InvalidMediaDispatcher)
    monkeypatch.setattr(
        pipeline,
        "load_current_approved_teaching_plan_source",
        lambda **_kwargs: _source(source),
    )

    outcome = await pipeline.run_post_section_pipeline(
        db_session_factory,
        run_id="7d3c5b1e-4f2a-4c8e-9b6d-2a1f0e9c8b7a",
        owner_user_id="owner",
        path_lesson_id="lesson",
        preparation_generation_id="prep",
    )

    assert outcome.state == "blocked"
    assert outcome.stage == "media"
    assert "avoid_repeating_violated" in (outcome.error or "")


def _passed_boundaries() -> BoundaryDispatchResult:
    return BoundaryDispatchResult(run_id="7d3c5b1e-4f2a-4c8e-9b6d-2a1f0e9c8b7a", state="no_boundaries")


def _source(source):
    async def load(**_kwargs):
        return source

    return load()


async def _inputs(run, source, composition, section):
    return run, source, (), (composition,), (section,)


def _ready_finalization() -> SharedLessonFinalizationDispatchOutcome:
    return SharedLessonFinalizationDispatchOutcome(status="ready")

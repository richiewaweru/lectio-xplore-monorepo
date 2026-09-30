"""Advisory vs blocking document quality gate (QG-B)."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

import document.shared_lesson.qa as qa_module
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.document_semantic import DocumentSemanticVerdict
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.http import get_shared_document_quality_flags
from document.shared_lesson.qa import (
    DETERMINISTIC_ISSUE_CLASSIFICATION,
    DocumentQAResult,
    qa_shared_lesson_document,
)
from document.shared_lesson.qa_runtime import (
    DocumentQARuntimeError,
    DocumentQAWorkItemJob,
    admit_document_qa_work_item,
    execute_document_qa_work_item,
    load_run_quality_flags,
    load_verified_document_qa,
)
from infra.database.models import GenerationEventModel, GenerationWorkItemModel
from test_shared_qa_runtime import _deterministic, _seed_run, _source_and_document

_SRC = Path(__file__).resolve().parents[2] / "src" / "document" / "shared_lesson"


def _issue(code: str, section_id: str, *, node_ids=()) -> ContinuityIssue:
    return ContinuityIssue(
        issue_code=code,
        affected_section_id=section_id,
        affected_node_ids=tuple(node_ids),
        explanation=f"{code} explanation",
        required_correction=f"fix {code}",
    )


def test_deterministic_classification_table_covers_every_emitted_code() -> None:
    emitted: set[str] = set()
    for name in ("qa.py", "continuity.py"):
        emitted |= set(re.findall(r'_issue\(\s*"([a-z_]+)"', (_SRC / name).read_text()))
    assert emitted, "no deterministic issue codes found"
    assert emitted <= set(DETERMINISTIC_ISSUE_CLASSIFICATION), sorted(
        emitted - set(DETERMINISTIC_ISSUE_CLASSIFICATION)
    )
    assert set(DETERMINISTIC_ISSUE_CLASSIFICATION.values()) == {"hard", "advisory"}
    # Structure/lineage/hash/contract failures can never be advisory.
    for code in (
        "document_hash_mismatch",
        "source_lineage_mismatch",
        "node_id_mismatch",
        "node_kind_mismatch",
        "section_shape_mismatch",
        "task_anchor_mismatch",
        "required_media_missing",
        "expected_shape_missing",
    ):
        assert DETERMINISTIC_ISSUE_CLASSIFICATION[code] == "hard"


@pytest.mark.parametrize("gate", ["advisory", "blocking"])
def test_deterministic_qa_splits_advisory_issues_only_in_advisory_mode(
    monkeypatch, gate: str
) -> None:
    from infra.config import settings

    monkeypatch.setattr(settings, "document_quality_gate", gate)
    source, document = _source_and_document()
    section_id = document.sections[0].id
    injected = [
        _issue("metadata_or_placeholder_leak", section_id),
        _issue("node_id_mismatch", section_id),
    ]
    monkeypatch.setattr(qa_module, "validate_section_continuity", lambda **_kw: injected)
    monkeypatch.setattr(qa_module, "validate_section_boundary", lambda **_kw: [])

    result = qa_shared_lesson_document(
        document=document,
        teaching_plan_sections=tuple(source.plan.sections),
        expected_shapes={section.id: () for section in document.sections},
    )
    hard = {issue.issue_code for issue in result.issues}
    advisory = {issue.issue_code for issue in result.advisory_issues}
    assert "node_id_mismatch" in hard
    assert not result.ready
    if gate == "advisory":
        assert advisory == {"metadata_or_placeholder_leak"}
        assert "metadata_or_placeholder_leak" not in hard
    else:
        assert advisory == set()
        assert "metadata_or_placeholder_leak" in hard


def test_unknown_deterministic_code_is_hard() -> None:
    assert not qa_module.is_advisory_deterministic_code("some_future_code")


async def _admitted(db_session, suffix: str, deterministic=None):
    source, document = _source_and_document()
    owner, run_id = await _seed_run(db_session, source, suffix=suffix)
    deterministic = deterministic or _deterministic(document)
    admitted = await admit_document_qa_work_item(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        document=document,
        deterministic_qa=deterministic,
    )
    return source, document, owner, run_id, admitted.record.id, deterministic


def _semantic_issue_verdict(document):
    async def provider(_request):
        return DocumentSemanticVerdict(
            status="issue",
            issues=(
                _issue(
                    "answer_leakage",
                    document.sections[0].id,
                    node_ids=(document.sections[0].nodes[0].id,),
                ),
            ),
        )

    return provider


@pytest.mark.asyncio
async def test_advisory_semantic_issue_becomes_ready_with_flags_and_same_hash(db_session) -> None:
    source, document, owner, run_id, item_id, deterministic = await _admitted(
        db_session, "adv-ready"
    )
    hash_before = document.content_hash

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=item_id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=deterministic,
            semantic_validator=_semantic_issue_verdict(document),
        )
    )
    assert outcome.qa is not None and outcome.error_code is None
    item = await db_session.get(GenerationWorkItemModel, item_id)
    assert item is not None and item.status == "ready"

    verified = await load_verified_document_qa(
        db_session, run_id=run_id, owner_user_id=owner, source=source, document=document
    )
    assert verified.semantic_qa.passed
    [flag] = verified.quality_flags
    assert flag.code == "answer_leakage"
    assert flag.severity == "warning"
    assert flag.source == "semantic_qa"
    assert flag.section_id == document.sections[0].id
    assert flag.required_correction == "fix answer_leakage"
    # The document itself is untouched.
    assert document.content_hash == hash_before == shared_lesson_content_hash(document)

    events = (
        await db_session.scalars(
            select(GenerationEventModel).where(GenerationEventModel.run_id == run_id)
        )
    ).all()
    assert "document_qa_advisory_flags" in {event.event_type for event in events}
    assert "document_qa_semantic_issues" not in {event.event_type for event in events}

    flags = await load_run_quality_flags(db_session, run_id=run_id, owner_user_id=owner)
    assert [f.code for f in flags] == ["answer_leakage"]
    assert await load_run_quality_flags(db_session, run_id=run_id, owner_user_id="someone-else") == ()


@pytest.mark.asyncio
async def test_advisory_records_deterministic_advisory_and_writer_warning_sources(
    db_session,
) -> None:
    source, document = _source_and_document()
    section_id = document.sections[0].id
    deterministic = DocumentQAResult(
        document_id=document.id,
        document_revision=document.revision,
        advisory_issues=(_issue("metadata_or_placeholder_leak", section_id),),
    )
    source, document, owner, run_id, item_id, deterministic = await _admitted(
        db_session, "adv-sources", deterministic
    )
    writer_warning = _issue("unsupported_claim", section_id)

    async def clean(_request):
        return DocumentSemanticVerdict(status="pass")

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=item_id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=deterministic,
            semantic_validator=clean,
            synthetic_issues=(writer_warning,),
        )
    )
    assert outcome.qa is not None
    flags = await load_run_quality_flags(db_session, run_id=run_id, owner_user_id=owner)
    assert [(f.source, f.code) for f in flags] == [
        ("deterministic_qa", "metadata_or_placeholder_leak"),
        ("writer_warning", "unsupported_claim"),
    ]


@pytest.mark.asyncio
async def test_clean_pass_records_no_flags(db_session) -> None:
    source, document, owner, run_id, item_id, deterministic = await _admitted(
        db_session, "adv-clean"
    )

    async def clean(_request):
        return DocumentSemanticVerdict(status="pass")

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=item_id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=deterministic,
            semantic_validator=clean,
        )
    )
    assert outcome.qa is not None
    assert await load_run_quality_flags(db_session, run_id=run_id, owner_user_id=owner) == ()


@pytest.mark.asyncio
async def test_blocking_mode_still_parks_for_review(db_session, blocking_quality_gate) -> None:
    source, document, owner, run_id, item_id, deterministic = await _admitted(
        db_session, "blocking"
    )
    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=item_id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=deterministic,
            semantic_validator=_semantic_issue_verdict(document),
        )
    )
    assert outcome.qa is None
    assert outcome.error_code == "document_qa_semantic_issue"
    item = await db_session.get(GenerationWorkItemModel, item_id)
    assert item is not None
    assert (item.status, item.recovery_action) == ("failed_recoverable", "review")
    assert await load_run_quality_flags(db_session, run_id=run_id, owner_user_id=owner) == ()


@pytest.mark.asyncio
async def test_advisory_mode_still_fails_hard_on_malformed_provider_output(db_session) -> None:
    source, document, owner, _run_id, item_id, deterministic = await _admitted(
        db_session, "adv-malformed"
    )

    async def malformed(_request):
        return {"status": "pass", "issues": ({"unexpected": True},)}

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=item_id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=deterministic,
            semantic_validator=malformed,
        )
    )
    assert outcome.qa is None
    item = await db_session.get(GenerationWorkItemModel, item_id)
    assert item is not None
    assert (item.status, item.error_class, item.recovery_action) == (
        "failed_recoverable",
        "provider_output",
        "retry",
    )


@pytest.mark.asyncio
async def test_advisory_mode_still_fails_hard_on_transport_error(db_session) -> None:
    source, document, owner, _run_id, item_id, deterministic = await _admitted(
        db_session, "adv-transport"
    )

    async def boom(_request):
        raise TimeoutError("provider timed out")

    outcome = await execute_document_qa_work_item(
        DocumentQAWorkItemJob(
            session=db_session,
            work_item_id=item_id,
            worker_id="qa-worker",
            owner_user_id=owner,
            source=source,
            document=document,
            deterministic_qa=deterministic,
            semantic_validator=boom,
        )
    )
    assert outcome.qa is None
    item = await db_session.get(GenerationWorkItemModel, item_id)
    assert item is not None
    assert (item.status, item.error_class) == ("failed_recoverable", "provider_transport")


@pytest.mark.asyncio
async def test_advisory_mode_rejects_hard_deterministic_failure(db_session) -> None:
    source, document, owner, run_id, item_id, _det = await _admitted(db_session, "adv-hard")
    with pytest.raises(DocumentQARuntimeError):
        await execute_document_qa_work_item(
            DocumentQAWorkItemJob(
                session=db_session,
                work_item_id=item_id,
                worker_id="qa-worker",
                owner_user_id=owner,
                source=source,
                document=document,
                deterministic_qa=_deterministic(document, ready=False),
            )
        )
    assert await load_run_quality_flags(db_session, run_id=run_id, owner_user_id=owner) == ()


@pytest.mark.asyncio
async def test_quality_flags_endpoint_is_owner_scoped_and_validates_input(db_session) -> None:
    user = SimpleNamespace(id="nobody")
    with pytest.raises(HTTPException) as both:
        await get_shared_document_quality_flags(
            editable_lesson_id="a", generation_id="b", current_user=user, session=db_session
        )
    assert both.value.status_code == 422
    with pytest.raises(HTTPException) as neither:
        await get_shared_document_quality_flags(current_user=user, session=db_session)
    assert neither.value.status_code == 422

    missing = await get_shared_document_quality_flags(
        editable_lesson_id="unknown", current_user=user, session=db_session
    )
    assert missing == {"run_id": None, "flags": []}
    missing = await get_shared_document_quality_flags(
        generation_id="unknown", current_user=user, session=db_session
    )
    assert missing == {"run_id": None, "flags": []}

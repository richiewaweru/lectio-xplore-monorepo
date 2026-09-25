from __future__ import annotations

from datetime import UTC, datetime

import pytest

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.document_semantic import (
    DocumentSemanticOutputError,
    DocumentSemanticQAResult,
    DocumentSemanticVerdict,
    qa_shared_lesson_document_semantics,
)
from document.shared_lesson.models import (
    ParagraphDisplay,
    ParagraphNode,
    SharedSection,
    build_shared_lesson_document,
)
from document.shared_lesson.qa import DocumentQAResult
from infra.authoring.model_policy import DOCUMENT_SEMANTIC_QA, get_v3_slot


def _plan_section() -> TeachingPlanSection:
    return TeachingPlanSection(
        slot_id="section-1",
        display_title="Energy transfer",
        entry_state=["recognize energy"],
        must_establish=["explain energy transfer"],
        avoid_repeating=[],
        bridge_from_previous=None,
        exit_state=["explain energy transfer"],
    )


def _document() -> object:
    return build_shared_lesson_document(
        {
            "id": "document-1",
            "revision": 1,
            "teaching_plan_id": "plan-1",
            "teaching_plan_revision": 1,
            "teaching_plan_hash": "a" * 64,
            "title": "Energy transfer",
            "sections": [
                SharedSection(
                    id="section-1",
                    title="Energy transfer",
                    position=0,
                    nodes=(
                        ParagraphNode(
                            id="node-1",
                            teaching_block_id="block-1",
                            display=ParagraphDisplay(
                                text="Energy moves from one system to another."
                            ),
                        ),
                    ),
                )
            ],
            "created_at": datetime.now(UTC),
        }
    )


def _deterministic(*issues: object) -> DocumentQAResult:
    document = _document()
    return DocumentQAResult(
        document_id=document.id,
        document_revision=document.revision,
        issues=issues,
    )


@pytest.mark.asyncio
async def test_document_semantic_qa_makes_one_call_and_preserves_pass() -> None:
    document = _document()
    calls: list[object] = []

    async def reviewer(request):
        calls.append(request)
        return DocumentSemanticVerdict(status="pass")

    result = await qa_shared_lesson_document_semantics(
        document=document,
        teaching_plan_sections=(_plan_section(),),
        deterministic=_deterministic(),
        semantic_validator=reviewer,
    )

    assert result == DocumentSemanticQAResult(
        document_id="document-1",
        document_revision=1,
        status="pass",
        semantic_calls=1,
    )
    assert len(calls) == 1
    assert calls[0].document.id == document.id


@pytest.mark.asyncio
async def test_semantic_issue_must_bind_to_existing_section_and_node() -> None:
    document = _document()

    async def reviewer(_request):
        return {
            "status": "issue",
            "issues": [
                {
                    "issue_code": "progression_gap",
                    "affected_section_id": "section-1",
                    "affected_node_ids": ["node-1"],
                    "explanation": "The transfer step is not explained.",
                    "required_correction": "Explain how energy moves between systems.",
                }
            ],
        }

    result = await qa_shared_lesson_document_semantics(
        document=document,
        teaching_plan_sections=(_plan_section(),),
        deterministic=_deterministic(),
        semantic_validator=reviewer,
    )

    assert result.status == "issue"
    assert result.semantic_calls == 1
    assert result.issues[0].affected_node_ids == ("node-1",)


@pytest.mark.asyncio
async def test_malformed_closed_output_is_a_semantic_contract_error() -> None:
    async def reviewer(_request):
        return {"status": "pass", "issues": [{"unexpected": True}]}

    with pytest.raises(DocumentSemanticOutputError, match="closed schema"):
        await qa_shared_lesson_document_semantics(
            document=_document(),
            teaching_plan_sections=(_plan_section(),),
            deterministic=_deterministic(),
            semantic_validator=reviewer,
        )


@pytest.mark.asyncio
async def test_unbound_issue_is_rejected_without_repair_or_rewrite() -> None:
    async def reviewer(_request):
        return {
            "status": "issue",
            "issues": [
                {
                    "issue_code": "progression_gap",
                    "affected_section_id": "missing-section",
                    "explanation": "Unknown target.",
                    "required_correction": "Use a supplied section.",
                }
            ],
        }

    with pytest.raises(DocumentSemanticOutputError, match="unknown section"):
        await qa_shared_lesson_document_semantics(
            document=_document(),
            teaching_plan_sections=(_plan_section(),),
            deterministic=_deterministic(),
            semantic_validator=reviewer,
        )


@pytest.mark.asyncio
async def test_deterministic_failure_skips_semantic_call() -> None:
    called = False

    async def reviewer(_request):
        nonlocal called
        called = True
        return DocumentSemanticVerdict(status="pass")

    result = await qa_shared_lesson_document_semantics(
        document=_document(),
        teaching_plan_sections=(_plan_section(),),
        deterministic=_deterministic(
            {
                "issue_code": "required_media_missing",
                "affected_section_id": "section-1",
                "explanation": "Figure is missing.",
                "required_correction": "Complete required media.",
            }
        ),
        semantic_validator=reviewer,
    )

    assert not called
    assert result.semantic_calls == 0
    assert result.deterministic_skipped_semantic is True
    assert result.issues[0].issue_code == "required_media_missing"


@pytest.mark.asyncio
async def test_provider_operational_error_propagates() -> None:
    class ProviderDown(RuntimeError):
        pass

    async def reviewer(_request):
        raise ProviderDown("provider unavailable")

    with pytest.raises(ProviderDown, match="provider unavailable"):
        await qa_shared_lesson_document_semantics(
            document=_document(),
            teaching_plan_sections=(_plan_section(),),
            deterministic=_deterministic(),
            semantic_validator=reviewer,
        )


def test_document_semantic_qa_uses_fast_existing_capability_slot() -> None:
    assert get_v3_slot(DOCUMENT_SEMANTIC_QA).value == "fast"


@pytest.mark.asyncio
async def test_default_validator_dispatches_only_semantic_capability(monkeypatch) -> None:
    from document.shared_lesson import document_semantic

    calls: list[dict] = []

    async def run_structured_agent(**kwargs):
        calls.append(kwargs)
        return DocumentSemanticVerdict(status="pass")

    monkeypatch.setattr(
        "infra.authoring.structured_provider.run_structured_agent", run_structured_agent
    )

    result = await document_semantic.default_document_semantic_validator(
        document_semantic.DocumentSemanticQARequest(
            document=_document(), teaching_plan_sections=(_plan_section(),)
        )
    )

    assert result.status == "pass"
    assert len(calls) == 1
    assert calls[0]["node_name"] == DOCUMENT_SEMANTIC_QA
    assert calls[0]["repair_attempts"] == 0
    assert calls[0]["retries"] == {"output": 0}

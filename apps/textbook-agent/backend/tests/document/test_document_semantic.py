from __future__ import annotations

from datetime import UTC, datetime

import pytest

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.document_semantic import (
    DocumentSemanticInputError,
    DocumentSemanticOutputError,
    DocumentSemanticQAResult,
    DocumentSemanticQARequest,
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
        document_hash=document.content_hash,
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
@pytest.mark.parametrize(
    "issue_code",
    [
        "misconception_unresolved",
        "answer_leakage",
        "assessment_duplicates_example",
        "factual_inaccuracy",
    ],
)
async def test_new_quality_issue_codes_bind_to_real_section_and_node(
    issue_code: str,
) -> None:
    document = _document()

    async def reviewer(_request):
        return {
            "status": "issue",
            "issues": [
                {
                    "issue_code": issue_code,
                    "affected_section_id": "section-1",
                    "affected_node_ids": ["node-1"],
                    "explanation": f"A {issue_code} defect was found.",
                    "required_correction": "Fix the defect in this node only.",
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
    assert result.issues[0].issue_code == issue_code


def test_document_semantic_qa_prompt_documents_new_quality_checks() -> None:
    from core.prompts import effective_prompt_text

    prompt = effective_prompt_text("document-semantic-qa")

    for issue_code in (
        "misconception_unresolved",
        "answer_leakage",
        "assessment_duplicates_example",
        "factual_inaccuracy",
    ):
        assert issue_code in prompt
    # The prompt must tell the reviewer that evaluation/response data (not
    # just task prompts) is available for judging leakage and duplication.
    assert "evaluation" in prompt
    assert "response" in prompt


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
@pytest.mark.parametrize(
    ("document_id", "document_revision"),
    [("stale-document", 1), ("document-1", 99)],
)
async def test_stale_deterministic_result_is_rejected(
    document_id: str, document_revision: int
) -> None:
    document = _document()
    with pytest.raises(DocumentSemanticInputError, match="identity"):
        await qa_shared_lesson_document_semantics(
            document=document,
            teaching_plan_sections=(_plan_section(),),
            deterministic=DocumentQAResult(
                document_id=document_id,
                document_revision=document_revision,
            ),
            semantic_validator=lambda _request: pytest.fail("semantic call must be skipped"),
        )


@pytest.mark.asyncio
async def test_document_hash_mismatch_is_rejected_before_semantic_call() -> None:
    document = _document().model_copy(update={"content_hash": "b" * 64})
    with pytest.raises(DocumentSemanticInputError, match="content_hash"):
        await qa_shared_lesson_document_semantics(
            document=document,
            teaching_plan_sections=(_plan_section(),),
            deterministic=DocumentQAResult(
                document_id=document.id,
                document_revision=document.revision,
            ),
            semantic_validator=lambda _request: pytest.fail("semantic call must be skipped"),
        )


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


def test_document_semantic_qa_uses_standard_slot() -> None:
    assert get_v3_slot(DOCUMENT_SEMANTIC_QA).value == "standard"


def test_document_semantic_qa_runs_with_deepseek_thinking_enabled() -> None:
    from infra.authoring.model_policy import V3_NODE_REASONING

    assert V3_NODE_REASONING[DOCUMENT_SEMANTIC_QA] == "medium"


def test_document_semantic_qa_payload_includes_task_evaluation_and_plan_sections() -> None:
    """The single QA call must see task evaluation/answers, not just prompts."""
    document = _document()
    request = DocumentSemanticQARequest(
        document=document, teaching_plan_sections=(_plan_section(),)
    )
    payload = request.model_dump(mode="json")

    assert payload["teaching_plan_sections"][0]["must_establish"] == [
        "explain energy transfer"
    ]
    # Tasks (with response/evaluation) travel inside the document itself.
    assert "tasks" in payload["document"]


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

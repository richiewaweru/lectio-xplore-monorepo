from __future__ import annotations

from typing import Any

import pytest

from curriculum.shared_sourcebook_authoring import (
    SharedSourcebookAuthoringError,
    approved_sourcebook_refs,
    author_shared_sourcebook,
)
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock, TeachingPlanSection
from infra.authoring import (
    AuthoringEngineError,
    AuthoringProviderCall,
    AuthoringProviderTerminalError,
)


class ScriptedProvider:
    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[AuthoringProviderCall] = []

    async def invoke(self, call: AuthoringProviderCall) -> Any:
        self.calls.append(call)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _entry(
    ref: str,
    *,
    purpose: str = "A stable fact",
    provenance_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "approved_ref_id": ref,
        "type": "definition",
        "purpose": purpose,
        "content": {"text": f"Content for {ref}"},
        "provenance_refs": provenance_refs or [f"fact:{ref}"],
    }


def _plan(*refs: tuple[str, str]) -> TeachingPlan:
    blocks = [
        TeachingPlanBlock(
            id=f"b{index}",
            position=index,
            intent="explain",
            brief=f"Explain {ref}",
            evidence="Learner understands the stable fact.",
            sourcebook_needs=[f"Need {ref}"],
            sourcebook_refs=[ref],
        )
        for index, (ref, _label) in enumerate(refs)
    ]
    return TeachingPlan(
        contract_version=2,
        learner_title="A shared sourcebook lesson",
        arc="Build a stable explanation",
        starting_state=["Learner has an initial question"],
        target_state=["Learner can explain the idea"],
        teaching_plan_id="tp-sourcebook",
        revision=4,
        approval_status="approved",
        sections=[
            TeachingPlanSection(
                slot_id="s1",
                display_title="Core explanation",
                specific_purpose="Establish the shared facts.",
                entry_state=["Learner has an initial question"],
                must_establish=["Learner can name the shared facts"],
                avoid_repeating=[],
                bridge_from_previous=None,
                exit_state=["Learner can explain the idea"],
                blocks=blocks,
            )
        ],
    )


@pytest.mark.asyncio
async def test_repeated_ref_across_blocks_is_authored_once_in_first_use_order() -> None:
    plan = _plan(("approved-beta", "one"), ("approved-alpha", "two"), ("approved-beta", "three"))
    provider = ScriptedProvider({"entries": [_entry("approved-alpha"), _entry("approved-beta")]})

    sourcebook = await author_shared_sourcebook(plan, provider=provider)

    assert [entry.id for entry in sourcebook.entries] == ["approved-beta", "approved-alpha"]
    assert [entry.provenance_refs for entry in sourcebook.entries] == [
        ["fact:approved-beta"],
        ["fact:approved-alpha"],
    ]
    assert provider.calls[0].capability_id == "shared_sourcebook_authoring"
    assert provider.calls[0].is_repair is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"entries": []}, "omitted approved sourcebook refs"),
        ({"entries": [_entry("approved-a"), _entry("unsupported")]}, "unsupported sourcebook ref"),
        ({"entries": [_entry("approved-a"), _entry("approved-a")]}, "duplicate sourcebook ref"),
    ],
)
async def test_provider_must_cover_exactly_the_approved_ref_set(
    payload: dict[str, Any], message: str
) -> None:
    plan = _plan(("approved-a", "one"))
    provider = ScriptedProvider(payload, payload)

    with pytest.raises(AuthoringEngineError, match="REPAIR_EXHAUSTED") as caught:
        await author_shared_sourcebook(plan, provider=provider)

    assert message in str(caught.value.errors[0].message) or message in str(caught.value)
    assert len(provider.calls) == 2
    assert provider.calls[1].is_repair is True


@pytest.mark.asyncio
async def test_malformed_output_gets_one_bounded_semantic_repair() -> None:
    plan = _plan(("approved-a", "one"))
    provider = ScriptedProvider(
        {
            "entries": [
                {
                    "type": "definition",
                    "purpose": "missing association",
                    "content": {},
                    "provenance_refs": ["fact:approved-a"],
                }
            ]
        },
        {"entries": [_entry("approved-a")]},
    )

    sourcebook = await author_shared_sourcebook(plan, provider=provider)

    assert [entry.id for entry in sourcebook.entries] == ["approved-a"]
    assert len(provider.calls) == 2
    assert provider.calls[1].is_repair is True


@pytest.mark.asyncio
async def test_config_or_provider_terminal_error_is_not_semantically_repaired() -> None:
    plan = _plan(("approved-a", "one"))
    provider = ScriptedProvider(
        AuthoringProviderTerminalError("authentication", "API key rejected")
    )

    with pytest.raises(AuthoringEngineError, match="PROVIDER_FAILURE"):
        await author_shared_sourcebook(plan, provider=provider)

    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_stale_plan_hash_is_rejected_before_provider_dispatch() -> None:
    plan = _plan(("approved-a", "one"))
    provider = ScriptedProvider({"entries": [_entry("approved-a")]})

    with pytest.raises(SharedSourcebookAuthoringError, match="hash is stale"):
        await author_shared_sourcebook(
            plan,
            expected_teaching_plan_hash="0" * 64,
            provider=provider,
        )

    assert provider.calls == []


@pytest.mark.asyncio
async def test_needs_without_approved_ref_fail_closed() -> None:
    plan = _plan(("approved-a", "one"))
    block = plan.sections[0].blocks[0].model_copy(update={"sourcebook_refs": []})
    plan = plan.model_copy(
        update={
            "sections": [plan.sections[0].model_copy(update={"blocks": [block]})],
        }
    )
    provider = ScriptedProvider({"entries": []})

    with pytest.raises(SharedSourcebookAuthoringError, match="no approved sourcebook_refs"):
        await author_shared_sourcebook(plan, provider=provider)

    assert provider.calls == []


def test_approved_ref_whitespace_cannot_be_normalized_into_a_new_identity() -> None:
    plan = _plan(("approved-a ", "one"))

    with pytest.raises(SharedSourcebookAuthoringError, match="non-canonical sourcebook ref"):
        # The ref is part of the approved plan identity and must remain byte-for-byte exact.
        approved_sourcebook_refs(plan)


@pytest.mark.asyncio
async def test_plan_without_refs_returns_empty_sourcebook_without_provider_call() -> None:
    plan = _plan(("approved-a", "one"))
    block = (
        plan.sections[0]
        .blocks[0]
        .model_copy(update={"sourcebook_needs": [], "sourcebook_refs": []})
    )
    plan = plan.model_copy(
        update={
            "sections": [plan.sections[0].model_copy(update={"blocks": [block]})],
        }
    )
    provider = ScriptedProvider()

    sourcebook = await author_shared_sourcebook(plan, provider=provider)

    assert sourcebook.entries == []
    assert provider.calls == []

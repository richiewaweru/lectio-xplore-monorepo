"""Author the immutable semantic sourcebook for an approved Teaching Plan.

The Teaching Plan owns sourcebook identities.  The provider supplies only the
content for those identities and must explicitly associate each draft entry
with exactly one approved reference.  This adapter deliberately sits beside
the legacy sourcebook writer until the Phase 9 shadow path is accepted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from curriculum.lesson_sourcebook.models import (
    LessonSourcebook,
    SourcebookEntry,
    SourcebookEntryType,
)
from curriculum.prompts import lesson_sourcebook_writer_prompt
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringProvider,
    AuthoringRegistry,
    AuthoringRequest,
    LLMAuthoringProvider,
)
from infra.authoring.model_policy import SHARED_SOURCEBOOK_AUTHORING
from infra.authoring.models import AuthoringValidationError
from infra.execution.call_budget import CallBudget, CallBudgetLedger


class SharedSourcebookAuthoringError(ValueError):
    """An approved sourcebook contract cannot be satisfied."""


class SharedSourcebookEntryDraft(BaseModel):
    """Provider content with a code-validated approved identity association."""

    model_config = ConfigDict(extra="forbid")

    approved_ref_id: str = Field(min_length=1)
    type: SourcebookEntryType
    purpose: str = Field(min_length=1)
    content: dict[str, Any]
    provenance_refs: list[str] = Field(min_length=1)


class SharedSourcebookDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[SharedSourcebookEntryDraft] = Field(default_factory=list)


def approved_sourcebook_refs(plan: TeachingPlan) -> tuple[str, ...]:
    """Return approved sourcebook identities in first-use order.

    A reference can be used by several blocks, but it is authored once.  A
    block that asks for sourcebook content without an approved identity fails
    closed because the provider cannot safely invent a binding.
    """

    if plan.approval_status != "approved":
        raise SharedSourcebookAuthoringError(
            "shared sourcebook authoring requires an approved Teaching Plan"
        )
    if not plan.teaching_plan_id:
        raise SharedSourcebookAuthoringError("approved Teaching Plan is missing teaching_plan_id")
    if plan.revision is None or plan.revision < 1:
        raise SharedSourcebookAuthoringError(
            "approved Teaching Plan is missing a positive revision"
        )

    ordered: list[str] = []
    seen: set[str] = set()
    for section in plan.sections:
        for block in section.blocks:
            refs = list(block.sourcebook_refs)
            if block.sourcebook_needs and not refs:
                raise SharedSourcebookAuthoringError(
                    f"block {block.id!r} has sourcebook_needs but no approved sourcebook_refs"
                )
            for ref in refs:
                if not isinstance(ref, str) or not ref:
                    raise SharedSourcebookAuthoringError(
                        f"block {block.id!r} contains an empty approved sourcebook ref"
                    )
                if ref != ref.strip():
                    raise SharedSourcebookAuthoringError(
                        f"block {block.id!r} contains a non-canonical sourcebook ref {ref!r}"
                    )
                if ref not in seen:
                    seen.add(ref)
                    ordered.append(ref)
    return tuple(ordered)


def _sourcebook_contract_validator(
    _definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    try:
        draft = SharedSourcebookDraft.model_validate(payload)
    except ValidationError as exc:
        return [AuthoringValidationError("", str(exc))]

    requested = [str(ref) for ref in request.inputs.get("approved_sourcebook_refs", ())]
    allowed = set(requested)
    errors: list[str] = []
    associated: list[str] = []
    for index, entry in enumerate(draft.entries):
        ref = entry.approved_ref_id
        if any(not provenance_ref.strip() for provenance_ref in entry.provenance_refs):
            errors.append(f"entry {index} has an empty provenance ref")
        if ref not in allowed:
            errors.append(f"entry {index} has unsupported sourcebook ref {ref!r}")
            continue
        if ref in associated:
            errors.append(f"provider returned duplicate sourcebook ref {ref!r}")
            continue
        associated.append(ref)

    missing = [ref for ref in requested if ref not in set(associated)]
    if missing:
        errors.append(f"provider omitted approved sourcebook refs {missing!r}")
    if len(draft.entries) != len(requested):
        errors.append(
            "provider must return exactly one sourcebook entry for each unique approved ref"
        )
    return [AuthoringValidationError("", error) for error in errors]


def _sourcebook_definition() -> AuthoringDefinition:
    return AuthoringDefinition(
        capability_id=SHARED_SOURCEBOOK_AUTHORING,
        native_path="shared_document",
        modes=("generate",),
        instructions=(
            lesson_sourcebook_writer_prompt()
            + "\nFor every entry, include approved_ref_id exactly as supplied. "
            "It is the code-owned identity association; provenance_refs must remain "
            "the supporting fact or source citations and must not be replaced by it."
        ),
        payload_schema=SharedSourcebookDraft.model_json_schema(),
        required_inputs=("teaching_plan", "approved_sourcebook_refs"),
        validator_refs=("shared_sourcebook.schema", "shared_sourcebook.refs"),
    )


def _registry() -> AuthoringRegistry:
    return (
        AuthoringRegistry()
        .with_validator("shared_sourcebook.schema", lambda *_args, **_kwargs: [])
        .with_validator("shared_sourcebook.refs", _sourcebook_contract_validator)
    )


async def author_shared_sourcebook(
    plan: TeachingPlan,
    *,
    expected_teaching_plan_hash: str | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    work_order_id: str | None = None,
    trace_id: str | None = None,
    call_budget: CallBudget | None = None,
    budget_ledger: CallBudgetLedger | None = None,
) -> LessonSourcebook:
    """Generate one sourcebook bound to the exact approved plan hash.

    The engine owns transport handling and allows one semantic repair.  The
    adapter performs no semantic retry for configuration, authentication, or
    programming errors raised by the provider boundary.
    """

    refs = approved_sourcebook_refs(plan)
    plan_hash = teaching_plan_content_hash(plan)
    if expected_teaching_plan_hash is not None and expected_teaching_plan_hash != plan_hash:
        raise SharedSourcebookAuthoringError(
            "Teaching Plan hash is stale: supplied hash does not match the approved plan"
        )

    result_entries: list[SourcebookEntry] = []
    if refs:
        plan_id = str(plan.teaching_plan_id)
        revision = int(plan.revision or 0)
        request = AuthoringRequest(
            work_order_id=work_order_id or f"sourcebook:{plan_id}:{revision}:{plan_hash[:16]}",
            definition=_sourcebook_definition(),
            scoped_request={
                "stage": "shared_sourcebook_authoring",
                "teaching_plan_id": plan_id,
                "teaching_plan_revision": revision,
                "teaching_plan_hash": plan_hash,
            },
            inputs={
                "teaching_plan": plan.model_dump(mode="json"),
                "approved_sourcebook_refs": list(refs),
                "sourcebook_needs": [
                    {"block_id": block.id, "needs": list(block.sourcebook_needs)}
                    for section in plan.sections
                    for block in section.blocks
                    if block.sourcebook_needs
                ],
            },
            teaching_revision=revision,
            source_identities=(plan_id, plan_hash),
            mode="generate",
            trace_id=trace_id,
        )
        selected_engine = engine
        if selected_engine is None:
            selected_engine = AuthoringEngine(
                registry=_registry(),
                provider=provider or LLMAuthoringProvider(node_name=SHARED_SOURCEBOOK_AUTHORING),
                max_repair_attempts=1,
                max_provider_calls=2,
                budget_ledger=budget_ledger,
            )
        result = await selected_engine.execute(
            request,
            provider=provider,
            call_budget=call_budget,
        )
        draft = SharedSourcebookDraft.model_validate(result.payload)
        by_ref = {entry.approved_ref_id: entry for entry in draft.entries}
        result_entries = [
            SourcebookEntry(
                id=ref,
                type=by_ref[ref].type,
                purpose=by_ref[ref].purpose,
                content=dict(by_ref[ref].content),
                provenance_refs=list(by_ref[ref].provenance_refs),
            )
            for ref in refs
        ]

    return LessonSourcebook(
        teaching_plan_id=str(plan.teaching_plan_id),
        teaching_plan_revision=int(plan.revision or 0),
        teaching_plan_hash=plan_hash,
        entries=result_entries,
    )


__all__ = [
    "SharedSourcebookAuthoringError",
    "SharedSourcebookDraft",
    "SharedSourcebookEntryDraft",
    "approved_sourcebook_refs",
    "author_shared_sourcebook",
]

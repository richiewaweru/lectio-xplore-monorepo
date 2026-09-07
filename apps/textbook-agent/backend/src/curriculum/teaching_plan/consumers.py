"""Native consumers of an approved shared teaching revision."""

from __future__ import annotations

from typing import Any, Literal

from curriculum.teaching_plan.models import TeachingPlan, TeachingRevisionRecord
from curriculum.teaching_plan.revisions import TeachingRevisionStore

NativeTeachingConsumer = Literal["print", "learn"]


class TeachingRevisionUnavailableError(ValueError):
    code = "TEACHING_REVISION_UNAVAILABLE"


class TeachingRevisionNotApprovedError(ValueError):
    code = "TEACHING_REVISION_NOT_APPROVED"


def accept_approved_teaching_revision(
    state: dict[str, Any],
    *,
    consumer: NativeTeachingConsumer,
    revision: int | None = None,
) -> TeachingPlan:
    """Both Print and Learn accept the identical approved teaching revision.

    No fixture substitution: the consumer receives the stored plan bytes as
    validated TeachingPlan. Semantic roles/intents are preserved verbatim.
    """
    store = TeachingRevisionStore(state)
    if revision is None:
        approved = store.state.get("teaching_review", {}).get("approved_revision")
        if approved is None:
            # Fall back to the latest approved snapshot in the ledger.
            approved_rows = [
                row for row in store.list_revisions() if row.status == "approved"
            ]
            if not approved_rows:
                raise TeachingRevisionNotApprovedError(
                    f"{consumer} requires an approved teaching revision"
                )
            record = max(approved_rows, key=lambda row: row.revision)
        else:
            record = store.get_revision(int(approved))
            if record is None:
                raise TeachingRevisionUnavailableError(
                    f"approved teaching revision {approved} missing for {consumer}"
                )
    else:
        record = store.get_revision(revision)
        if record is None:
            raise TeachingRevisionUnavailableError(
                f"teaching revision {revision} missing for {consumer}"
            )
    if record.status not in {"approved", "superseded"}:
        raise TeachingRevisionNotApprovedError(
            f"{consumer} cannot consume teaching revision {record.revision} "
            f"with status {record.status!r}"
        )
    plan = TeachingPlan.model_validate(record.plan)
    # Stamp consumer handoff metadata without rewriting instructional meaning.
    handoffs = dict(state.get("teaching_consumer_handoffs") or {})
    handoffs[consumer] = {
        "teaching_plan_id": record.teaching_plan_id,
        "revision": record.revision,
        "preparation_hash": record.preparation_hash,
        "arc": plan.arc,
        "block_ids": [
            block.id for section in plan.sections for block in section.blocks
        ],
        "intents": [
            block.intent for section in plan.sections for block in section.blocks
        ],
    }
    state["teaching_consumer_handoffs"] = handoffs
    return plan


def assert_identical_consumer_handoffs(state: dict[str, Any]) -> None:
    """Prove Print and Learn pinned the same instructional identities."""
    handoffs = state.get("teaching_consumer_handoffs") or {}
    print_handoff = handoffs.get("print")
    learn_handoff = handoffs.get("learn")
    if not print_handoff or not learn_handoff:
        raise AssertionError("both print and learn handoffs are required")
    for key in ("teaching_plan_id", "revision", "preparation_hash", "block_ids", "intents"):
        if print_handoff.get(key) != learn_handoff.get(key):
            raise AssertionError(
                f"print/learn teaching handoff diverge on {key}: "
                f"{print_handoff.get(key)!r} vs {learn_handoff.get(key)!r}"
            )


def revision_record_as_dict(record: TeachingRevisionRecord) -> dict[str, Any]:
    return record.model_dump(mode="json")

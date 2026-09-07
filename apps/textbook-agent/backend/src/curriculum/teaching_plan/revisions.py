"""Teaching approval and revision storage (curriculum-owned)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from curriculum.teaching_plan.models import TeachingPlan, TeachingRevisionRecord


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TeachingRevisionStore:
    """In-memory / state-blob revision ledger.

    Persists under chunked generation state as ``teaching_revisions`` so Print
    and Learn can pin the same approved revision without fixture substitution.
    """

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._state = state if state is not None else {}
        self._state.setdefault("teaching_revisions", [])
        review = dict(self._state.get("teaching_review") or {})
        review.setdefault("revision", 1)
        review.setdefault("status", "pending")
        self._state["teaching_review"] = review

    @property
    def state(self) -> dict[str, Any]:
        return self._state

    def teaching_plan_id(self) -> str:
        existing = self._state.get("teaching_plan_id")
        if isinstance(existing, str) and existing.strip():
            return existing
        plan_id = str(uuid4())
        self._state["teaching_plan_id"] = plan_id
        return plan_id

    def current_revision(self) -> int:
        review = dict(self._state.get("teaching_review") or {})
        return int(review.get("revision") or 1)

    def list_revisions(self) -> list[TeachingRevisionRecord]:
        rows = self._state.get("teaching_revisions") or []
        return [TeachingRevisionRecord.model_validate(row) for row in rows]

    def get_revision(self, revision: int) -> TeachingRevisionRecord | None:
        for record in self.list_revisions():
            if record.revision == revision:
                return record
        return None

    def record_draft(
        self,
        plan: TeachingPlan | dict[str, Any],
        *,
        preparation_hash: str,
        revision: int | None = None,
    ) -> TeachingRevisionRecord:
        plan_payload = (
            plan.model_dump(mode="json")
            if isinstance(plan, TeachingPlan)
            else dict(plan)
        )
        rev = revision if revision is not None else self.current_revision()
        plan_id = self.teaching_plan_id()
        plan_payload["teaching_plan_id"] = plan_id
        plan_payload["revision"] = rev
        plan_payload["preparation_hash"] = preparation_hash
        plan_payload["approval_status"] = "pending"
        record = TeachingRevisionRecord(
            teaching_plan_id=plan_id,
            revision=rev,
            status="pending",
            preparation_hash=preparation_hash,
            plan=plan_payload,
            created_at=_utcnow(),
        )
        revisions = [
            row
            for row in (self._state.get("teaching_revisions") or [])
            if int(row.get("revision") or 0) != rev
        ]
        revisions.append(record.model_dump(mode="json"))
        self._state["teaching_revisions"] = revisions
        self._state["teaching_plan"] = deepcopy(plan_payload)
        review = dict(self._state.get("teaching_review") or {})
        review["status"] = "pending"
        review["revision"] = rev
        self._state["teaching_review"] = review
        return record

    def approve(
        self,
        *,
        expected_revision: int,
        reviewed_by: str | None = None,
        teacher_note: str | None = None,
    ) -> TeachingRevisionRecord:
        current = self.current_revision()
        if expected_revision != current:
            raise ValueError(
                f"stale teaching revision: expected {expected_revision}, current {current}"
            )
        pending = self.get_revision(expected_revision)
        if pending is None:
            raise ValueError(f"no teaching revision {expected_revision} to approve")
        approved = pending.model_copy(
            update={
                "status": "approved",
                "approved_at": _utcnow(),
                "reviewed_by": reviewed_by,
                "teacher_note": teacher_note,
            }
        )
        plan = dict(approved.plan)
        plan["approval_status"] = "approved"
        plan["revision"] = expected_revision
        approved = approved.model_copy(update={"plan": plan})

        revisions: list[dict[str, Any]] = []
        for row in self._state.get("teaching_revisions") or []:
            if int(row.get("revision") or 0) == expected_revision:
                revisions.append(approved.model_dump(mode="json"))
            else:
                # Prior approved revisions remain readable as superseded snapshots.
                if row.get("status") == "approved":
                    row = dict(row)
                    row["status"] = "superseded"
                revisions.append(row)
        self._state["teaching_revisions"] = revisions
        self._state["teaching_plan"] = deepcopy(plan)
        review = dict(self._state.get("teaching_review") or {})
        review["status"] = "approved"
        review["revision"] = expected_revision + 1
        review["reviewed_by"] = reviewed_by
        review["reviewed_at"] = _utcnow()
        review["teacher_note"] = teacher_note
        review["approved_revision"] = expected_revision
        self._state["teaching_review"] = review
        return approved

    def edit_plan(
        self,
        plan: TeachingPlan | dict[str, Any],
        *,
        preparation_hash: str,
        teacher_note: str | None = None,
    ) -> TeachingRevisionRecord:
        """Material pedagogical edit → new pending revision; old approved stays readable."""
        next_revision = self.current_revision()
        # If the latest approved revision equals next_revision - 0 wait:
        # after approve, current_revision is approved+1 (next pending slot).
        record = self.record_draft(
            plan,
            preparation_hash=preparation_hash,
            revision=next_revision,
        )
        if teacher_note:
            review = dict(self._state.get("teaching_review") or {})
            review["teacher_note"] = teacher_note
            self._state["teaching_review"] = review
        # Link supersession metadata on the new draft.
        revisions = list(self._state.get("teaching_revisions") or [])
        for index, row in enumerate(revisions):
            if int(row.get("revision") or 0) == next_revision:
                row = dict(row)
                approved = review_approved_revision(self._state)
                if approved is not None:
                    row["supersedes_revision"] = approved
                revisions[index] = row
        self._state["teaching_revisions"] = revisions
        return TeachingRevisionRecord.model_validate(
            next(r for r in revisions if int(r.get("revision") or 0) == next_revision)
        )


def review_approved_revision(state: dict[str, Any]) -> int | None:
    review = state.get("teaching_review") or {}
    value = review.get("approved_revision")
    return int(value) if value is not None else None

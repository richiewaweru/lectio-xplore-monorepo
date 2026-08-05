"""Persist whole-lesson planning artifacts in GenerationModel.chunked_state_json."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import GenerationModel
from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state

PAGE_DOCUMENT_KEY = "page_document_v2"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_page_document_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "lesson_packet": None,
        "catalogue": {
            "version": None,
            "teaching_projection_hash": None,
            "form_projection_hash": None,
        },
        "teaching_plan": None,
        "teaching_validation": None,
        "teaching_qc": [],
        "teaching_raw": None,
        "teaching_prompt": None,
        "teaching_review": {
            "status": "pending",
            "reviewed_by": None,
            "reviewed_at": None,
            "revision": 1,
            "teacher_note": None,
        },
        "form_plan": None,
        "form_validation": None,
        "form_qc": [],
        "form_raw": None,
        "form_prompt": None,
        "block_execution": {},
        "advisory_qc": [],
        "events": [],
        "last_heartbeat": None,
        "document_revision": 0,
    }


class PageDocumentRepository:
    def __init__(self, session: AsyncSession, generation_id: str) -> None:
        self.session = session
        self.generation_id = generation_id

    async def _load_generation(self) -> GenerationModel:
        generation = await self.session.get(GenerationModel, self.generation_id)
        if generation is None:
            raise KeyError(f"generation {self.generation_id!r} not found")
        return generation

    async def load_page_generation_state(self) -> dict[str, Any]:
        chunked = await load_chunked_state(self.generation_id, self.session)
        state = chunked.get(PAGE_DOCUMENT_KEY)
        if not isinstance(state, dict):
            state = empty_page_document_state()
        return deepcopy(state)

    async def _save(self, state: dict[str, Any], *, stage: str | None = None) -> dict[str, Any]:
        state = deepcopy(state)
        state["last_heartbeat"] = _now()
        patch: dict[str, Any] = {PAGE_DOCUMENT_KEY: state}
        if stage is not None:
            patch["stage"] = stage
        await persist_chunked_state(self.generation_id, patch, self.session)
        await self.session.commit()
        return state

    async def save_lesson_packet(self, packet: dict[str, Any]) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        state["lesson_packet"] = packet
        return await self._save(state)

    async def save_catalogue_meta(
        self,
        *,
        version: str,
        teaching_projection_hash: str | None = None,
        form_projection_hash: str | None = None,
    ) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        catalogue = dict(state.get("catalogue") or {})
        catalogue["version"] = version
        if teaching_projection_hash is not None:
            catalogue["teaching_projection_hash"] = teaching_projection_hash
        if form_projection_hash is not None:
            catalogue["form_projection_hash"] = form_projection_hash
        state["catalogue"] = catalogue
        return await self._save(state)

    async def save_teaching_plan(
        self,
        *,
        plan: dict[str, Any],
        validation: dict[str, Any],
        qc: list[dict[str, Any]],
        prompt: str | None = None,
        raw: str | None = None,
        stage: str = "awaiting_teaching_approval",
    ) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        state["teaching_plan"] = plan
        state["teaching_validation"] = validation
        state["teaching_qc"] = qc
        if prompt is not None:
            state["teaching_prompt"] = prompt
        if raw is not None:
            state["teaching_raw"] = raw
        review = dict(state.get("teaching_review") or {})
        review["status"] = "pending"
        review["revision"] = int(review.get("revision") or 1)
        state["teaching_review"] = review
        generation = await self._load_generation()
        generation.status = "awaiting_teaching_approval"
        return await self._save(state, stage=stage)

    async def save_teaching_review(
        self,
        *,
        status: str,
        expected_revision: int,
        reviewed_by: str | None = None,
        teacher_note: str | None = None,
    ) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        review = dict(state.get("teaching_review") or {})
        current = int(review.get("revision") or 1)
        if expected_revision != current:
            raise ValueError(
                f"stale teaching revision: expected {expected_revision}, current {current}"
            )
        review["status"] = status
        review["reviewed_by"] = reviewed_by
        review["reviewed_at"] = _now()
        review["teacher_note"] = teacher_note
        if status == "approved":
            review["revision"] = current + 1
        state["teaching_review"] = review
        stage = "planning_forms" if status == "approved" else "rejected_by_teacher"
        generation = await self._load_generation()
        generation.status = stage
        return await self._save(state, stage=stage)

    async def save_form_plan(
        self,
        *,
        plan: dict[str, Any],
        validation: dict[str, Any],
        qc: list[dict[str, Any]],
        prompt: str | None = None,
        raw: str | None = None,
    ) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        state["form_plan"] = plan
        state["form_validation"] = validation
        state["form_qc"] = qc
        if prompt is not None:
            state["form_prompt"] = prompt
        if raw is not None:
            state["form_raw"] = raw
        return await self._save(state, stage="writing_blocks")

    async def save_block_result(self, block_id: str, result: dict[str, Any]) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        execution = dict(state.get("block_execution") or {})
        execution[block_id] = result
        state["block_execution"] = execution
        return await self._save(state)

    async def save_qc_report(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        state["advisory_qc"] = findings
        return await self._save(state)

    async def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        state = await self.load_page_generation_state()
        events = list(state.get("events") or [])
        events.append({**event, "at": _now()})
        state["events"] = events[-500:]
        return await self._save(state)

    async def bump_document_revision(self) -> int:
        state = await self.load_page_generation_state()
        revision = int(state.get("document_revision") or 0) + 1
        state["document_revision"] = revision
        await self._save(state)
        return revision

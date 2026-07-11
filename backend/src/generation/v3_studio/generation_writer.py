from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.models import GenerationModel
from generation.v3_studio.planning_artifact import (
    parse_planning_artifact,
    planning_summary_from_artifact,
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_export_allowed(booklet_status: str) -> bool:
    return booklet_status in {
        "final_ready",
        "final_with_warnings",
        "draft_ready",
        "draft_with_warnings",
        "draft_needs_review",
    }


_QUALITY_MAP = {
    "final_ready": True,
    "final_with_warnings": True,
    "failed_unusable": False,
}


def _sections_from_document(document_json: Any) -> list[dict[str, Any]]:
    if not isinstance(document_json, dict):
        return []
    sections = document_json.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def _count_delivered_visuals(sections: list[dict[str, Any]]) -> int:
    delivered = 0
    for section in sections:
        diagram = section.get("diagram")
        if isinstance(diagram, dict) and isinstance(diagram.get("image_url"), str):
            if diagram.get("image_url"):
                delivered += 1
    return delivered


def _count_delivered_questions(sections: list[dict[str, Any]]) -> int:
    delivered = 0
    for section in sections:
        practice = section.get("practice")
        if isinstance(practice, dict):
            items = practice.get("items")
            if isinstance(items, list):
                delivered += sum(1 for item in items if isinstance(item, dict))
            problems = practice.get("problems")
            if isinstance(problems, list):
                delivered += sum(1 for item in problems if isinstance(item, dict))
        quiz = section.get("quiz")
        if isinstance(quiz, dict):
            delivered += 1
        check = section.get("check")
        if isinstance(check, dict):
            delivered += 1
    return delivered


class V3GenerationWriter:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_started(
        self,
        *,
        generation_id: str,
        user_id: str,
        subject: str,
        context: str,
        template_id: str,
        section_count: int,
        planned_visuals: int = 0,
        planned_questions: int = 0,
        component_count: int | None = None,
    ) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            report_json = self._default_report(
                section_count=section_count,
                planned_visuals=planned_visuals,
                planned_questions=planned_questions,
                planned_components=component_count or 0,
            )
            if model is None:
                model = GenerationModel(
                    id=generation_id,
                    user_id=user_id,
                    subject=subject,
                    context=context,
                    mode="v3",
                    status="running",
                    requested_template_id=template_id,
                    resolved_template_id=template_id,
                    requested_preset_id="v3-studio",
                    resolved_preset_id="v3-studio",
                    section_count=section_count,
                    quality_passed=None,
                    report_json=report_json,
                )
                session.add(model)
            else:
                model.user_id = user_id
                model.subject = subject
                model.context = context
                model.mode = "v3"
                model.status = "running"
                model.requested_template_id = template_id
                model.resolved_template_id = template_id
                model.requested_preset_id = "v3-studio"
                model.resolved_preset_id = "v3-studio"
                model.section_count = section_count
                model.quality_passed = None
                model.error = None
                model.error_type = None
                model.error_code = None
                model.completed_at = None
                model.report_json = self._merge_report(model.report_json, report_json)
            await session.commit()

    async def write_draft(self, generation_id: str, payload: dict[str, Any]) -> None:
        await self._write_pack_event(
            generation_id=generation_id,
            payload=payload,
            process_status="running",
        )

    async def write_final(self, generation_id: str, payload: dict[str, Any]) -> None:
        await self._write_pack_event(
            generation_id=generation_id,
            payload=payload,
            process_status="running",
        )

    async def write_generation_complete(self, generation_id: str, payload: dict[str, Any]) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None:
                return
            report = self._coerce_report(model.report_json, section_count=model.section_count or 0)
            booklet_status = str(payload.get("booklet_status") or report.get("booklet_status") or "")
            if booklet_status:
                report["booklet_status"] = booklet_status
            coherence = payload.get("coherence_review")
            if isinstance(coherence, dict):
                existing_coherence = report.get("coherence")
                if not isinstance(existing_coherence, dict):
                    existing_coherence = {}
                if isinstance(coherence.get("issues"), list):
                    report["coherence"] = coherence
                else:
                    existing_coherence["status"] = coherence.get("status")
                    report["coherence"] = existing_coherence
                summary = report.get("summary", {})
                if isinstance(summary, dict):
                    summary["blocking_issues"] = int(coherence.get("blocking_count") or 0)
                    summary["major_issues"] = int(coherence.get("major_count") or 0)
                    summary["minor_issues"] = int(coherence.get("minor_count") or 0)
                    report["summary"] = summary
            model.report_json = report
            model.quality_passed = _QUALITY_MAP.get(booklet_status)
            await session.commit()

    async def write_coherence_result(
        self,
        generation_id: str,
        coherence_dict: dict[str, Any],
    ) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None:
                return
            report = self._coerce_report(model.report_json, section_count=model.section_count or 0)
            report["coherence"] = coherence_dict

            summary = report.get("summary", {})
            if not isinstance(summary, dict):
                summary = {}
            summary["blocking_issues"] = int(coherence_dict.get("blocking_count") or 0)
            summary["major_issues"] = int(coherence_dict.get("major_count") or 0)
            summary["minor_issues"] = int(coherence_dict.get("minor_count") or 0)
            report["summary"] = summary
            model.report_json = report
            await session.commit()

    async def write_resource_finalised(self, generation_id: str, payload: dict[str, Any]) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None:
                return
            status = str(payload.get("status") or "")
            booklet_status = str(payload.get("booklet_status") or "")
            report = self._coerce_report(model.report_json, section_count=model.section_count or 0)
            report["booklet_status"] = booklet_status or report.get("booklet_status", "streaming_preview")

            summary = report.get("summary", {})
            if not isinstance(summary, dict):
                summary = {}
            planned_sections = int(summary.get("planned_sections") or model.section_count or 0)
            planned_visuals = int(summary.get("planned_visuals") or 0)
            planned_questions = int(summary.get("planned_questions") or 0)
            sections = _sections_from_document(model.document_json)
            assembled_sections = len(sections)
            ready_sections = assembled_sections
            missing_sections = max(planned_sections - assembled_sections, 0)
            delivered_visuals = _count_delivered_visuals(sections)
            delivered_questions = _count_delivered_questions(sections)

            if status in {"passed", "passed_with_warnings"}:
                model.status = "completed"
                model.quality_passed = True
                report["process_status"] = "completed"
            elif model.document_json:
                model.status = "partial"
                model.quality_passed = False
                report["process_status"] = "failed_finalisation"
            else:
                model.status = "failed"
                model.quality_passed = False
                report["process_status"] = "failed"

            summary["planned_sections"] = planned_sections
            summary["assembled_sections"] = assembled_sections
            summary["ready_sections"] = ready_sections
            summary["missing_sections"] = missing_sections
            summary["failed_sections"] = missing_sections
            summary["planned_visuals"] = planned_visuals
            summary["delivered_visuals"] = delivered_visuals
            summary["planned_questions"] = planned_questions
            summary["delivered_questions"] = delivered_questions
            summary["export_allowed"] = _is_export_allowed(str(report.get("booklet_status") or ""))
            report["summary"] = summary

            model.completed_at = _utc_now_naive()
            model.report_json = report
            await session.commit()

    async def write_failure(
        self,
        generation_id: str,
        *,
        message: str,
        error_type: str = "generation_warning",
        error_code: str = "v3_generation_warning",
    ) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None:
                return
            model.status = "failed"
            model.quality_passed = False
            model.error = message
            model.error_type = error_type
            model.error_code = error_code
            model.completed_at = _utc_now_naive()
            report = self._coerce_report(model.report_json, section_count=model.section_count or 0)
            report["process_status"] = "failed"
            model.report_json = report
            await session.commit()

    async def write_pdf_status(
        self,
        generation_id: str,
        *,
        status: str,
        error: str | None,
        debug: dict[str, Any] | None = None,
    ) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None:
                return
            report = self._coerce_report(model.report_json, section_count=model.section_count or 0)
            pdf = report.get("pdf", {})
            if not isinstance(pdf, dict):
                pdf = {}
            pdf["last_export_status"] = status
            pdf["last_error"] = error
            if debug is not None:
                pdf["last_debug"] = debug
            report["pdf"] = pdf
            model.report_json = report
            await session.commit()

    async def update_document_progress(
        self,
        generation_id: str,
        progress: dict[str, Any],
    ) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None or not isinstance(model.document_json, dict):
                return
            document = deepcopy(model.document_json)
            document["progress"] = deepcopy(progress)
            model.document_json = document
            await session.commit()

    async def update_document_progress_stage(
        self,
        generation_id: str,
        *,
        stage: str,
    ) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None or not isinstance(model.document_json, dict):
                return
            document = deepcopy(model.document_json)
            progress = document.get("progress")
            if not isinstance(progress, dict):
                progress = {}
            section_statuses = progress.get("sections")
            if not isinstance(section_statuses, dict):
                section_statuses = {}
            for section in _sections_from_document(document):
                section_id = section.get("section_id")
                if isinstance(section_id, str) and section_id:
                    section_statuses.setdefault(section_id, "pending")
            if stage == "completed":
                section_statuses = {
                    section_id: ("failed" if status == "failed" else "ready")
                    for section_id, status in section_statuses.items()
                }
            elif stage == "failed":
                section_statuses = {
                    section_id: ("ready" if status == "ready" else "failed")
                    for section_id, status in section_statuses.items()
                }
            document["progress"] = {
                "stage": stage,
                "sections": section_statuses,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            model.document_json = document
            await session.commit()

    async def get_document_json(
        self,
        generation_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None or model.user_id != user_id:
                return None
            if not isinstance(model.document_json, dict):
                return None
            return deepcopy(model.document_json)

    async def list_by_user(
        self,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[GenerationModel]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(GenerationModel)
                .where(
                    GenerationModel.user_id == user_id,
                    or_(
                        GenerationModel.mode == "v3",
                        GenerationModel.requested_preset_id == "v3-studio",
                    ),
                )
                .order_by(GenerationModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    async def get_generation_model(
        self,
        generation_id: str,
        user_id: str,
    ) -> GenerationModel | None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None or model.user_id != user_id:
                return None
            if model.mode != "v3" and model.requested_preset_id != "v3-studio":
                return None
            return model

    async def write_planning_artifact(
        self,
        *,
        generation_id: str,
        user_id: str,
        artifact: dict[str, Any],
    ) -> None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None or model.user_id != user_id:
                raise ValueError(
                    f"Generation {generation_id} not found for user {user_id}"
                )

            model.planning_spec_json = json.dumps(artifact)

            report = self._coerce_report(
                model.report_json,
                section_count=model.section_count or 0,
            )
            report["planning"] = planning_summary_from_artifact(artifact)
            model.report_json = report

            await session.commit()

    async def read_planning_artifact(
        self,
        generation_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None or model.user_id != user_id:
                return None
            return parse_planning_artifact(model.planning_spec_json)

    async def _write_pack_event(
        self,
        *,
        generation_id: str,
        payload: dict[str, Any],
        process_status: str,
    ) -> None:
        pack = payload.get("pack")
        if not isinstance(pack, dict):
            return

        async with self._session_factory() as session:
            model = await session.get(GenerationModel, generation_id)
            if model is None:
                return
            booklet_status = str(payload.get("booklet_status") or pack.get("status") or "streaming_preview")
            model.document_json = {"kind": "v3_booklet_pack", **pack}

            report = self._coerce_report(model.report_json, section_count=model.section_count or 0)
            summary = report.get("summary", {})
            if not isinstance(summary, dict):
                summary = {}
            planned_sections = int(summary.get("planned_sections") or model.section_count or 0)
            planned_visuals = int(summary.get("planned_visuals") or 0)
            planned_questions = int(summary.get("planned_questions") or 0)
            sections = _sections_from_document(model.document_json)
            assembled_sections = len(sections)
            missing_sections = max(planned_sections - assembled_sections, 0)
            delivered_visuals = _count_delivered_visuals(sections)
            delivered_questions = _count_delivered_questions(sections)

            report["process_status"] = process_status
            report["booklet_status"] = booklet_status
            summary["planned_sections"] = planned_sections
            summary["assembled_sections"] = assembled_sections
            summary["ready_sections"] = assembled_sections
            summary["missing_sections"] = missing_sections
            summary["failed_sections"] = missing_sections
            summary["planned_visuals"] = planned_visuals
            summary["delivered_visuals"] = delivered_visuals
            summary["planned_questions"] = planned_questions
            summary["delivered_questions"] = delivered_questions
            summary["export_allowed"] = _is_export_allowed(booklet_status)
            report["summary"] = summary
            model.report_json = report
            await session.commit()

    def _default_report(
        self,
        *,
        section_count: int,
        planned_visuals: int = 0,
        planned_questions: int = 0,
        planned_components: int = 0,
    ) -> dict[str, Any]:
        return {
            "pipeline_version": "v3",
            "report_schema": "v3_generation_report_v1",
            "process_status": "running",
            "booklet_status": "streaming_preview",
            "summary": {
                "planned_sections": section_count,
                "assembled_sections": 0,
                "ready_sections": 0,
                "missing_sections": section_count,
                "failed_sections": 0,
                "planned_components": planned_components,
                "planned_visuals": planned_visuals,
                "delivered_visuals": 0,
                "planned_questions": planned_questions,
                "delivered_questions": 0,
                "blocking_issues": 0,
                "major_issues": 0,
                "minor_issues": 0,
                "export_allowed": False,
            },
            "sections": [],
            "coherence": {
                "status": "pending",
                "issues": [],
            },
            "pdf": {
                "last_export_status": "not_attempted",
                "last_error": None,
            },
        }

    def _merge_report(self, current: Any, baseline: dict[str, Any]) -> dict[str, Any]:
        report = self._coerce_report(current, section_count=baseline["summary"]["planned_sections"])
        report["pipeline_version"] = baseline["pipeline_version"]
        report["report_schema"] = baseline["report_schema"]
        if not isinstance(report.get("pdf"), dict):
            report["pdf"] = baseline["pdf"]
        if not isinstance(report.get("coherence"), dict):
            report["coherence"] = baseline["coherence"]
        if not isinstance(report.get("summary"), dict):
            report["summary"] = baseline["summary"]
        return report

    def _coerce_report(self, current: Any, *, section_count: int) -> dict[str, Any]:
        if isinstance(current, dict):
            report = deepcopy(current)
        else:
            report = self._default_report(section_count=section_count)
        report.setdefault("pipeline_version", "v3")
        report.setdefault("report_schema", "v3_generation_report_v1")
        report.setdefault("process_status", "running")
        report.setdefault("booklet_status", "streaming_preview")
        report.setdefault("sections", [])
        report.setdefault(
            "coherence",
            {
                "status": "pending",
                "issues": [],
            },
        )
        coherence = report.get("coherence")
        if isinstance(coherence, dict):
            for stale_key in ("repair" + "_targets", "repaired" + "_target_ids"):
                coherence.pop(stale_key, None)
        report.setdefault(
            "pdf",
            {
                "last_export_status": "not_attempted",
                "last_error": None,
            },
        )
        summary = report.get("summary")
        if not isinstance(summary, dict):
            summary = {}
        summary.setdefault("planned_sections", section_count)
        summary.setdefault("assembled_sections", 0)
        summary.setdefault("ready_sections", 0)
        summary.setdefault("missing_sections", section_count)
        summary.setdefault("failed_sections", 0)
        summary.setdefault("planned_components", 0)
        summary.setdefault("planned_visuals", 0)
        summary.setdefault("delivered_visuals", 0)
        summary.setdefault("planned_questions", 0)
        summary.setdefault("delivered_questions", 0)
        summary.setdefault("blocking_issues", 0)
        summary.setdefault("major_issues", 0)
        summary.setdefault("minor_issues", 0)
        for stale_key in ("repair" + "_target_count", "repaired" + "_target_count"):
            summary.pop(stale_key, None)
        summary.setdefault("export_allowed", False)
        report["summary"] = summary
        return report


__all__ = ["V3GenerationWriter"]

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from telemetry.v3_trace import event_types as et
from telemetry.v3_trace.repository import V3TraceRepository

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class V3TraceWriter:
    def __init__(
        self,
        *,
        repository: V3TraceRepository,
        trace_id: str,
        generation_id: str,
    ) -> None:
        self._repo = repository
        self.trace_id = trace_id
        self.generation_id = generation_id
        self._last_booklet_status: str | None = None
        self._report: dict[str, Any] = {
            "trace_id": trace_id,
            "generation_id": generation_id,
            "summary": {},
        }

    async def start_run(
        self,
        *,
        user_id: str,
        blueprint_id: str,
        template_id: str,
        title: str | None,
        subject: str | None,
    ) -> None:
        payload = {
            "generation_id": self.generation_id,
            "user_id": user_id,
            "blueprint_id": blueprint_id,
            "template_id": template_id,
            "title": title,
            "subject": subject,
            "started_at": _utc_now_iso(),
        }
        self._report = {
            **self._report,
            "title": title,
            "subject": subject,
            "template_id": template_id,
            "blueprint_id": blueprint_id,
        }
        await self._repo.start_run(
            trace_id=self.trace_id,
            generation_id=self.generation_id,
            user_id=user_id,
            title=title,
            subject=subject,
            template_id=template_id,
            start_event_type=et.GENERATION_START_REQUESTED,
            start_event_payload=payload,
            phase="start",
        )

    async def record_blueprint_snapshot(
        self,
        *,
        blueprint_id: str,
        template_id: str,
        section_count: int,
        section_ids: list[str],
        component_count: int,
        visual_required_count: int,
        question_count: int,
    ) -> None:
        payload = {
            "blueprint_id": blueprint_id,
            "template_id": template_id,
            "section_count": section_count,
            "section_ids": section_ids,
            "component_count": component_count,
            "visual_required_count": visual_required_count,
            "question_count": question_count,
        }
        await self._record_event(
            phase="blueprint",
            event_type=et.BLUEPRINT_SNAPSHOT_SAVED,
            payload=payload,
        )
        await self._update_report(
            {
                "blueprint_id": blueprint_id,
                "template_id": template_id,
                "title": self._report.get("title"),
                "subject": self._report.get("subject"),
                "summary": {
                    **self._report.get("summary", {}),
                    "planned_sections": section_count,
                },
            }
        )

    async def record_work_orders(
        self,
        *,
        section_order_count: int,
        visual_order_count: int,
        question_order_count: int,
        answer_key_required: bool,
    ) -> None:
        await self._record_event(
            phase="execution",
            event_type=et.WORK_ORDERS_COMPILED,
            payload={
                "section_order_count": section_order_count,
                "visual_order_count": visual_order_count,
                "question_order_count": question_order_count,
                "answer_key_required": answer_key_required,
            },
        )

    async def record_execution_summary(
        self,
        *,
        sections_attempted: int,
        sections_succeeded: int,
        sections_failed: int,
        components_planned: int,
        components_delivered: int,
        questions_planned: int,
        questions_delivered: int,
        visuals_planned: int,
        visuals_delivered: int,
        warnings: list[str],
        failure_kinds: dict[str, int] | None = None,
    ) -> None:
        payload = {
            "sections_attempted": sections_attempted,
            "sections_succeeded": sections_succeeded,
            "sections_failed": sections_failed,
            "components_planned": components_planned,
            "components_delivered": components_delivered,
            "questions_planned": questions_planned,
            "questions_delivered": questions_delivered,
            "visuals_planned": visuals_planned,
            "visuals_delivered": visuals_delivered,
            "warnings": warnings,
            "failure_kinds": dict(failure_kinds or {}),
        }
        await self._record_event(
            phase="execution",
            event_type=et.EXECUTION_SUMMARY_READY,
            payload=payload,
        )
        await self._update_report(
            {
                "summary": {
                    **self._report.get("summary", {}),
                    "planned_visuals": visuals_planned,
                    "delivered_visuals": visuals_delivered,
                    "planned_questions": questions_planned,
                    "delivered_questions": questions_delivered,
                }
            }
        )

    async def record_visual_completed(
        self,
        *,
        generation_id: str,
        visual_id: str,
        attaches_to: str,
        component_id: str | None,
        parent_visual_id: str | None,
        mode: str,
        frame_count: int,
    ) -> None:
        await self._record_event(
            phase="execution",
            event_type=et.VISUAL_COMPLETED,
            payload={
                "generation_id": generation_id,
                "visual_id": visual_id,
                "attaches_to": attaches_to,
                "component_id": component_id,
                "parent_visual_id": parent_visual_id,
                "mode": mode,
                "frame_count": frame_count,
                "ok": True,
            },
        )

    async def record_visual_failed(
        self,
        *,
        generation_id: str,
        visual_id: str,
        attaches_to: str,
        component_id: str | None,
        parent_visual_id: str | None,
        mode: str,
        frame_count: int,
        error_summary: str,
    ) -> None:
        await self._record_event(
            phase="execution",
            event_type=et.VISUAL_FAILED,
            payload={
                "generation_id": generation_id,
                "visual_id": visual_id,
                "attaches_to": attaches_to,
                "component_id": component_id,
                "parent_visual_id": parent_visual_id,
                "mode": mode,
                "frame_count": frame_count,
                "ok": False,
                "error_summary": error_summary,
            },
        )

    async def record_draft_pack(
        self,
        *,
        booklet_status: str,
        planned_section_count: int,
        assembled_section_count: int,
        renderable: bool,
        incomplete_sections: list[str],
        missing_components_summary: dict[str, int],
        missing_visuals_summary: dict[str, int],
        warnings: list[str],
    ) -> None:
        payload = {
            "booklet_status": booklet_status,
            "planned_section_count": planned_section_count,
            "assembled_section_count": assembled_section_count,
            "renderable": renderable,
            "incomplete_sections": incomplete_sections,
            "missing_components_summary": missing_components_summary,
            "missing_visuals_summary": missing_visuals_summary,
            "warnings": warnings,
        }
        await self._record_event(
            phase="assembly",
            event_type=et.DRAFT_PACK_READY,
            payload=payload,
        )
        await self._update_report(
            {
                "booklet_status": booklet_status,
                "draft_available": assembled_section_count > 0 and renderable,
                "summary": {
                    **self._report.get("summary", {}),
                    "assembled_sections": assembled_section_count,
                },
            }
        )

    async def record_booklet_status(
        self,
        *,
        booklet_status: str,
        reason: str,
        draft_available: bool,
        final_available: bool,
        classroom_ready: bool,
        export_allowed: bool,
    ) -> None:
        if booklet_status == self._last_booklet_status:
            return
        self._last_booklet_status = booklet_status
        await self._record_event(
            phase="status",
            event_type=et.BOOKLET_STATUS_ASSIGNED,
            payload={
                "booklet_status": booklet_status,
                "reason": reason,
                "draft_available": draft_available,
                "final_available": final_available,
                "classroom_ready": classroom_ready,
                "export_allowed": export_allowed,
            },
        )
        await self._update_report(
            {
                "booklet_status": booklet_status,
                "draft_available": draft_available,
                "final_available": final_available,
                "classroom_ready": classroom_ready,
                "export_allowed": export_allowed,
            }
        )

    async def record_review_summary(
        self,
        *,
        minor_count: int,
        major_count: int,
        blocking_count: int,
        fatal_categories: list[str],
    ) -> None:
        await self._record_event(
            phase="review",
            event_type=et.COHERENCE_REPORT_READY,
            payload={
                "minor_count": minor_count,
                "major_count": major_count,
                "blocking_count": blocking_count,
                "fatal_categories": fatal_categories,
            },
        )
        await self._update_report(
            {
                "summary": {
                    **self._report.get("summary", {}),
                    "minor_issues": minor_count,
                    "major_issues": major_count,
                    "blocking_issues": blocking_count,
                }
            }
        )

    async def record_final_pack(
        self,
        *,
        booklet_status: str,
        final_section_count: int,
        warnings: list[str],
        classroom_ready: bool,
        export_allowed: bool,
    ) -> None:
        await self._record_event(
            phase="final",
            event_type=et.FINAL_PACK_READY,
            payload={
                "booklet_status": booklet_status,
                "final_section_count": final_section_count,
                "warnings": warnings,
                "classroom_ready": classroom_ready,
                "export_allowed": export_allowed,
            },
        )
        await self._update_report(
            {
                "booklet_status": booklet_status,
                "final_available": final_section_count > 0,
                "classroom_ready": classroom_ready,
                "export_allowed": export_allowed,
            }
        )

    async def record_terminal(
        self,
        *,
        terminal_event_type: str,
        process_status: str,
        booklet_status: str,
        draft_available: bool,
        final_available: bool,
        classroom_ready: bool,
        export_allowed: bool,
        error_summary: str | None,
    ) -> None:
        payload = {
            "process_status": process_status,
            "booklet_status": booklet_status,
            "draft_available": draft_available,
            "final_available": final_available,
            "classroom_ready": classroom_ready,
            "export_allowed": export_allowed,
            "error_summary": error_summary,
            "completed_at": _utc_now_iso(),
        }
        for attempt in (1, 2):
            try:
                await self._repo.append_event(
                    trace_id=self.trace_id,
                    phase="terminal",
                    event_type=terminal_event_type,
                    payload=payload,
                )
                await self._repo.update_report(
                    trace_id=self.trace_id,
                    status=process_status,
                    report={
                        **self._report,
                        "process_status": process_status,
                        "booklet_status": booklet_status,
                        "draft_available": draft_available,
                        "final_available": final_available,
                        "classroom_ready": classroom_ready,
                        "export_allowed": export_allowed,
                        "error_summary": error_summary,
                    },
                )
                return
            except Exception:  # noqa: BLE001
                logger.exception(
                    "v3 trace terminal write failed trace_id=%s generation_id=%s attempt=%s",
                    self.trace_id,
                    self.generation_id,
                    attempt,
                )

    async def _record_event(
        self,
        *,
        phase: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        try:
            await self._repo.append_event(
                trace_id=self.trace_id,
                phase=phase,
                event_type=event_type,
                payload=payload,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "v3 trace checkpoint write failed trace_id=%s generation_id=%s event=%s",
                self.trace_id,
                self.generation_id,
                event_type,
            )

    async def _update_report(self, patch: dict[str, Any]) -> None:
        self._report = {**self._report, **patch}
        try:
            await self._repo.update_report(
                trace_id=self.trace_id,
                report=self._report,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "v3 trace report update failed trace_id=%s generation_id=%s",
                self.trace_id,
                self.generation_id,
            )


__all__ = ["V3TraceWriter"]

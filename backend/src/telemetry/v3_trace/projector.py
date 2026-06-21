from __future__ import annotations

from telemetry.v3_trace.event_types import (
    ANSWER_KEY_COMPLETED,
    BOOKLET_STATUS_ASSIGNED,
    BLUEPRINT_ADJUSTED,
    BLUEPRINT_GENERATED,
    BLUEPRINT_SNAPSHOT_SAVED,
    COHERENCE_REVIEWED,
    COHERENCE_REPORT_READY,
    DRAFT_PACK_READY,
    GENERATION_COMPLETED,
    GENERATION_FAILED,
    GENERATION_START_REQUESTED,
    GENERATION_STARTED,
    QUESTIONS_COMPLETED,
    RESOURCE_FINALISED,
    SECTION_COMPLETED,
    SECTION_FAILED,
    EXECUTION_SUMMARY_READY,
    FINAL_PACK_READY,
    VISUAL_COMPLETED,
    VISUAL_FAILED,
    WORK_ORDERS_COMPILED,
)


def project_report(events: list[dict]) -> dict:
    report: dict = {
        "blueprint": None,
        "execution": {
            "sections": [],
            "visuals": [],
            "questions": [],
            "answer_key": None,
        },
        "review": None,
        "terminal": None,
        "llm_summary": {},
    }

    for event in events:
        event_type = event["event_type"]
        payload = event["payload"]

        if event_type == BLUEPRINT_GENERATED:
            report["blueprint"] = payload

        elif event_type == BLUEPRINT_SNAPSHOT_SAVED:
            report["blueprint"] = payload

        elif event_type == BLUEPRINT_ADJUSTED:
            if report.get("blueprint_adjustments") is None:
                report["blueprint_adjustments"] = []
            report["blueprint_adjustments"].append(payload)

        elif event_type == GENERATION_STARTED:
            report["generation"] = payload

        elif event_type == GENERATION_START_REQUESTED:
            report["generation"] = payload

        elif event_type == WORK_ORDERS_COMPILED:
            report["work_orders"] = payload

        elif event_type == EXECUTION_SUMMARY_READY:
            report["execution_summary"] = payload

        elif event_type == DRAFT_PACK_READY:
            report["draft"] = payload

        elif event_type == BOOKLET_STATUS_ASSIGNED:
            report["booklet_status"] = payload

        elif event_type == SECTION_COMPLETED:
            report["execution"]["sections"].append(
                {
                    "id": payload["section_id"],
                    "title": payload["section_title"],
                    "ok": payload["ok"],
                    "components": payload["component_count"],
                    "warnings": payload.get("warnings", []),
                }
            )

        elif event_type == SECTION_FAILED:
            report["execution"]["sections"].append(
                {
                    "id": payload["section_id"],
                    "title": payload["section_title"],
                    "ok": False,
                    "error_type": payload["error_type"],
                    "error": payload["error_summary"],
                    "node": payload["node"],
                    "attempt": payload["attempt"],
                }
            )

        elif event_type == VISUAL_COMPLETED:
            report["execution"]["visuals"].append(
                {
                    "section_id": payload["section_id"],
                    "mode": payload["mode"],
                    "frames": payload["frame_count"],
                    "ok": payload["ok"],
                }
            )

        elif event_type == VISUAL_FAILED:
            report["execution"]["visuals"].append(
                {
                    "section_id": payload["section_id"],
                    "mode": payload["mode"],
                    "ok": False,
                    "error": payload["error_summary"],
                    "attempt": payload["attempt"],
                }
            )

        elif event_type == QUESTIONS_COMPLETED:
            report["execution"]["questions"].append(
                {
                    "section_id": payload["section_id"],
                    "count": payload["question_count"],
                    "ok": payload["ok"],
                }
            )

        elif event_type == ANSWER_KEY_COMPLETED:
            report["execution"]["answer_key"] = {
                "style": payload["style"],
                "count": payload["question_count"],
                "ok": payload["ok"],
            }

        elif event_type == COHERENCE_REVIEWED:
            report["review"] = payload

        elif event_type == COHERENCE_REPORT_READY:
            report["review"] = payload

        elif event_type == FINAL_PACK_READY:
            report["final_pack"] = payload

        elif event_type in (GENERATION_COMPLETED, GENERATION_FAILED, RESOURCE_FINALISED):
            report["terminal"] = payload
            report["llm_summary"] = payload.get("llm_summary", {})

    return report

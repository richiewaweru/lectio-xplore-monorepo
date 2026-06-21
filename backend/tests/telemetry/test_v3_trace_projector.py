from __future__ import annotations

from telemetry.v3_trace.event_types import (
    BLUEPRINT_GENERATED,
    COHERENCE_REVIEWED,
    GENERATION_FAILED,
    SECTION_COMPLETED,
    SECTION_FAILED,
    VISUAL_FAILED,
)
from telemetry.v3_trace.projector import project_report


def test_project_successful_generation() -> None:
    events = [
        {
            "event_type": BLUEPRINT_GENERATED,
            "payload": {
                "blueprint_id": "b-1",
                "title": "T",
                "lens_ids": ["first_exposure"],
                "section_count": 2,
                "question_count": 4,
            },
        },
        {
            "event_type": SECTION_COMPLETED,
            "payload": {
                "section_id": "s1",
                "section_title": "Orient",
                "ok": True,
                "component_count": 3,
            },
        },
        {
            "event_type": SECTION_COMPLETED,
            "payload": {
                "section_id": "s2",
                "section_title": "Practice",
                "ok": True,
                "component_count": 4,
            },
        },
    ]

    report = project_report(events)
    assert report["blueprint"]["blueprint_id"] == "b-1"
    assert len(report["execution"]["sections"]) == 2
    assert all(section["ok"] for section in report["execution"]["sections"])


def test_project_failed_section_visible() -> None:
    events = [
        {
            "event_type": SECTION_FAILED,
            "payload": {
                "section_id": "practice",
                "section_title": "Try It",
                "node": "section_writer",
                "error_type": "schema_validation",
                "error_summary": "practice-stack field missing",
                "attempt": 2,
            },
        },
        {
            "event_type": VISUAL_FAILED,
            "payload": {
                "section_id": "practice",
                "mode": "diagram",
                "error_summary": "provider timeout",
                "attempt": 1,
            },
        },
    ]

    report = project_report(events)
    section = report["execution"]["sections"][0]
    assert section["ok"] is False
    assert section["error_type"] == "schema_validation"
    assert report["execution"]["visuals"][0]["ok"] is False


def test_coherence_issues_appear_in_review() -> None:
    events = [
        {
            "event_type": COHERENCE_REVIEWED,
            "payload": {
                "status": "failed",
                "blocking_count": 3,
                "major_count": 1,
                "minor_count": 0,
                "issues": [
                    {
                        "category": "missing_planned_content",
                        "severity": "blocking",
                        "message": "Section 'practice' missing practice-stack",
                        "executor": "section_writer",
                    }
                ],
            },
        },
    ]

    report = project_report(events)
    assert report["review"]["blocking_count"] == 3
    assert report["review"]["issues"][0]["category"] == "missing_planned_content"


def test_llm_summary_in_terminal() -> None:
    events = [
        {
            "event_type": GENERATION_FAILED,
            "payload": {
                "error_type": "coherence_unrecoverable",
                "error_summary": "34 blocking issues remain",
                "last_successful_phase": "review",
                "sections_ready": 2,
                "sections_failed": 1,
                "duration_seconds": 143.0,
                "llm_summary": {
                    "v3_stage1_planner": {
                        "calls": 1,
                        "cost_usd": 0.81,
                        "tokens_in": 3840,
                        "tokens_out": 2190,
                        "thinking_tokens": 4210,
                        "latency_ms_total": 87400,
                    }
                },
            },
        },
    ]

    report = project_report(events)
    assert report["terminal"]["error_type"] == "coherence_unrecoverable"
    assert report["llm_summary"]["v3_stage1_planner"]["cost_usd"] == 0.81

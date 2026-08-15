from __future__ import annotations

from v3_execution.booklet_status import collect_fatal_issue_categories, derive_booklet_status
from v3_execution.models import DraftPack
from v3_review.deterministic_checks import check_lectio_schema_validity


def test_no_sections_is_failed_unusable() -> None:
    status = derive_booklet_status(
        draft_section_count=0,
        render_valid=False,
        review_done=False,
        finalised=False,
        blocking_count=0,
        major_count=0,
        minor_count=0,
        fatal_issue_categories=set(),
    )
    assert status == "failed_unusable"


def test_review_not_done_with_draft_is_draft_ready() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=False,
        finalised=False,
        blocking_count=0,
        major_count=0,
        minor_count=0,
        fatal_issue_categories=set(),
    )
    assert status == "draft_ready"


def test_minor_issues_before_finalisation_is_draft_with_warnings() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=False,
        blocking_count=0,
        major_count=0,
        minor_count=1,
        fatal_issue_categories=set(),
    )
    assert status == "draft_with_warnings"


def test_major_issue_keeps_draft_needs_review() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=False,
        blocking_count=0,
        major_count=1,
        minor_count=0,
        fatal_issue_categories=set(),
    )
    assert status == "draft_needs_review"


def test_finalised_with_no_issues_is_final_ready() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=True,
        blocking_count=0,
        major_count=0,
        minor_count=0,
        fatal_issue_categories=set(),
    )
    assert status == "final_ready"


def test_finalised_with_minor_issues_is_final_with_warnings() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=True,
        blocking_count=0,
        major_count=0,
        minor_count=2,
        fatal_issue_categories=set(),
    )
    assert status == "final_with_warnings"


def test_fatal_categories_force_failed_unusable() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=True,
        blocking_count=0,
        major_count=0,
        minor_count=0,
        fatal_issue_categories={"internal_artifact_leak"},
    )
    assert status == "failed_unusable"


def test_failed_lane_cannot_be_reported_as_final() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=True,
        blocking_count=0,
        major_count=0,
        minor_count=0,
        fatal_issue_categories=set(),
        failed_lane_count=1,
        lane_count=2,
    )
    assert status == "failed_unusable"


def test_lane_failure_threshold_is_configurable() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=True,
        blocking_count=0,
        major_count=0,
        minor_count=0,
        fatal_issue_categories=set(),
        failed_lane_count=1,
        lane_count=2,
        max_failed_lane_fraction=0.5,
    )
    assert status == "final_ready"


def test_incomplete_section_cannot_be_reported_as_final() -> None:
    status = derive_booklet_status(
        draft_section_count=2,
        render_valid=True,
        review_done=True,
        finalised=True,
        blocking_count=0,
        major_count=0,
        minor_count=0,
        fatal_issue_categories=set(),
        incomplete_section_count=1,
        planned_section_count=2,
    )
    assert status == "failed_unusable"


def test_section_metadata_keys_do_not_create_schema_violations() -> None:
    pack = DraftPack(
        generation_id="gen-meta",
        blueprint_id="bp-meta",
        template_id="guided-concept-path",
        subject="Mathematics",
        status="draft_ready",
        sections=[
            {
                "section_id": "intro",
                "template_id": "guided-concept-path",
                "_component_order": ["explanation"],
                "_component_positions": {"explanation": 0},
                "_schema_warnings": [],
            }
        ],
    )

    issues = check_lectio_schema_validity(pack)
    fatal_categories = collect_fatal_issue_categories(issues)
    status = derive_booklet_status(
        draft_section_count=len(pack.sections),
        render_valid=bool(pack.sections),
        review_done=True,
        finalised=True,
        blocking_count=0,
        major_count=0,
        minor_count=len(issues),
        fatal_issue_categories=fatal_categories,
    )

    assert issues == []
    assert fatal_categories == set()
    assert status != "failed_unusable"

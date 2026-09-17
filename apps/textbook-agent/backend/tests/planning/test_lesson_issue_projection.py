from curriculum.lesson_review.issue_projection import collect_lesson_issues


def test_collects_coherence_realization_and_print_issues_with_deduplication() -> None:
    response = collect_lesson_issues(
        path="print",
        realization={
            "realization_id": "r-1",
            "status": "failed_recoverable",
            "error_summary": "writer failed",
        },
        states=[
            {
                "smart_lesson": {
                    "coherence_reports": {
                        "print": {
                            "issues": [
                                {"code": "FIGURE_MISSING", "message": "missing figure", "severity": "blocking", "figure_id": "fig-1"},
                                {"code": "FIGURE_MISSING", "message": "missing figure", "severity": "blocking", "figure_id": "fig-1"},
                            ]
                        }
                    }
                }
            }
        ],
        booklet_issues=[{"code": "PAGINATION", "message": "page overflow", "severity": "major"}],
    )

    assert len(response.issues) == 3
    assert response.counts.error == 2
    assert response.counts.warning == 1
    assert {issue.source for issue in response.issues} == {"coherence_review", "realization_status", "print_document"}


def test_collects_required_missing_figure_and_explicit_empty_state() -> None:
    response = collect_lesson_issues(
        path="learn",
        documents=[{"nodes": [{"kind": "figure", "id": "explain-1", "required": True, "status": "omitted_quality"}]}],
    )
    assert any(issue.code == "REQUIRED_FIGURE_MISSING" for issue in response.issues)
    assert any(issue.category == "figure" for issue in response.issues)
    assert response.counts.error >= 1

    empty = collect_lesson_issues(path="learn")
    assert empty.issues == []
    assert empty.counts.model_dump() == {"info": 0, "warning": 0, "error": 0}


def test_collects_learn_document_and_interaction_contract_failures() -> None:
    response = collect_lesson_issues(
        path="learn",
        documents=[
            {
                "version": 2,
                "id": "lesson-1",
                "title": "Lesson",
                "subject": "science",
                "source": "native_learn",
                "created_at": "now",
                "updated_at": "now",
                "nodes": [{"kind": "interaction", "id": "check-1", "type": "bad"}],
            }
        ],
    )

    assert response.counts.error >= 1
    assert any(issue.category == "interaction" for issue in response.issues)


def test_required_visual_slot_without_child_figure_is_an_issue() -> None:
    response = collect_lesson_issues(
        path="print",
        documents=[
            {
                "sections": [
                    {"id": "section-1", "title": "Explain", "visual_required": True, "blocks": []}
                ]
            }
        ],
    )

    assert any(issue.code == "REQUIRED_FIGURE_MISSING" for issue in response.issues)

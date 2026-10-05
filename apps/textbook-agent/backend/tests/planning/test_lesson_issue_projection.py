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


_PLAN_STATE = {
    "teaching_plan": {
        "sections": [
            {
                "slot_id": "explain",
                "blocks": [
                    {
                        "id": "explain-b1",
                        "visual": {"purpose": "See the cycle.", "must_show": ["evaporation"]},
                    },
                    {"id": "explain-b2"},
                ],
            }
        ]
    }
}
_REALIZATION = {"realization_id": "r-1", "status": "ready"}


def _figure_issues(documents: list[dict], *, states: list[dict] | None = None) -> list:
    response = collect_lesson_issues(
        path="print",
        realization=_REALIZATION,
        states=[_PLAN_STATE] if states is None else states,
        documents=documents,
    )
    return [issue for issue in response.issues if issue.code == "REQUIRED_FIGURE_MISSING"]


def test_plan_visual_without_bound_figure_is_an_issue() -> None:
    issues = _figure_issues([{"nodes": [{"kind": "paragraph", "id": "p1", "teaching_block_id": "explain-b1"}]}])

    assert [issue.target_id for issue in issues] == ["explain-b1"]
    assert issues[0].severity == "error"
    assert issues[0].category == "figure"


def test_plan_visual_with_bound_figure_is_clean() -> None:
    issues = _figure_issues(
        [{"nodes": [{"kind": "figure", "id": "f1", "teaching_block_id": "explain-b1", "status": "ready"}]}]
    )

    assert issues == []


def test_plan_visual_with_failed_figure_is_an_issue() -> None:
    issues = _figure_issues(
        [{"nodes": [{"kind": "figure", "id": "f1", "teaching_block_id": "explain-b1", "status": "failed"}]}]
    )

    assert [issue.target_id for issue in issues] == ["explain-b1"]


def test_plan_without_visual_never_requires_a_figure() -> None:
    state = {"teaching_plan": {"sections": [{"slot_id": "explain", "blocks": [{"id": "explain-b1"}]}]}}

    assert _figure_issues([{"nodes": [{"kind": "paragraph", "id": "p1"}]}], states=[state]) == []


def test_section_level_visual_required_flag_is_ignored() -> None:
    response = collect_lesson_issues(
        path="print",
        documents=[
            {"sections": [{"id": "section-1", "title": "Explain", "visual_required": True, "blocks": []}]}
        ],
    )

    assert not any(issue.code == "REQUIRED_FIGURE_MISSING" for issue in response.issues)

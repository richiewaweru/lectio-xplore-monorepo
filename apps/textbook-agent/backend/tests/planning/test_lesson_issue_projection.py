from curriculum.lesson_review.issue_projection import collect_lesson_issues


def test_collects_allow_listed_coherence_realization_issues_with_deduplication() -> None:
    # Deliberate change: the projection is now an allow-list. Raw coherence codes
    # that are not teacher-facing (FIGURE_MISSING here) and free-form legacy
    # booklet codes (PAGINATION) are excluded instead of surfaced verbatim.
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
                                {"code": "SLOPE_DRIFT", "message": "slope drifted", "severity": "blocking", "figure_id": "fig-1"},
                                {"code": "SLOPE_DRIFT", "message": "slope drifted", "severity": "blocking", "figure_id": "fig-1"},
                                {"code": "FIGURE_MISSING", "message": "missing figure", "severity": "blocking", "figure_id": "fig-1"},
                            ]
                        }
                    }
                }
            }
        ],
        booklet_issues=[{"code": "PAGINATION", "message": "page overflow", "severity": "major"}],
    )

    assert [issue.code for issue in response.issues] == ["REALIZATION_FAILED", "SLOPE_DRIFT"]
    assert [issue.group for issue in response.issues] == ["blocking", "needs_look"]
    assert response.counts.error == 1
    assert response.counts.warning == 1
    assert response.counts.attention == 2
    assert {issue.source for issue in response.issues} == {"coherence_review", "realization_status"}
    failed = response.issues[0]
    assert failed.message == "This lesson didn't finish building."
    assert failed.details == "writer failed"


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
    assert empty.counts.model_dump() == {
        "info": 0,
        "warning": 0,
        "error": 0,
        "blocking": 0,
        "needs_look": 0,
        "informational": 0,
        "dismissed": 0,
        "attention": 0,
    }


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
        [
            {
                "nodes": [
                    {
                        "kind": "figure",
                        "id": "f1",
                        "teaching_block_id": "explain-b1",
                        "status": "ready",
                        "asset_id": "https://storage.example.test/f1.png",
                    }
                ]
            }
        ]
    )

    assert issues == []


def test_learn_figure_without_image_is_an_issue_only_when_ready() -> None:
    document = {"nodes": [{"kind": "figure", "id": "f1", "teaching_block_id": "explain-b1", "asset_id": None}]}
    issues = _figure_issues([document])
    assert [issue.target_id for issue in issues] == ["explain-b1"]
    # Teacher copy replaces the raw message; the original stays behind "details".
    assert issues[0].message == "A figure this lesson needs could not be created."
    assert issues[0].details == "The planned figure has no image yet."
    assert issues[0].severity == "error"

    pending = collect_lesson_issues(
        path="learn",
        realization={"realization_id": "r-1", "status": "queued"},
        states=[_PLAN_STATE],
        documents=[document],
    )
    assert [i for i in pending.issues if i.code == "REQUIRED_FIGURE_MISSING"] == []


def test_print_shaped_figure_block_matches_by_node_id_and_needs_image() -> None:
    from curriculum.teaching_plan.models import TeachingPlanBlock
    from document.shared_lesson.composer import figure_item_for_block

    block = {
        "id": "explain-b1",
        "position": 0,
        "intent": "explain",
        "brief": "Explain the cycle.",
        "evidence": "Source text",
        "visual": {"purpose": "See the cycle.", "must_show": ["evaporation"]},
    }
    TeachingPlanBlock.model_validate(block)
    state = {"teaching_plan": {"sections": [{"slot_id": "explain", "blocks": [block]}]}}
    node_id = figure_item_for_block("explain", TeachingPlanBlock.model_validate(block)).id

    with_image = {
        "sections": [
            {
                "blocks": [
                    {
                        "id": node_id,
                        "object": "figure",
                        "content": {"asset": {"kind": "image", "status": "ready", "src": "https://x.test/a.png"}},
                    }
                ]
            }
        ]
    }
    assert _figure_issues([with_image], states=[state]) == []

    without_image = {
        "sections": [
            {
                "blocks": [
                    {
                        "id": node_id,
                        "object": "figure",
                        "content": {"asset": {"kind": "image", "status": "pending"}},
                    }
                ]
            }
        ]
    }
    issues = _figure_issues([without_image], states=[state])
    assert [i.details for i in issues] == ["The planned figure has no image yet."]


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


def test_unavailable_learn_figure_is_an_advisory_warning_with_its_reason() -> None:
    document = {
        "nodes": [
            {
                "kind": "figure",
                "id": "f1",
                "teaching_block_id": "explain-b1",
                "asset_id": None,
                "status": "unavailable",
                "unavailable_reason": "The figure service was unavailable for this figure.",
            }
        ]
    }
    issues = _figure_issues([document])
    assert [i.target_id for i in issues] == ["explain-b1"]
    assert issues[0].severity == "warning"
    assert issues[0].group == "needs_look"
    assert issues[0].dismissible is True
    assert "The figure service was unavailable for this figure." in (issues[0].details or "")


def test_unavailable_print_figure_is_an_advisory_warning() -> None:
    document = {
        "sections": [
            {
                "blocks": [
                    {
                        "id": "f1",
                        "object": "figure",
                        "teaching_block_id": "explain-b1",
                        "content": {"asset": {"kind": "image", "status": "failed"}},
                    }
                ]
            }
        ]
    }
    issues = _figure_issues([document])
    assert [i.severity for i in issues] == ["warning"]

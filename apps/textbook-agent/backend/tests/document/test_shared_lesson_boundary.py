from __future__ import annotations

import pytest

from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection
from document.shared_lesson import boundary
from document.shared_lesson.boundary import (
    BoundarySemanticVerdict,
    validate_and_repair_boundary,
)
from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode, SharedSection
from document.shared_lesson.writer import SectionWriterRequest


def _plan(
    slot_id: str,
    *,
    title: str,
    entry: tuple[str, ...] = (),
    bridge: str | None = None,
    must: tuple[str, ...] = (),
    exit_state: tuple[str, ...] = (),
) -> TeachingPlanSection:
    return TeachingPlanSection(
        slot_id=slot_id,
        display_title=title,
        entry_state=list(entry),
        must_establish=list(must),
        avoid_repeating=[],
        bridge_from_previous=bridge,
        exit_state=list(exit_state),
        blocks=[
            TeachingPlanBlock(
                id=f"{slot_id}-block",
                position=0,
                intent="explain the concept",
                brief="explain the concept",
                evidence="learner can explain the concept",
            )
        ],
    )


def _section(section_id: str, position: int, text: str) -> SharedSection:
    return SharedSection(
        id=section_id,
        title="Light and energy" if section_id == "s1" else "Photosynthesis",
        position=position,
        nodes=(
            ParagraphNode(
                id=f"{section_id}-node",
                teaching_block_id=f"{section_id}-block",
                display=ParagraphDisplay(text=text),
            ),
        ),
    )


def _writer_request(plan: TeachingPlanSection) -> SectionWriterRequest:
    composition = SectionCompositionPlan(
        section_slot_id=plan.slot_id,
        items=(
            CompositionItem(
                id=f"{plan.slot_id}-node",
                kind="paragraph",
                teaching_block_id=f"{plan.slot_id}-block",
                semantic_role="explanation",
            ),
        ),
    )
    return SectionWriterRequest(section=plan, composition_plan=composition)


class _Semantic:
    def __init__(self, verdict):
        self.verdict = list(verdict) if isinstance(verdict, list) else verdict
        self.calls = 0

    async def __call__(self, _request):
        self.calls += 1
        if isinstance(self.verdict, list):
            return self.verdict[min(self.calls - 1, len(self.verdict) - 1)]
        return self.verdict


class _Repair:
    def __init__(self, section):
        self.section = section
        self.calls = 0
        self.requests = []

    async def repair_section(self, request):
        self.calls += 1
        self.requests.append(request)
        return self.section


def _boundary(*, next_text: str = "Light energy supports photosynthesis."):
    previous_plan = _plan(
        "s1", title="Light and energy", must=("light energy",), exit_state=("light energy",)
    )
    next_plan = _plan(
        "s2",
        title="Photosynthesis",
        entry=("light energy",),
        bridge="light energy supports photosynthesis",
        must=("photosynthesis",),
        exit_state=("photosynthesis",),
    )
    previous = _section("s1", 0, "Sunlight provides light energy.")
    following = _section("s2", 1, next_text)
    return previous_plan, next_plan, previous, following


@pytest.mark.asyncio
async def test_deterministic_boundary_failure_precedes_semantic_and_repairs_once() -> None:
    previous_plan, next_plan, previous, following = _boundary(
        next_text="Photosynthesis makes food."
    )
    semantic = _Semantic(BoundarySemanticVerdict(status="pass"))
    repair = _Repair(_section("s2", 1, "Light energy supports photosynthesis."))

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.passed
    assert result.semantic_calls == 1
    assert semantic.calls == 1
    assert repair.calls == 1
    assert result.previous_section == previous
    assert result.next_section.nodes[0].display.text.startswith("Light energy")


@pytest.mark.asyncio
async def test_missing_repair_engine_uses_bounded_default_writer_adapter(monkeypatch) -> None:
    previous_plan, next_plan, previous, following = _boundary(
        next_text="Photosynthesis makes food."
    )
    semantic = _Semantic(BoundarySemanticVerdict(status="pass"))
    provider_calls = []

    async def repair_provider(payload):
        provider_calls.append(payload)
        return {
            "nodes": [
                {
                    "id": "s2-node",
                    "kind": "paragraph",
                    "teaching_block_id": "s2-block",
                    "display": {"text": "Light energy supports photosynthesis."},
                }
            ]
        }

    monkeypatch.setattr(boundary, "_default_provider", repair_provider)

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.passed
    assert result.repair_attempted
    assert result.semantic_calls == 1
    assert semantic.calls == 1
    assert len(provider_calls) == 1
    assert provider_calls[0]["repair"]["scope"] == "targeted"
    assert result.previous_section == previous


@pytest.mark.asyncio
async def test_default_adapter_does_not_repair_issues_on_both_boundary_sides(monkeypatch) -> None:
    previous_plan, next_plan, previous, following = _boundary(
        next_text="Photosynthesis makes food."
    )
    previous = _section("s1", 0, "Plants use sunlight.")

    async def unexpected_provider_call(_payload):
        pytest.fail("ambiguous boundary must not invoke a repair provider")

    monkeypatch.setattr(boundary, "_default_provider", unexpected_provider_call)
    semantic = _Semantic(BoundarySemanticVerdict(status="pass"))

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        writer_requests={
            "s1": _writer_request(previous_plan),
            "s2": _writer_request(next_plan),
        },
    )

    assert result.failure_code == "boundary_repair_ambiguous"
    assert result.repair_attempted is False
    assert result.semantic_calls == 0
    assert semantic.calls == 0


@pytest.mark.asyncio
async def test_deterministic_repair_is_blocked_by_post_repair_semantic_issue() -> None:
    previous_plan, next_plan, previous, following = _boundary(
        next_text="Photosynthesis makes food."
    )
    semantic = _Semantic(
        BoundarySemanticVerdict(
            status="issue",
            issue=ContinuityIssue(
                issue_code="semantic_bridge_gap",
                affected_section_id="s2",
                explanation="the opening still does not connect the prerequisite",
                required_correction="add the approved bridge to the opening",
            ),
        )
    )
    repair = _Repair(_section("s2", 1, "Light energy supports photosynthesis."))

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.status == "recoverable_failure"
    assert result.failure_code == "boundary_semantic_revalidation_failed"
    assert result.semantic_calls == 1
    assert semantic.calls == 1
    assert repair.calls == 1
    assert result.previous_section == previous


@pytest.mark.asyncio
async def test_malformed_semantic_output_is_typed_and_never_repaired() -> None:
    previous_plan, next_plan, previous, following = _boundary()
    semantic = _Semantic({"status": "rewrite", "section": "s2"})
    repair = _Repair(following)

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.status == "recoverable_failure"
    assert result.failure_code == "boundary_semantic_output_invalid"
    assert result.semantic_calls == 1
    assert repair.calls == 0


@pytest.mark.asyncio
async def test_semantic_issue_targets_one_section_and_preserves_sibling() -> None:
    previous_plan, next_plan, previous, following = _boundary()
    semantic = _Semantic(
        [
            BoundarySemanticVerdict(
                status="issue",
                issue=ContinuityIssue(
                    issue_code="semantic_bridge_gap",
                    affected_section_id="s2",
                    explanation="the opening does not connect the prerequisite",
                    required_correction="add the approved bridge to the opening",
                ),
            ),
            BoundarySemanticVerdict(status="pass"),
        ]
    )
    repaired = _section("s2", 1, "Light energy supports photosynthesis.")
    repair = _Repair(repaired)

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.passed
    assert result.repair_attempted
    assert result.semantic_calls == 2
    assert repair.calls == 1
    assert semantic.calls == 2
    assert repair.requests[0].target_section_id == "s2"
    assert result.previous_section == previous


@pytest.mark.asyncio
async def test_repeated_failure_is_recoverable_and_budget_stays_one_call() -> None:
    previous_plan, next_plan, previous, following = _boundary()
    semantic = _Semantic(
        BoundarySemanticVerdict(
            status="issue",
            issue=ContinuityIssue(
                issue_code="semantic_bridge_gap",
                affected_section_id="s2",
                explanation="the opening does not connect the prerequisite",
                required_correction="add the approved bridge to the opening",
            ),
        )
    )
    repair = _Repair(_section("s2", 1, "still unrelated content"))

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.status == "recoverable_failure"
    assert result.failure_code == "boundary_revalidation_failed"
    assert repair.calls == 1
    assert result.previous_section == previous


@pytest.mark.asyncio
async def test_internal_planning_leak_in_repaired_section_fails_closed() -> None:
    previous_plan, next_plan, previous, following = _boundary()
    semantic = _Semantic(
        BoundarySemanticVerdict(
            status="issue",
            issue=ContinuityIssue(
                issue_code="semantic_bridge_gap",
                affected_section_id="s2",
                explanation="the opening does not connect the prerequisite",
                required_correction="add the approved bridge to the opening",
            ),
        )
    )
    repair = _Repair(_section("s2", 1, "Use teaching_block_id s2-block here."))

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.status == "recoverable_failure"
    assert any(issue.issue_code == "metadata_or_placeholder_leak" for issue in result.issues)


@pytest.mark.asyncio
async def test_provider_cannot_target_an_unrelated_section() -> None:
    previous_plan, next_plan, previous, following = _boundary()
    semantic = _Semantic(
        BoundarySemanticVerdict(
            status="issue",
            issue=ContinuityIssue(
                issue_code="bad_target",
                affected_section_id="s3",
                explanation="wrong target",
                required_correction="target this boundary",
            ),
        )
    )
    repair = _Repair(following)

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.failure_code == "boundary_issue_unbound"
    assert repair.calls == 0


@pytest.mark.asyncio
async def test_semantic_issue_cannot_leak_internal_planning_language() -> None:
    previous_plan, next_plan, previous, following = _boundary()
    semantic = _Semantic(
        BoundarySemanticVerdict(
            status="issue",
            issue=ContinuityIssue(
                issue_code="bad_copy",
                affected_section_id="s2",
                explanation="the teaching_block_id is missing from the bridge",
                required_correction="rewrite the composition_plan",
            ),
        )
    )

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
    )

    assert result.failure_code == "boundary_semantic_output_invalid"
    assert result.repair_attempted is False


@pytest.mark.asyncio
async def test_provider_operational_error_is_not_reclassified_as_bad_output() -> None:
    previous_plan, next_plan, previous, following = _boundary()

    async def operational_failure(_request):
        raise RuntimeError("provider credentials are unavailable")

    with pytest.raises(RuntimeError, match="credentials"):
        await validate_and_repair_boundary(
            previous_section=previous,
            previous_plan=previous_plan,
            next_section=following,
            next_plan=next_plan,
            semantic_validator=operational_failure,
        )


@pytest.mark.asyncio
async def test_persistent_semantic_issue_fails_after_one_revalidation_without_repair_loop() -> None:
    previous_plan, next_plan, previous, following = _boundary()
    issue = ContinuityIssue(
        issue_code="semantic_bridge_gap",
        affected_section_id="s2",
        explanation="the opening does not connect the prerequisite",
        required_correction="add the approved bridge to the opening",
    )
    semantic = _Semantic(
        [
            BoundarySemanticVerdict(status="issue", issue=issue),
            BoundarySemanticVerdict(status="issue", issue=issue),
        ]
    )
    repair = _Repair(_section("s2", 1, "Light energy supports photosynthesis."))

    result = await validate_and_repair_boundary(
        previous_section=previous,
        previous_plan=previous_plan,
        next_section=following,
        next_plan=next_plan,
        semantic_validator=semantic,
        repair_engine=repair,
        writer_requests={"s2": _writer_request(next_plan)},
    )

    assert result.status == "recoverable_failure"
    assert result.failure_code == "boundary_semantic_revalidation_failed"
    assert result.semantic_calls == 2
    assert repair.calls == 1
    assert result.previous_section == previous


@pytest.mark.asyncio
async def test_repair_operational_error_is_not_reclassified_as_recoverable_content_failure() -> (
    None
):
    previous_plan, next_plan, previous, following = _boundary(
        next_text="Photosynthesis makes food."
    )

    class _OperationalRepair:
        async def repair_section(self, _request):
            raise RuntimeError("writer credentials are unavailable")

    with pytest.raises(RuntimeError, match="credentials"):
        await validate_and_repair_boundary(
            previous_section=previous,
            previous_plan=previous_plan,
            next_section=following,
            next_plan=next_plan,
            semantic_validator=_Semantic(BoundarySemanticVerdict(status="pass")),
            repair_engine=_OperationalRepair(),
            writer_requests={"s2": _writer_request(next_plan)},
        )

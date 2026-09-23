"""Optional semantic reviewer stage using the canonical authoring runner."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from curriculum.agents import _run_structured
from curriculum.models import FlowChoice
from curriculum.prompts import whole_lesson_coherence_reviewer_prompt
from infra.authoring.model_policy import V3_WHOLE_LESSON_COHERENCE_REVIEWER

from .models import ReviewIssue


class SemanticReviewDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issues: list[ReviewIssue] = Field(default_factory=list)


async def run_semantic_reviewer(
    *,
    path: str,
    teaching_plan: dict[str, Any],
    flow_choice: FlowChoice | dict[str, Any] | None,
    sourcebook: dict[str, Any] | None,
    shared_tasks: list[dict[str, Any]],
    output: dict[str, Any],
    trace_id: str | None = None,
) -> list[ReviewIssue]:
    draft = await _run_structured(
        node=V3_WHOLE_LESSON_COHERENCE_REVIEWER,
        caller="v3_whole_lesson_coherence_reviewer",
        output_type=SemanticReviewDraft,
        system_prompt=whole_lesson_coherence_reviewer_prompt(),
        user_payload={
            "path": path,
            "teaching_plan": teaching_plan,
            "flow_choice": flow_choice.model_dump(mode="json") if isinstance(flow_choice, FlowChoice) else flow_choice,
            "sourcebook": sourcebook,
            "shared_tasks": shared_tasks,
            "output": output,
        },
        trace_id=trace_id,
    )
    return draft.issues


__all__ = ["SemanticReviewDraft", "run_semantic_reviewer"]

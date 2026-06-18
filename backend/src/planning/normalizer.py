from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from planning.llm_config import (
    PLANNING_BRIEF_INTERPRETER_CALLER,
    get_planning_slot,
)
from planning.models import (
    GenerationDirectives,
    NormalizedBrief,
    PlanningLearningOutcome,
    PlanningScaffoldLevel,
    PlanningTopicType,
    StudioBriefRequest,
)

logger = logging.getLogger(__name__)
_PROCESS_HINTS = (
    "how to",
    "steps",
    "process",
    "procedure",
    "method",
    "solve",
    "carry out",
)
_FACT_HINTS = (
    "facts",
    "terms",
    "definitions",
    "vocabulary",
    "dates",
    "names",
    "remember",
)


class _BriefIntentResolution(BaseModel):
    topic_type: PlanningTopicType | None = None
    learning_outcome: PlanningLearningOutcome | None = None
    keyword_profile: list[str] = Field(default_factory=list)
    scope_warning: str | None = None


def _resolve_topic_type(brief: StudioBriefRequest) -> PlanningTopicType:
    if brief.signals.topic_type is not None:
        return brief.signals.topic_type

    intent = brief.intent.lower()
    if any(marker in intent for marker in _PROCESS_HINTS):
        return "process"
    if any(marker in intent for marker in _FACT_HINTS):
        return "facts"
    if " and " in intent or "," in intent:
        return "mixed"
    return "concept"


def _resolve_learning_outcome(
    brief: StudioBriefRequest,
    topic_type: PlanningTopicType,
) -> PlanningLearningOutcome:
    if brief.signals.learning_outcome is not None:
        return brief.signals.learning_outcome
    if topic_type == "process":
        return "be-able-to-do"
    if topic_type == "facts":
        return "remember-terms"
    return "understand-why"


def _resolve_scaffold_level(brief: StudioBriefRequest) -> PlanningScaffoldLevel:
    styles = set(brief.signals.class_style)
    if brief.preferences.reading_level == "simple" or "needs-explanation-first" in styles:
        return "high"
    if brief.preferences.reading_level == "advanced" or "tries-before-told" in styles:
        return "low"
    return "medium"


def _scope_warning(brief: StudioBriefRequest, topic_type: PlanningTopicType) -> str | None:
    intent = brief.intent.strip()
    if len(intent.split()) > 12:
        return "Topic looks broad. Keep the lesson tightly scoped when you review the plan."
    if topic_type == "mixed" and (" and " in intent.lower() or "," in intent):
        return "This topic may contain several sub-topics. Review the section focus before generating."
    return None


def _keyword_profile(intent: str) -> list[str]:
    keywords: list[str] = []
    for token in intent.lower().split():
        cleaned = token.strip(" ,.")
        if len(cleaned) <= 3 or cleaned in keywords:
            continue
        keywords.append(cleaned)
        if len(keywords) == 12:
            break
    return keywords


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized: list[str] = []
    for token in keywords:
        cleaned = token.strip().lower().strip(" ,.")
        if len(cleaned) <= 3 or cleaned in normalized:
            continue
        normalized.append(cleaned)
        if len(normalized) == 12:
            break
    return normalized


def _system_prompt() -> str:
    return "\n".join(
        [
            "You resolve planning intent for Teacher Studio lessons.",
            "Preserve any signal the teacher already selected explicitly.",
            "Infer only the lesson intent metadata needed for planning.",
            "Return valid JSON only.",
            "Schema fields:",
            "- topic_type: concept | process | facts | mixed | null",
            "- learning_outcome: understand-why | be-able-to-do | remember-terms | apply-to-new | null",
            "- keyword_profile: up to 12 lowercase keywords",
            "- scope_warning: optional short warning string",
        ]
    )


def _user_prompt(brief: StudioBriefRequest) -> str:
    return "\n".join(
        [
            f"Intent: {brief.intent}",
            f"Audience: {brief.audience}",
            f"Prior knowledge: {brief.prior_knowledge or 'none'}",
            f"Extra context: {brief.extra_context or 'none'}",
            f"Teacher topic_type: {brief.signals.topic_type or 'unset'}",
            f"Teacher learning_outcome: {brief.signals.learning_outcome or 'unset'}",
            f"Class style: {', '.join(brief.signals.class_style) or 'none'}",
            f"Format: {brief.signals.format or 'unset'}",
            f"Constraints: keep_short={brief.constraints.keep_short}, more_practice={brief.constraints.more_practice}, use_visuals={brief.constraints.use_visuals}, print_first={brief.constraints.print_first}",
            "Infer the unresolved lesson intent and keep the topic tightly scoped.",
        ]
    )


async def _resolve_with_llm(
    brief: StudioBriefRequest,
    *,
    model: Any | None,
    run_llm_fn: Callable[..., Awaitable[Any]] | None,
    generation_id: str,
) -> _BriefIntentResolution | None:
    if model is None or run_llm_fn is None:
        return None

    agent = Agent(
        model=model,
        output_type=_BriefIntentResolution,
        system_prompt=_system_prompt(),
    )
    user_prompt = _user_prompt(brief)

    for attempt in range(2):
        try:
            result = await run_llm_fn(
                trace_id=generation_id,
                caller=PLANNING_BRIEF_INTERPRETER_CALLER,
                agent=agent,
                model=model,
                user_prompt=user_prompt,
                slot=get_planning_slot(PLANNING_BRIEF_INTERPRETER_CALLER),
            )
            output = result.output
            if output is None:
                raise ValueError("Planning normalizer returned no output.")
            return output
        except Exception as exc:
            logger.warning("Planning normalizer attempt %s failed: %s", attempt + 1, exc)

    return None


async def normalize_brief(
    brief: StudioBriefRequest,
    *,
    model: Any | None = None,
    run_llm_fn: Callable[..., Awaitable[Any]] | None = None,
    generation_id: str = "",
) -> NormalizedBrief:
    llm_resolution = await _resolve_with_llm(
        brief,
        model=model,
        run_llm_fn=run_llm_fn,
        generation_id=generation_id,
    )
    fallback_topic_type = _resolve_topic_type(brief)
    resolved_topic_type = brief.signals.topic_type or (
        llm_resolution.topic_type if llm_resolution is not None and llm_resolution.topic_type else fallback_topic_type
    )
    resolved_learning_outcome = brief.signals.learning_outcome or (
        llm_resolution.learning_outcome
        if llm_resolution is not None and llm_resolution.learning_outcome
        else _resolve_learning_outcome(brief, resolved_topic_type)
    )
    resolved_format = (
        "printed-booklet" if brief.constraints.print_first else brief.signals.format or "both"
    )
    directives = GenerationDirectives(
        tone_profile=brief.preferences.tone,
        reading_level=brief.preferences.reading_level,
        explanation_style=brief.preferences.explanation_style,
        example_style=brief.preferences.example_style,
        scaffold_level=_resolve_scaffold_level(brief),
        brevity=brief.preferences.brevity,
    )
    fallback_warning = _scope_warning(brief, resolved_topic_type)
    scope_warning = (
        llm_resolution.scope_warning.strip()
        if llm_resolution is not None and llm_resolution.scope_warning and llm_resolution.scope_warning.strip()
        else fallback_warning
    )
    keyword_profile = (
        _normalize_keywords(llm_resolution.keyword_profile)
        if llm_resolution is not None and llm_resolution.keyword_profile
        else _keyword_profile(brief.intent)
    )
    return NormalizedBrief(
        brief=brief,
        resolved_topic_type=resolved_topic_type,
        resolved_learning_outcome=resolved_learning_outcome,
        resolved_format=resolved_format,
        directives=directives,
        scope_warning=scope_warning,
        keyword_profile=keyword_profile,
    )

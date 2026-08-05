"""Model-tier routing for whole-lesson native generation.

Tiers are semantic. Concrete model names come from configuration, never from
planner/writer call sites.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from core.config import settings

ModelTier = Literal["STANDARD", "FAST"]


class PageModelCall(str, Enum):
    LESSON_APPROACH = "lesson_approach"
    LESSON_APPROACH_REPAIR = "lesson_approach_repair"
    FORM_PLAN = "form_plan"
    FORM_PLAN_REPAIR = "form_plan_repair"
    PROSE_WRITER = "prose_writer"
    WORKED_EXAMPLE_WRITER = "worked_example_writer"
    LIST_WRITER = "list_writer"
    TABLE_WRITER = "table_writer"
    FIGURE_BRIEF_WRITER = "figure_brief_writer"
    ANSWER_KEY = "answer_key"


_CALL_TIERS: dict[PageModelCall, ModelTier] = {
    PageModelCall.LESSON_APPROACH: "STANDARD",
    PageModelCall.LESSON_APPROACH_REPAIR: "STANDARD",
    PageModelCall.FORM_PLAN: "FAST",
    PageModelCall.FORM_PLAN_REPAIR: "FAST",
    PageModelCall.PROSE_WRITER: "STANDARD",
    PageModelCall.WORKED_EXAMPLE_WRITER: "STANDARD",
    PageModelCall.LIST_WRITER: "FAST",
    PageModelCall.TABLE_WRITER: "FAST",
    PageModelCall.FIGURE_BRIEF_WRITER: "FAST",
    PageModelCall.ANSWER_KEY: "FAST",
}

_OBJECT_WRITER_CALLS: dict[str, PageModelCall] = {
    "prose": PageModelCall.PROSE_WRITER,
    "worked-example": PageModelCall.WORKED_EXAMPLE_WRITER,
    "list": PageModelCall.LIST_WRITER,
    "table": PageModelCall.TABLE_WRITER,
    "figure": PageModelCall.FIGURE_BRIEF_WRITER,
}


def tier_for_call(call: PageModelCall | str) -> ModelTier:
    if isinstance(call, str):
        call = PageModelCall(call)
    return _CALL_TIERS[call]


def tier_for_object_writer(object_id: str) -> ModelTier | None:
    """Return tier for a writer object, or None when no model call is used."""
    if object_id == "questions":
        return None
    call = _OBJECT_WRITER_CALLS.get(object_id)
    if call is None:
        raise KeyError(f"no writer tier mapping for object {object_id!r}")
    return tier_for_call(call)


def model_name_for_tier(tier: ModelTier) -> str:
    if tier == "STANDARD":
        return settings.page_model_standard
    if tier == "FAST":
        return settings.page_model_fast
    raise ValueError(f"unknown model tier {tier!r}")


def model_name_for_call(call: PageModelCall | str) -> str:
    return model_name_for_tier(tier_for_call(call))


def timeout_seconds_for_call(call: PageModelCall | str) -> int:
    if isinstance(call, str):
        call = PageModelCall(call)
    if call in {PageModelCall.LESSON_APPROACH, PageModelCall.LESSON_APPROACH_REPAIR}:
        return settings.page_lesson_plan_timeout_seconds
    if call in {PageModelCall.FORM_PLAN, PageModelCall.FORM_PLAN_REPAIR}:
        return settings.page_form_plan_timeout_seconds
    tier = tier_for_call(call)
    if tier == "STANDARD":
        return settings.page_standard_writer_timeout_seconds
    return settings.page_fast_writer_timeout_seconds

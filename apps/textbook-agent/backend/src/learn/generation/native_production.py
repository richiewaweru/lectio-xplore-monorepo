"""Learn native production compatibility shim.

P10E retires ordinary Learn composition/writing and the interaction-selection
helper: the SharedLessonDocument Learn adapter
(``learn.generation.shared_document_adapter``) now copies ordinary content and
maps every TaskAnchor to a Learn interaction deterministically. Nothing in the
production Learn path authors ordinary content or selects an interaction via
an LLM any more.

This module keeps only ``teaching_plan_content_hash``, which
``application.unit_lesson.realize_learn_handoff`` still imports as the
canonical pedagogical digest adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from curriculum.teaching_plan.content_hash import (
    teaching_plan_content_hash as _canonical_teaching_plan_content_hash,
)
from curriculum.teaching_plan.models import TeachingPlan


def teaching_plan_content_hash(plan: TeachingPlan | Mapping[str, Any]) -> str:
    """Compatibility adapter to the curriculum-owned pedagogical digest."""
    return _canonical_teaching_plan_content_hash(plan)


__all__ = ["teaching_plan_content_hash"]

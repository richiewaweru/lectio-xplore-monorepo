"""Print native production compatibility shim.

P11B retires ordinary Print composition/writing (the closed-catalogue
form/work-order pipeline and the whole-lesson planning/writing executor):
the SharedLessonDocument Print adapter
(``print.generation.shared_document_adapter`` /
``print.generation.shared_document_execution``) now realizes Print
deterministically from the verified shared source. Nothing in the
production Print path authors ordinary content or selects a form via an LLM
any more, and standalone (non-Unit) Print generation is retired.

This module keeps only ``teaching_plan_content_hash``, which
``application.unit_lesson.realize_print_handoff`` still imports as the
canonical pedagogical digest adapter (mirroring
``learn.generation.native_production``'s P10E shim).
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

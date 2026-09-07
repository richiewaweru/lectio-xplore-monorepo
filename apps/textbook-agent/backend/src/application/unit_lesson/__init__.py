"""Unit-path lesson preparation orchestration.

Real ownership lives here (D1). Historical planning.bridge /
generation.path_preparation shims were removed in D5.
"""

from __future__ import annotations

from application.unit_lesson.contracts import PathPreparationBlocked
from application.unit_lesson.dispatch import (
    enforce_path_owned_card_objective,
    initialise_path_generation,
)
from application.unit_lesson.prepare import prepare_path_lesson
from application.unit_lesson.realizations import (
    admit_realization,
    list_realizations_for_lesson,
    mark_stale_for_teaching_change,
    request_outputs,
    resolve_by_path,
    retry_realization,
    to_identity,
)

__all__ = [
    "PathPreparationBlocked",
    "admit_realization",
    "enforce_path_owned_card_objective",
    "initialise_path_generation",
    "list_realizations_for_lesson",
    "mark_stale_for_teaching_change",
    "prepare_path_lesson",
    "request_outputs",
    "resolve_by_path",
    "retry_realization",
    "to_identity",
]

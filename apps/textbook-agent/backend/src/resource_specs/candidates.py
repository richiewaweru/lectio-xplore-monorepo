"""Compatibility shim — use ``print.resources.candidates``.

Temporary (R1). Remove when all call sites import the print path (R7).
"""

from __future__ import annotations

from print.resources.candidates import (  # noqa: F401
    ALWAYS_EXCLUDED_OBJECTS,
    FIRST_SLICE_OBJECTS,
    CandidateConfigurationError,
    IntentCandidate,
    LessonGuidance,
    ObjectCandidate,
    SlotGuidance,
    assemble_lesson_guidance,
    assemble_slot_guidance,
    resolve_block_candidates,
)

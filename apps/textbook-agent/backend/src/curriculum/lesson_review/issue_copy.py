"""Teacher-facing allow-list and plain-language copy for the Issues tab.

Only codes listed here ever reach the Issues payload; anything else (new
internal codes, checkpoint/lease/hash/retry state, shape checks) is dropped
rather than shown. Copy is written for a teacher: no codes, no ids.

Groups
- ``blocking``: the lesson did not finish building.
- ``needs_look``: content advisories a teacher would notice and can act on
  (edit, retry, regenerate, or mark as fine).
- ``info``: informational; shown collapsed, no actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IssueGroup = Literal["blocking", "needs_look", "info"]


@dataclass(frozen=True)
class IssueCopy:
    group: IssueGroup
    #: ``None`` means "use the flag's own message" (boundary warnings are
    #: already written for teachers and name both sections).
    message: str | None
    suggestion: str | None = None


#: Lesson did not finish: kept from the original projection, teacher wording added.
BLOCKING_COPY: dict[str, IssueCopy] = {
    "REALIZATION_FAILED": IssueCopy(
        "blocking",
        "This lesson didn't finish building.",
        "Try again. If it keeps failing, regenerate the lesson.",
    ),
    "REQUIRED_FIGURE_MISSING": IssueCopy(
        "blocking",
        "A figure this lesson needs could not be created.",
        "Try again to rebuild the figure, or regenerate the lesson.",
    ),
    "DOCUMENT_INVALID": IssueCopy(
        "blocking",
        "Part of this lesson couldn't be put together correctly and may not display properly.",
        "Try again, or regenerate the lesson.",
    ),
    "LEARN_INTERACTION_INVALID": IssueCopy(
        "blocking",
        "A practice activity in this lesson isn't set up correctly.",
        "Try again, or regenerate the lesson.",
    ),
    "OUTPUT_ERROR": IssueCopy(
        "blocking",
        "Something went wrong while building this lesson.",
        "Try again. If it keeps failing, regenerate the lesson.",
    ),
}

#: A planned figure that shipped as a labelled placeholder (retries exhausted).
FIGURE_FALLBACK_COPY = IssueCopy(
    "needs_look",
    "A figure couldn't be generated, so this section may show a placeholder instead.",
    "Add your own image in the editor, or leave it as it is.",
)

_PLACEHOLDER_LEAK_COPY = IssueCopy(
    "needs_look",
    "Planning text or a placeholder may be visible to students in this section.",
    "Look for stray labels or placeholder text and remove them.",
)

#: Document-QA / writer / boundary quality-flag codes a teacher can act on.
FLAG_COPY: dict[str, IssueCopy] = {
    "boundary_transition_warning": IssueCopy(
        "needs_look",
        None,
        "Read the start of this section and smooth the transition if needed.",
    ),
    "answer_leakage": IssueCopy(
        "needs_look",
        "A task's answer may be given away in the text around it.",
        "Check the wording before the task and remove anything that gives the answer.",
    ),
    "assessment_duplicates_example": IssueCopy(
        "needs_look",
        "A check question reuses the numbers or wording of an earlier worked example.",
        "Change the question so it tests something new.",
    ),
    "misconception_unresolved": IssueCopy(
        "needs_look",
        "A common wrong idea is mentioned but never corrected in this section.",
        "Add a sentence that corrects it, or remove the mention.",
    ),
    "factual_inaccuracy": IssueCopy(
        "needs_look",
        "A statement in this section may be factually wrong.",
        "Check it against your source before using the lesson.",
    ),
    "unsupported_claim": IssueCopy(
        "needs_look",
        "A claim or number in this section may not be backed by your source material.",
        "Check it before using the lesson.",
    ),
    "unsupported_required_fact": IssueCopy(
        "needs_look",
        "A fact in this section may not be backed by your source material.",
        "Check it before using the lesson.",
    ),
    "progression_gap": IssueCopy(
        "needs_look",
        "This section may not build on the one before it as planned, so the wording could be unclear.",
        "Read the section and clarify how it follows on.",
    ),
    "metadata_leak": _PLACEHOLDER_LEAK_COPY,
    "metadata_or_placeholder_leak": _PLACEHOLDER_LEAK_COPY,
    "internal_id_leak": _PLACEHOLDER_LEAK_COPY,
    "figure_media_unavailable": FIGURE_FALLBACK_COPY,
}

#: Writer shape checks (``_WRITER_ADVISORY_CODES``) are intentionally NOT in
#: ``FLAG_COPY``: they are layout/length heuristics with machine-style messages
#: ("Advisory shape check length_over_target at nodes[3]"), all content is
#: preserved, and a teacher cannot act on them. They stay visible only in the
#: editor's Quality Notes. Listed here so the decision is explicit and tested.
HIDDEN_SHAPE_CODES = frozenset(
    {
        "length_over_target",
        "shape_missing",
        "list_item_not_parallel",
        "paragraph_run_exceeded",
        "block_exceeds_node_limit",
        "section_exceeds_node_limit",
        "section_exceeds_callout_limit",
        "heading_missing_subsection_cue",
        "kind_missing_semantic_cue",
        "callout_missing_cautionary_cue",
    }
)

#: Legacy whole-lesson coherence-report codes worth a teacher's attention.
#: Everything else the reviewer emits (task parity, contract and duplicate-id
#: checks) is internal and excluded.
COHERENCE_COPY: dict[str, IssueCopy] = {
    "SLOPE_DRIFT": IssueCopy(
        "needs_look",
        "A worked example's numbers don't agree with each other.",
        "Check the example and correct the figures.",
    ),
    "SLOPE_POINT_MISSING": IssueCopy(
        "needs_look",
        "A worked example is missing a number it relies on.",
        "Check the example and add the missing figures.",
    ),
}

__all__ = [
    "BLOCKING_COPY",
    "COHERENCE_COPY",
    "FIGURE_FALLBACK_COPY",
    "FLAG_COPY",
    "HIDDEN_SHAPE_CODES",
    "IssueCopy",
    "IssueGroup",
]

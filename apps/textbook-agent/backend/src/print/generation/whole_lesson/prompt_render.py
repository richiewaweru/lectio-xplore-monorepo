"""Render exact planner prompts with resource identity substitution."""

from __future__ import annotations

from print.contracts.lectio_page import PAGE_OBJECT_IDS


class PromptObjectLeakError(ValueError):
    pass


def assert_no_page_object_ids(text: str, *, where: str) -> None:
    """Fail when page-object catalogue forms leak into the teaching prompt.

    Hyphenated object ids and explicit object-catalogue markers are hard fails.
    Bare English tokens (list/table/figure) are allowed in pedagogical prose.
    """
    leaks: list[str] = []
    markers = (
        "available_objects",
        "valid_objects",
        "content_schema",
        "worked-example",
        "answer-key",
    )
    for marker in markers:
        if marker in text:
            leaks.append(marker)
    for object_id in PAGE_OBJECT_IDS:
        if "-" in object_id and object_id in text:
            leaks.append(object_id)
    if leaks:
        raise PromptObjectLeakError(
            f"{where} contains page-object markers: {sorted(set(leaks))}"
        )


BACKBONE_TEACHING_GUIDANCE = """## Lesson backbone

This lesson has one fixed backbone: one anchor scenario with exact data, up to two
variants, and their figures. The approved questions were written against the anchor
or a variant (see the approved question ids and their backbone references in the
fixed input; each reference names the question's target).

Share the anchor scenario and its data freely across sections; that is intended,
not repetition to avoid.

Each approved question belongs to its check. Its stem, the specific question it
poses about its target, and that question's answer are reserved for the block that
owns it. A teaching block must not pose the same question about the same target or
work out its answer.

Prefer working examples on the anchor and leaving variants to the checks. When a
check targets the anchor, teach with the anchor's other facts or with a variant,
never the check's own question.

Use the backbone's exact data and figure facts; do not invent other scenarios,
shapes or numbers. For this lesson these rules replace the general rule about
choosing a different scenario than the approved items; they never permit copying
an approved stem.

Figures: every approved question whose backbone reference has a figure_id must be owned by a block whose visual has figure_ref set to that id; copy mode (render, diagram or image), purpose, must_show and labels_required from that backbone figure. The figure's data is copied by code; do not write it. Teaching blocks may also show a backbone figure the same way (for example the worked example on the anchor's figure). For backbone figures this replaces the default of adding no visual; still add no other visuals for variety.

FIGURE KINDS. Every figure has a `mode`:
- render: drawn exactly and to scale: tables of values, bar charts, combo charts (bars plus a line on two scales), graphs of a rule (y = 2x + 1), number lines, shapes with given side lengths, simple step flows, and cycles. It cannot draw real objects such as plants, apparatus or organs.
- diagram: a flat, labelled schematic of real things and their named parts. It may carry value labels as text (for example 'Height Day 28: 48 cm'), but it is not to scale: its numbers are words on the picture, not measurements to read off.
- image: a realistic scene or object where what it looks like is the point. Little or no text.
Choose in this order: if the learner must read exact values, lengths or positions from the figure, use render. If the learner must see real things and their named parts, use diagram. If only the look matters, use image. A figure whose data holds a series of values (a list of numbers) is always render.
Examples: a table of seedling heights at each weekly check is render; two labelled seedlings side by side, one green and tall in the sun, one pale and short in the dark, with their heights written as labels, is diagram."""

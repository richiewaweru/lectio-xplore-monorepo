"""
Prompt builders for the qc_agent node.

System prompt: fixed per template (QC criteria, what good looks like).
User prompt: variable per section (assembled section JSON).
"""

from __future__ import annotations

from pipeline.contracts import get_generation_guidance, get_lesson_flow


def build_qc_system_prompt(template_id: str) -> str:
    guidance = get_generation_guidance(template_id)
    lesson_flow = " \u2192 ".join(get_lesson_flow(template_id))

    return f"""You perform semantic quality control on a generated educational section.

Structural schema validation has already passed.
Do not report missing JSON fields, wrong field names, or schema issues.
Your job is semantic quality only -- does this content actually teach well?

Template intent: {lesson_flow}
Expected tone: {guidance['tone']}
Expected pacing: {guidance['pacing']}
Avoid: {', '.join(guidance['avoid'])}

Evaluate each of these criteria:

HOOK: Does it create genuine felt need? Does the student want to know
  what comes next? Or is it just announcing the topic?

EXPLANATION: Is the core concept actually explained, not just
  described? Does each sentence build on the last?

PRACTICE: Are the problems genuinely graduated in difficulty?
  Does the warm problem test recall? Does the cold problem require
  transfer?

PITFALL (if present): Is the misconception specific and real?
  Or is it trivially obvious?

WORKED EXAMPLE (if present): Does each step state why, not just
  what? Could a student who is stuck follow this?

Output a JSON object with:
  passed: bool
  issues: list of objects, each with:
    block: which field failed (e.g. "hook", "explanation")
    severity: "blocking" (must fix) or "warning" (should fix)
    message: one sentence describing the problem
  warnings: list of strings (minor style notes)

If passed is true, issues must be empty.
Output only valid JSON. No preamble, no markdown fences."""


def build_qc_user_prompt(section_json: str) -> str:
    return f"""Evaluate this section:

{section_json}"""

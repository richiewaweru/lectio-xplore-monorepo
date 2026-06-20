"""Prompt templates for V3 Studio LLM steps."""

from functools import lru_cache

from contracts.lectio import get_component_card, get_planner_index, get_template_contract

SIGNAL_SYSTEM = """You extract structured teaching signals from a structured teacher form.

The form already provides lesson_mode, learner_level, support_needs, prior_knowledge_level,
intended_outcome, grade_level, subject, duration_minutes, topic, and subtopics.

Do NOT re-infer these from free text. Read them directly from the form fields.

Your job:
- Confirm the teaching topic (short, specific).
- Optionally select ONE subtopic string (or null) if the form subtopics are empty or too broad.
- Summarise teacher_goal in one clear sentence.
- Set inferred_resource_type to one of:
    lesson          - default; full instructional lesson with explanation and practice
    mini_booklet    - compact guided learning students can follow step by step
    worksheet       - practice resource; concept has already been taught
    quiz            - formal assessment with scored questions
    exit_ticket     - short end-of-lesson check, 3-5 questions
    practice_set    - drill-style repetition, minimal explanation
    quick_explainer - focused concept explainer or reference card
  Default to lesson if the teacher's intent does not clearly match another type.
"""

ADJUST_SYSTEM = """You revise the given ProductionBlueprint JSON according to the teacher's plain-language instruction.
Preserve IDs where possible; keep schema valid. Output the full revised blueprint."""


@lru_cache(maxsize=1)
def _planner_index_block() -> str:
    """Build the component palette block shared by the chunked planner."""

    template = get_template_contract("guided-concept-path") or {}
    planner = get_planner_index()

    always_present = set(template.get("always_present", []))
    available = set(template.get("available_components", []))
    all_available = always_present | available

    component_budget: dict = template.get("component_budget", {})
    max_per_section: dict = template.get("max_per_section", {})

    lines: list[str] = [
        "TEMPLATE: guided-concept-path",
        f"REQUIRED in every section: {', '.join(sorted(always_present)) or 'none'}",
        "AVAILABLE COMPONENTS (use only these slugs):",
    ]

    phase_map: dict = planner.get("phase_map", {})
    for phase_num in sorted(phase_map.keys(), key=lambda k: int(k)):
        phase = phase_map[phase_num]
        phase_name = phase.get("name", f"Phase {phase_num}")
        lines.append(f"\nPhase {phase_num} - {phase_name}:")
        for cid in phase.get("components", []):
            if cid not in all_available:
                continue
            card = get_component_card(cid) or {}
            field = card.get("section_field", "-")
            role = card.get("role", "")
            job = card.get("cognitive_job", "")
            req = " [REQUIRED]" if cid in always_present else ""
            lines.append(f"  {cid} [{field}]{req}: {role} - {job}")

    if component_budget:
        lines.append("\nCOMPONENT BUDGETS (max across entire lesson):")
        for slug, limit in component_budget.items():
            lines.append(f"  {slug}: max {limit}")

    if max_per_section:
        lines.append("\nPER-SECTION LIMITS:")
        for slug, limit in max_per_section.items():
            lines.append(f"  {slug}: max {limit} per section")

    return "\n".join(lines)

"""Prompt templates for V3 Studio LLM steps."""

from functools import lru_cache

from contracts.lectio import get_component_card, get_planner_index, get_template_contract

SIGNAL_SYSTEM = """You extract structured teaching signals from a structured teacher form.

The form already provides resource_type, learner_level, reading_level, language_support,
prior_knowledge_level, grade_level, subject, duration_minutes, topic, subtopics, outcome,
struggle, and prior_knowledge.

Do NOT invent or overwrite those fields. Read them directly from the form.

Your job:
- Confirm the teaching topic (short, specific).
- Optionally select ONE subtopic string (or null) if the form subtopics are empty or too broad.
- Summarise teacher_goal in one clear sentence.
- Infer inferred_lesson_mode using these rules:
    repair         - the struggle names a misconception, gap, or something students keep getting wrong
    first_exposure - the outcome introduces a concept for the first time, or prior knowledge is light
    consolidation  - the class already knows the idea and needs guided practice or strengthening
    retrieval      - the goal is recall, quick review, or bringing prior learning back to mind
    transfer       - the goal is applying understanding in a new or unfamiliar context
  Pick the single best fit from the evidence in the form.
- Set lesson_mode_confidence to:
    high - the outcome/struggle clearly match one rule
    low  - the form leaves the mode genuinely unclear or multiple rules compete
"""

ADJUST_SYSTEM = """You revise the given ProductionBlueprint JSON according to the teacher's plain-language instruction.
Preserve IDs where possible; keep schema valid. Output the full revised blueprint."""

PROPOSE_INTENT_SYSTEM = """You draft three teacher-owned intent fields for a lesson:
outcome, likely struggle, and prior knowledge. You are proposing drafts a teacher will read,
correct, and approve — not final copy.

Condition every draft on the full class + lesson shape:
- Reading level and language support shape sentence complexity and vocabulary in the outcome.
- Learner level shapes the ceiling of what "by the end" means.
- Prior knowledge level shapes what you assume and what you list as prerequisites.
- Subtopics (if present) narrow the outcome scope. If subtopics are empty, treat topic as the scope.

Hard rules:
- outcome_draft: one sentence, starts "By the end...", names a specific observable capability. No hedging, no lists.
- struggle_draft: 2-3 sentences, concrete for THIS class profile, not generic pedagogy. Name the actual misconception or friction.
- prior_knowledge_draft: 2-4 short items, newline-separated. Concrete prerequisites, not vibes.
- Do not invent facts about the class the form did not provide.
- Output valid JSON only. No preamble."""


def build_propose_intent_user_prompt(
    *,
    grade_level: str,
    subject: str,
    resource_type: str,
    duration_minutes: int,
    learner_level: str,
    reading_level: str,
    language_support: str,
    prior_knowledge_level: str,
    topic: str,
    subtopics: list[str],
) -> str:
    scope = ", ".join(subtopics) if subtopics else "(none — use topic as scope)"
    return (
        f"Grade level: {grade_level}\n"
        f"Subject: {subject}\n"
        f"Resource type: {resource_type}   Duration: {duration_minutes} min\n"
        f"Learner level: {learner_level}\n"
        f"Reading level: {reading_level}\n"
        f"Language support: {language_support}\n"
        f"Prior knowledge level: {prior_knowledge_level}\n"
        f"Topic: {topic}\n"
        f"Subtopics: {scope}\n\n"
        "Draft outcome_draft, struggle_draft, and prior_knowledge_draft tailored to this exact class and topic."
    )


@lru_cache(maxsize=1)
def build_v3_shared_prefix() -> str:
    """Stable prompt prefix reused across V3 planning and writing nodes."""

    return """TEXTBOOK V3 PIPELINE RULES
- Work only within the responsibility of the current node.
- Preserve fixed facts, identifiers, and structural commitments from context.
- Return only the format requested for this node.
"""


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

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

REASONING_SCAFFOLD = """
REASONING STEPS - work through these before writing any JSON

Do not skip ahead. Each step locks a decision that the next step depends on.
Keep answers short. You are building toward the blueprint, not writing an essay.

STEP 1 - LEARNER CONTEXT
  Who is this class? What is their level and what are their main barriers?
  What do the teacher form signals imply for content density, language load, and visual support?
  Answer in 2-3 sentences.

STEP 2 - CONCEPT AND DIFFICULTY
  What is the core concept in one sentence?
  What is the single hardest step for this learner group to understand?
  What misconception most commonly arises here, and does it need a pitfall section?
  Answer in 3 short sentences.

STEP 3 - RESOURCE STRUCTURE
  Read the RESOURCE SPEC in your context window.
  State: what this resource type is for, what is forbidden, what sections are required.
  If a section you wanted to plan is forbidden by the spec, remove it now.
  This step is a gate.

STEP 4 - TEACHING SEQUENCE
  Given the lesson_mode, learner_level, and teacher form signals,
  write the teaching sequence as an ordered list of 4-6 moves.
  Each move is one verb phrase: "Orient the learner to...", "Explain how to...",
  "Model with...", "Practice...".

STEP 5 - COMPONENT MAPPING
  Map each sequence move to one component slug.
  Follow this order for every move:
    a. Name the pedagogical role of this move
    b. Find the phase in the AVAILABLE COMPONENTS that matches that role
    c. Choose the right component from that phase for this learner and context
    d. Check section_field - no two components with the same field in one section
  Answer as: move -> role -> phase -> slug [field].

STEP 6 - VISUALS
  For each section, answer yes or no: does this concept require visual support here?
  Spatial and procedural steps usually need visuals.
  Definitions and pitfall warnings usually do not.
  Check resource spec visual policy - some resource types restrict visuals.

STEP 7 - QUESTIONS
  Given the lesson_mode, what is the right difficulty progression?
  lesson_mode -> allowed temperatures:
    first_exposure -> warm and medium only
    consolidation  -> start medium, reach cold and transfer
    repair         -> warm only at first; cold only after the pitfall is resolved
    retrieval      -> cold and transfer; no warm unless very fragile
    transfer       -> transfer questions; cold acceptable; no warm or medium

  For each planned question, write one sentence: difficulty, what cognitive
  move it tests, whether it needs a diagram.
  Question count must stay within the depth limits in the resource spec.

Now produce the ProductionBlueprint JSON exactly matching the schema.
Do not include the reasoning steps in the JSON output.
"""

ADJUST_SYSTEM = """You revise the given ProductionBlueprint JSON according to the teacher's plain-language instruction.
Preserve IDs where possible; keep schema valid. Output the full revised blueprint."""

SUPPLEMENT_SYSTEM_ADDENDUM = """
This run produces a POST-LESSON companion resource, not a new full lesson.

Students have already received the parent resource.

Use the parent blueprint to understand:
- what was taught
- what supports were used
- what students should now be able to do
- what question targets already exist

Do not reteach the whole parent resource.
Do not copy the parent section structure.
Do not reuse parent section IDs.
Do not add instruction, explanation-blocks, hooks, summaries, or worked examples unless the target resource spec explicitly allows them.

The target RESOURCE SPEC is the authority on:
- section count
- allowed components
- forbidden components
- visual policy
- question count
- assessment constraints

If the base architect prompt conflicts with the target resource spec, follow the target resource spec.
"""

SUPPLEMENT_USER_PROMPT_TEMPLATE = """TASK:
Create a NEW {target_resource_type} blueprint as a supplement to the parent resource.

TARGET RESOURCE SPEC - hard constraints:
{resource_spec_block}

PARENT BLUEPRINT FIELD GUIDE:
metadata.title:
  Parent concept/resource title.

metadata.subject:
  Subject area.

lesson.resource_type:
  What the parent resource was. This tells you what students already received.

lesson.lesson_mode:
  The instructional purpose of the parent resource.

voice:
  Register, tone, and language style to keep consistent.

prior_knowledge:
  Anchors students have already seen or should already know.

anchor:
  Reusable example context if appropriate.

sections:
  What the parent resource taught or practiced.

sections[].components[].content_intent:
  The intended teaching job of each component.

question_plan:
  Knowledge and skill targets students should now be able to answer.

question_plan[].temperature:
  Difficulty level: warm, medium, cold, transfer.

question_plan[].expected_answer:
  Target answer or understanding.

RULES:
- The parent resource has already been taught.
- Do not reteach the full lesson.
- Do not copy parent section_ids.
- Do not copy parent section structure.
- Preserve relevant learner adaptations.
- Build a fresh blueprint obeying the target resource spec.
- Use the same ProductionBlueprint schema.

PARENT CONTEXT:
{parent_context_json}
"""


def build_parent_context_for_supplement(parent_artifact: dict) -> dict:
    derived = parent_artifact.get("derived") if isinstance(parent_artifact.get("derived"), dict) else {}
    return {
        "form": parent_artifact.get("form"),
        "blueprint": parent_artifact.get("blueprint"),
        "derived": {
            "title": derived.get("title"),
            "subject": derived.get("subject"),
            "resource_type": derived.get("resource_type"),
            "lesson_mode": derived.get("lesson_mode"),
            "section_count": derived.get("section_count"),
            "component_count": derived.get("component_count"),
            "question_count": derived.get("question_count"),
            "visual_required_count": derived.get("visual_required_count"),
        },
    }


def build_supplement_architect_system_prompt() -> str:
    return build_architect_system_prompt() + "\n\n" + SUPPLEMENT_SYSTEM_ADDENDUM


def build_supplement_user_prompt(
    *,
    target_resource_type: str,
    resource_spec_block: str,
    parent_context_json: str,
) -> str:
    return SUPPLEMENT_USER_PROMPT_TEMPLATE.format(
        target_resource_type=target_resource_type,
        resource_spec_block=resource_spec_block,
        parent_context_json=parent_context_json,
    )


@lru_cache(maxsize=1)
def _planner_index_block() -> str:
    """
    Build the component palette block for the lesson architect prompt.

    Reads from lectio-content-contract.json via contract accessors.
    Produces phase-grouped component lines with required tags, budgets,
    and per-section limits.
    """
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


def build_architect_system_prompt() -> str:
    """System prompt for the lesson architect using teacher signals directly."""

    planner_block = _planner_index_block()

    return f"""You are a lesson architect. Output ONLY a valid ProductionBlueprint matching the schema.

{planner_block}

CONSTRAINT: Each section_field (shown in brackets above) may appear at
most once per section. Never plan two components with the same
section_field in the same section.

{REASONING_SCAFFOLD}

OUTPUT RULES:
- Only use component slugs from the AVAILABLE COMPONENTS list above. Never invent slugs.
- metadata: version "3.0", title, subject (from teacher subject)
- lesson:
    lesson_mode - choose from: first_exposure | consolidation | repair | retrieval | transfer
    resource_type - read from the RESOURCE SPEC in your context window (do not invent)
- voice: register (simple|balanced|formal), optional tone - match to learner level
- anchor: reuse_scope string - describe how the anchor example recurs across sections
- sections: each with section_id, title, role, visual_required bool,
  components with slug and content_intent.
  content_intent must be specific enough that a writer can act on it without asking questions.
- question_plan: temperature must match lesson_mode guidance from Step 7.
  Each item: question_id, section_id, temperature, prompt, expected_answer, diagram_required.
- visual_strategy: only for sections where visual_required = true.
  Each item: section_id, strategy (what the visual should show), optional density.
- answer_key: style - answers_only | brief_explanations | full_working
- repair_focus: required when lesson_mode = repair.
  fault_line: what specifically went wrong (one sentence).
  what_not_to_teach: list of things to exclude from this lesson.
- teacher_materials and prior_knowledge lists are allowed and encouraged.
Use short, clear section IDs: intro, explain, practice, summary, process, assess.
"""

from __future__ import annotations

import os

from generation.v3_studio.prompts import build_v3_shared_prefix
from core.prompts import effective_prompt_text
from v3_execution.prompts.formatting import (
    format_consistency_rules,
    format_source_of_truth,
    format_support_adaptations,
)
from v3_execution.models import SectionWriterWorkOrder, WriterSectionComponent

_ORDER_CONTEXT_MARKER = "<!-- ORDER_CONTEXT -->"


def _skip_expander_enabled() -> bool:
    return os.getenv("V3_SKIP_EXPANDER", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _load_static_template() -> str:
    return effective_prompt_text("section-writer")


def _format_schema_shape(shape: dict) -> str:
    """Render schema shape dict from get_component_schema_shape for the writer prompt."""
    lines: list[str] = ["SCHEMA SHAPE — fill this exactly:"]
    for p in shape.get("properties", []):
        name = p.get("name", "")
        typ = p.get("type", "object")
        req_lbl = "required" if p.get("required") else "optional"
        line = f"  {name} [{typ}, {req_lbl}]"
        enum = p.get("enum")
        if enum:
            line += " — must be one of: " + " | ".join(str(e) for e in enum)
        lines.append(line)
        nested = p.get("nested")
        if nested:
            lines.append("    each item:")
            for n in nested:
                nn = n.get("name", "")
                nt = n.get("type", "object")
                nr = "required" if n.get("required") else "optional"
                nline = f"      {nn} [{nt}, {nr}]"
                ne = n.get("enum")
                if ne:
                    nline += " — must be one of: " + " | ".join(str(x) for x in ne)
                lines.append(nline)
    return "\n".join(lines)


def format_formatting_policy_legend(policy: dict) -> str:
    """
    Emit the format type vocabulary once at the top of the prompt.
    This tells the writer what format labels mean.
    """
    if not policy:
        return ""
    lines = ["FORMAT TYPE LEGEND (referenced in component contracts below):"]
    for fmt_name, fmt_desc in policy.items():
        lines.append(f"  {fmt_name}: {fmt_desc}")
    return "\n".join(lines)


def format_component_contract_for_writer(card: dict, content_intent: str) -> str:
    """
    Format a single component card into a compact writer-facing contract block.
    """
    from contracts.lectio import get_component_schema_shape

    cid = card.get("component_id", "")
    field = card.get("section_field", "")
    role = card.get("role", "")
    cj = card.get("cognitive_job", "")
    field_contracts: dict = card.get("field_contracts", {})
    constraints: list = card.get("component_constraints", [])
    examples: list = card.get("examples", [])

    lines = [
        f"{cid} → section field: {field}",
        f"Intent: {content_intent}",
        f"Purpose: {role}",
        f"Cognitive job: {cj}",
    ]

    if field_contracts:
        lines.append("Field contracts:")
        for fname, fdef in field_contracts.items():
            fmt = fdef.get("format", "")
            desc = fdef.get("description", "")
            fconstraints: list = fdef.get("constraints", [])
            optional_tag = " (optional)" if fdef.get("required") is False else ""
            lines.append(f"  {fname}{optional_tag} [{fmt}]")
            if desc:
                lines.append(f"    {desc}")
            for fc in fconstraints:
                lines.append(f"    constraint: {fc}")
    else:
        lines.append("Field contracts: none declared — follow section_field name as the key.")

    if constraints:
        lines.append("Component constraints:")
        for c in constraints:
            lines.append(f"  - {c}")

    if examples:
        import json as _json

        ex = examples[0]
        lines.append("Example output:")
        lines.append(f"  {_json.dumps(ex, ensure_ascii=False)}")

    shape = get_component_schema_shape(cid)
    if shape:
        lines.append(_format_schema_shape(shape))

    return "\n".join(lines)


def _format_skip_expander_component(
    component: WriterSectionComponent,
    card: dict,
) -> str:
    """Phase 0 writer branch: structured plan purpose + registry, not brief prose."""
    from contracts.lectio import get_component_schema_shape

    capacity = card.get("capacity") or {}
    capacity_bits = []
    for key in ("max_words", "max_items", "max_sentences", "notes"):
        if key in capacity and capacity[key] not in (None, "", []):
            capacity_bits.append(f"{key}={capacity[key]}")

    lines = [
        f"COMPONENT: {component.teacher_label or component.component_id} ({component.component_id})",
        f"  purpose (from plan slot): {component.content_intent}",
        f"  section_field: {card.get('section_field', '')}",
        f"  cognitive_job: {card.get('cognitive_job', '')}",
        f"  registry_role: {card.get('role', '')}",
    ]
    if capacity_bits:
        lines.append(f"  capacity: {', '.join(str(b) for b in capacity_bits)}")
    else:
        lines.append("  capacity: (none declared)")

    constraints: list = card.get("component_constraints", [])
    if constraints:
        lines.append("  component_constraints:")
        for item in constraints:
            lines.append(f"    - {item}")

    field_contracts: dict = card.get("field_contracts", {})
    if field_contracts:
        lines.append("  field_contracts:")
        for fname, fdef in field_contracts.items():
            fmt = fdef.get("format", "")
            desc = fdef.get("description", "")
            lines.append(f"    {fname} [{fmt}] {desc}".rstrip())

    shape = get_component_schema_shape(component.component_id)
    if shape:
        lines.append(_format_schema_shape(shape))

    return "\n".join(lines)


def _format_corrections_block(order: SectionWriterWorkOrder) -> str:
    lines: list[str] = []
    for component in order.section.components:
        for correction in component.corrections:
            label = component.teacher_label or component.component_id
            lines.append(
                f"- [{label}] {correction.text}"
                f" (at {correction.created_at}"
                f"{', gen ' + correction.applied_in_generation if correction.applied_in_generation else ''})"
            )
    if not lines:
        return ""
    return "TEACHER CORRECTIONS (honour each; do not drop):\n" + "\n".join(lines)


def _build_skip_expander_order_context(order: SectionWriterWorkOrder) -> str:
    from contracts.lectio import get_formatting_policy

    policy = get_formatting_policy()
    policy_block = format_formatting_policy_legend(policy)
    component_blocks = "\n\n".join(
        _format_skip_expander_component(
            component,
            order.component_cards.get(component.component_id, {}),
        )
        for component in order.section.components
    )
    corrections_block = _format_corrections_block(order)
    corrections_section = f"\n\n{corrections_block}\n" if corrections_block else "\n"
    return f"""SECTION: {order.section.title}
SECTION_ID: {order.section.id}
ROLE: {order.section.role or "(unset)"}
CARD_ID: {order.section.card_id or "(none)"}
TRANSITION_NOTE: {order.section.transition_note or "first section — no prior"}

PLAN CONSTRAINTS (structured — honour each item):
- Write only the components listed below.
- Use each component's plan purpose and registry contract; do not invent a separate brief.
- Honour ANCHOR FACTS and CONSISTENCY RULES below.
- Honour SUPPORT ADAPTATIONS and register guidance.
{corrections_section}COMPONENTS TO WRITE:
{component_blocks}

REGISTER:
- Level: {order.register_spec.level}
- Sentence length: {order.register_spec.sentence_length}
- Vocabulary: {order.register_spec.vocabulary_policy}
- Tone: {order.register_spec.tone}
- Avoid: {", ".join(order.register_spec.avoid) or "none"}

LEARNER PROFILE:
{order.learner_profile.level_summary}
Reading load: {order.learner_profile.reading_load}
Language support: {order.learner_profile.language_support}
Pacing: {order.learner_profile.pacing}

SUPPORT ADAPTATIONS:
{format_support_adaptations(order.support_adaptations)}

ANCHOR FACTS (do not change these):
{format_source_of_truth(order.source_of_truth)}

CONSISTENCY RULES:
{format_consistency_rules(order.consistency_rules)}

SECTION CONSTRAINTS:
{chr(10).join(f"- {c}" for c in order.section.constraints) or "- none"}

{policy_block}"""


def _build_brief_order_context(order: SectionWriterWorkOrder) -> str:
    from contracts.lectio import get_formatting_policy

    components_list = "\n".join(
        f"- {c.teacher_label or c.component_id} ({c.component_id}): {c.content_intent}"
        for c in order.section.components
    )

    policy = get_formatting_policy()
    policy_block = format_formatting_policy_legend(policy)

    contract_blocks = "\n\n".join(
        format_component_contract_for_writer(
            order.component_cards.get(c.component_id, {}),
            c.content_intent,
        )
        for c in order.section.components
    )
    corrections_block = _format_corrections_block(order)
    corrections_section = f"\n{corrections_block}\n" if corrections_block else ""

    return f"""SECTION: {order.section.title}
SECTION_ID: {order.section.id}
LEARNING INTENT: {order.section.learning_intent}
{corrections_section}
COMPONENTS TO WRITE:
{components_list}

REGISTER:
- Level: {order.register_spec.level}
- Sentence length: {order.register_spec.sentence_length}
- Vocabulary: {order.register_spec.vocabulary_policy}
- Tone: {order.register_spec.tone}
- Avoid: {", ".join(order.register_spec.avoid) or "none"}

LEARNER PROFILE:
{order.learner_profile.level_summary}
Reading load: {order.learner_profile.reading_load}
Language support: {order.learner_profile.language_support}
Pacing: {order.learner_profile.pacing}

SUPPORT ADAPTATIONS:
{format_support_adaptations(order.support_adaptations)}

ANCHOR FACTS (do not change these):
{format_source_of_truth(order.source_of_truth)}

CONSISTENCY RULES:
{format_consistency_rules(order.consistency_rules)}

SECTION CONSTRAINTS:
{chr(10).join(f"- {c}" for c in order.section.constraints) or "- none"}

{policy_block}

LECTIO COMPONENT CONTRACTS:
{contract_blocks}"""


def build_section_writer_prompt(order: SectionWriterWorkOrder) -> str:
    shared_prefix = build_v3_shared_prefix()
    if _skip_expander_enabled():
        order_context = _build_skip_expander_order_context(order)
    else:
        order_context = _build_brief_order_context(order)

    body = _load_static_template().replace(_ORDER_CONTEXT_MARKER, order_context)
    return f"{shared_prefix}\n{body}\n"


def build_section_writer_retry_prompt(
    order: SectionWriterWorkOrder,
    prior_errors: list[str],
) -> str:
    """
    Build a retry prompt with focused correction guidance.
    """
    base_prompt = build_section_writer_prompt(order)
    error_lines = "\n".join(f"  - {e}" for e in prior_errors[:8])
    correction_block = f"""RETRY CORRECTION — your previous attempt had these problems:
{error_lines}

Fix ONLY the problems listed above. Do not change anything else.
Re-read the LECTIO COMPONENT CONTRACTS below and correct the identified fields.
"""
    first_newline = base_prompt.index("\n")
    return (
        base_prompt[: first_newline + 1]
        + "\n"
        + correction_block
        + "\n"
        + base_prompt[first_newline + 1 :]
    )


__all__ = ["build_section_writer_prompt", "build_section_writer_retry_prompt"]

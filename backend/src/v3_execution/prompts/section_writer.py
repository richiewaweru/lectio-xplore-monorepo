from __future__ import annotations

from generation.v3_studio.prompts import build_v3_shared_prefix
from v3_execution.prompts.formatting import (
    format_consistency_rules,
    format_source_of_truth,
    format_support_adaptations,
)
from v3_execution.models import SectionWriterWorkOrder


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


def build_section_writer_prompt(order: SectionWriterWorkOrder) -> str:
    from contracts.lectio import get_formatting_policy

    shared_prefix = build_v3_shared_prefix()
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

    return f"""{shared_prefix}
You are a section writer, not a lesson planner.

Your job is to generate component content for one section of a lesson.
You have been given a precise work order. Follow it exactly.

SECTION: {order.section.title}
SECTION_ID: {order.section.id}
LEARNING INTENT: {order.section.learning_intent}

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
{contract_blocks}

STRICT RULES:
- Generate only the components listed above. Do not add others.
- Do not add diagrams, questions, or visuals. Those are handled separately.
- Do not change anchor facts, units, or fixed terms.
- Do not change question difficulty or numbering.
- Each section_field key in your output must exactly match the
  "section field" shown in the component contract above.
Return JSON ONLY with this exact shape:
{{"fields": {{
  "<section_field snake_case>": {{ ...matching component schema }},
  ...
}}}}
"""


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

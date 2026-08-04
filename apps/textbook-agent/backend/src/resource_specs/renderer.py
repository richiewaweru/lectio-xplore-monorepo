from __future__ import annotations

from resource_specs.schema import ResourceSpec, SectionSpec


def render_spec_for_prompt(
    spec: ResourceSpec,
    depth: str,
    active_roles: list[str],
    active_supports: list[str],
) -> str:
    limit = spec.depth_limit(depth)
    active_role_set = set(active_roles)
    active_support_set = set(active_supports)
    sections = [
        section
        for section in [*spec.sections.required, *spec.sections.optional]
        if (
            section.role in active_role_set
            or section in spec.sections.required
            or section.only_when_support in active_support_set
        )
    ]

    lines = [
        f"Resource type: {spec.label}",
        "",
        "Resource intent:",
        spec.intent.strip(),
    ]

    if spec.forbidden_components:
        lines.extend(
            [
                "",
                "HARD CONSTRAINT - these components are NEVER permitted for this resource type:",
                *[f"- {component}" for component in spec.forbidden_components],
            ]
        )

    lines.extend(
        [
            "",
            f"Depth: {depth}",
            f"Target time: {limit.time_minutes} minutes",
            f"Section count: {limit.sections}",
            f"Question count: {limit.questions}",
        ]
    )
    if limit.note:
        lines.append(f"Depth note: {limit.note}")
    if limit.warning:
        lines.append(f"Depth warning: {limit.warning}")

    lines.append("")
    lines.append("Resource sections and component rules:")
    for section in sections:
        lines.extend(_render_section(section))

    support_blocks = [
        (key, modification)
        for key, modification in spec.supports.items()
        if key in active_support_set
    ]
    if support_blocks:
        lines.extend(["", "Active support modifications:"])
        for key, modification in support_blocks:
            lines.append(f"- Support: {key}")
            if modification.intent_note:
                lines.append(f"  Instruction: {modification.intent_note}")
            if modification.note:
                lines.append(f"  Note: {modification.note}")
            if modification.preferred_components:
                lines.append(
                    f"  Preferred components: {', '.join(modification.preferred_components)}"
                )
            if modification.adds_section:
                lines.append(f"  Adds section: {modification.adds_section}")
            if modification.adds_component:
                lines.append(f"  Adds component: {modification.adds_component}")

    if spec.validation:
        lines.extend(["", "Validation rules:", *[f"- {rule}" for rule in spec.validation]])

    return "\n".join(lines)


def _render_section(section: SectionSpec) -> list[str]:
    lines = ["", f"Section role: {section.role}", f"Intent: {section.intent.strip()}"]
    if section.preferred_components:
        lines.append(f"Preferred components: {', '.join(section.preferred_components)}")
    if section.allowed_components:
        lines.append(f"Also allowed: {', '.join(section.allowed_components)}")
    if section.forbidden_components:
        lines.append(f"Forbidden here: {', '.join(section.forbidden_components)}")
    if section.placement:
        lines.append(f"Placement: {section.placement}")
    if section.only_when_support:
        lines.append(f"Only when support is active: {section.only_when_support}")
    return lines

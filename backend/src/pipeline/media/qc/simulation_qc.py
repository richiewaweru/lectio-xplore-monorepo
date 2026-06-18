from __future__ import annotations

from pipeline.media.types import VisualSlot
from pipeline.types.section_content import DiagramContent, SimulationContent

_FORBIDDEN_PATTERNS = [
    "<script src=",
    "cdn.jsdelivr",
    "unpkg.com",
    "cdnjs.cloudflare",
    "googleapis.com",
    "import ",
    "require(",
    "@import",
    "fetch(",
    "XMLHttpRequest",
    "window.parent",
    "window.top",
    "postMessage",
]


def _check_html_safety(html_content: str) -> list[str]:
    lowered = html_content.lower()
    issues: list[str] = []
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.lower() in lowered:
            issues.append(f"simulation html_content contains forbidden pattern: {pattern}")
    return issues


def _check_complexity(html_content: str) -> list[str]:
    slider_count = html_content.lower().count('input type="range"') + html_content.lower().count(
        "input[type=range]"
    )
    if slider_count > 4:
        return ["simulation html_content uses more than four slider controls"]
    return []


def validate_simulation_content(
    *,
    slot: VisualSlot,
    simulation: SimulationContent | None,
    fallback_diagram: DiagramContent | None,
) -> list[str]:
    issues: list[str] = []
    if simulation is None:
        issues.append("simulation content is missing")
        return issues
    if simulation.spec is None:
        issues.append("simulation spec is missing")

    html_content = (simulation.html_content or "").strip()
    if not html_content:
        issues.append("simulation html_content is missing")
    else:
        issues.extend(_check_html_safety(html_content))
        issues.extend(_check_complexity(html_content))

    if slot.expects_static_fallback and fallback_diagram is None:
        issues.append("simulation fallback_diagram is required for print translation")
    return issues


__all__ = [
    "_FORBIDDEN_PATTERNS",
    "_check_complexity",
    "_check_html_safety",
    "validate_simulation_content",
]

from __future__ import annotations

from contracts.section_content import SectionContent


def section_title(section: SectionContent, fallback: str | None = None) -> str:
    if section.header is not None and section.header.title.strip():
        return section.header.title.strip()
    if fallback and fallback.strip():
        return fallback.strip()
    if section.section_id.strip():
        return section.section_id.strip()
    return "Untitled section"


def practice_problems(section: SectionContent) -> list:
    if section.practice is None:
        return []
    return list(section.practice.problems)

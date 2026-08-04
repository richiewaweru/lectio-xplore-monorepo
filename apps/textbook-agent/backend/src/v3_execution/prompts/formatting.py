from __future__ import annotations

from v3_execution.models import SourceOfTruthEntry


def format_source_of_truth(entries: list[SourceOfTruthEntry]) -> str:
    if not entries:
        return "(none)"
    return "\n".join(f"- [{e.key}] {e.text}" for e in entries)


def format_consistency_rules(rules: list[str]) -> str:
    if not rules:
        return "(none)"
    return "\n".join(f"- {r}" for r in rules)


def format_support_adaptations(adaptations: list[str]) -> str:
    if not adaptations:
        return "(none)"
    return "\n".join(f"- {a}" for a in adaptations)


__all__ = [
    "format_consistency_rules",
    "format_source_of_truth",
    "format_support_adaptations",
]

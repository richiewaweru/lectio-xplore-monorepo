"""Writer inputs for the lesson backbone (plain data, no I/O)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


def _texts(values: Iterable[Any] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        if isinstance(value, Mapping):
            value = value.get("statement") or value.get("term") or value.get("description")
        text = str(value or "").strip()
        if text:
            out.append(text)
    return out


def card_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """One concept card as the writer sees it.

    ``risk`` is read defensively: it may not exist on every misconception yet.
    """
    misconceptions: list[dict[str, Any]] = []
    for item in row.get("misconceptions") or []:
        if not isinstance(item, Mapping):
            continue
        entry: dict[str, Any] = {
            "id": str(item.get("id") or ""),
            "description": str(item.get("description") or item.get("statement") or ""),
        }
        risk = item.get("risk")
        if risk:
            entry["risk"] = risk
        misconceptions.append(entry)
    return {
        "id": str(row.get("id") or ""),
        "title": str(row.get("title") or ""),
        "objective": str(row.get("objective") or ""),
        "misconceptions": misconceptions,
    }


@dataclass(frozen=True)
class BackboneInputs:
    objective: str
    cards: list[dict[str, Any]]
    seed_anchor: str
    anchor_reuse_scope: str = ""
    sections: list[dict[str, str]] = field(default_factory=list)
    subject: str = ""
    level: str = ""
    notation: str | None = None
    terminology: list[str] = field(default_factory=list)
    must_not_introduce: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "concept_cards": self.cards,
            "seed_anchor": {
                "description": self.seed_anchor,
                "reuse_scope": self.anchor_reuse_scope,
            },
            "sections": self.sections,
            "subject": self.subject,
            "level": self.level,
            "notation": self.notation,
            "terminology": self.terminology,
            "exclusions": self.must_not_introduce,
            "assumed_prerequisites": self.prerequisites,
        }

    def input_hash(self) -> str:
        canonical = json.dumps(
            self.payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_backbone_inputs(
    *,
    structural_plan: Any,
    context: Mapping[str, Any],
    card_rows: Iterable[Mapping[str, Any]],
    subject: str,
    level: str,
    notation: str | None,
) -> BackboneInputs:
    """Assemble writer inputs from the approved plan, context and concept cards.

    ``structural_plan`` is a :class:`StructuralPlan`; ``card_rows`` are the
    approved (possibly teacher-edited) concept cards as plain mappings.
    """
    cards = [card_payload(row) for row in card_rows]
    scope = context.get("scope_contract") if isinstance(context, Mapping) else None
    scope = scope if isinstance(scope, Mapping) else {}
    objective = str(structural_plan.lesson_intent.goal or "").strip() or (
        cards[0]["objective"] if cards else ""
    )
    return BackboneInputs(
        objective=objective,
        cards=cards,
        seed_anchor=str(structural_plan.anchor.example or "").strip(),
        anchor_reuse_scope=str(structural_plan.anchor.reuse_scope or "").strip(),
        sections=[
            {
                "id": section.id,
                "role": section.role,
                "title": section.title,
                "purpose": section.purpose,
            }
            for section in structural_plan.sections
        ],
        subject=subject,
        level=level,
        notation=notation or scope.get("notation") or None,
        terminology=_texts(scope.get("terminology")),
        must_not_introduce=_texts(
            scope.get("must_not_introduce") or context.get("exclusions")
        ),
        prerequisites=_texts(scope.get("assumed_prerequisites")),
    )


__all__ = ["BackboneInputs", "build_backbone_inputs", "card_payload"]

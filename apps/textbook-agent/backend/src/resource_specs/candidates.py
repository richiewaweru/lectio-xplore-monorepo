"""Whole-lesson guidance assembly from resource vocabulary and skeleton slots.

v1.1 replaces the closed candidate fence with:
  excluded            hard wall
  permitted           available; atypical use requires departure_reason
  typical_intents     guidance, not a gate
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

FIRST_SLICE_OBJECTS = frozenset(
    {"prose", "list", "table", "figure", "worked-example", "questions"}
)
ALWAYS_EXCLUDED_OBJECTS = frozenset({"heading", "answer-key"})


class CandidateConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ObjectCandidate:
    id: str
    record: dict[str, Any]


@dataclass(frozen=True)
class IntentCandidate:
    id: str
    record: dict[str, Any]
    objects: tuple[ObjectCandidate, ...]
    typical: bool = False


@dataclass(frozen=True)
class SlotGuidance:
    slot_id: str
    typical_intents: tuple[str, ...]
    permitted_intents: tuple[IntentCandidate, ...]
    excluded_intents: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class LessonGuidance:
    slots: tuple[SlotGuidance, ...]
    permitted_intent_ids: frozenset[str]
    excluded_intents: dict[str, str]
    permitted_object_ids: frozenset[str]


class _IntentBuckets(Protocol):
    permitted: list[str]
    core: list[str]
    optional: list[str]
    excluded: list[str] | dict[str, str]


class _ObjectBuckets(Protocol):
    allowed: list[str]
    excluded: list[str] | dict[str, str]


class _Vocabulary(Protocol):
    intents: _IntentBuckets
    objects: _ObjectBuckets


class _ResourceSpecLike(Protocol):
    id: str
    vocabulary: _Vocabulary | None


def _as_id_set(value: list[str] | dict[str, str] | None) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, dict):
        return set(value.keys())
    return set(value)


def _excluded_reasons(value: list[str] | dict[str, str] | None) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(reason) for key, reason in value.items()}
    return {str(item): "excluded by resource vocabulary" for item in value}


def _slot_typical_intents(skeleton_slot: Mapping[str, Any]) -> list[str]:
    raw = skeleton_slot.get("typical_intents")
    if raw is None:
        # Temporary bridge while skeletons migrate; remove after Cutline 1.5 rename.
        raw = skeleton_slot.get("candidate_intents") or {}
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if not isinstance(raw, Mapping):
        return []
    # Legacy core/optional buckets collapse to typical guidance order.
    if "core" in raw or "optional" in raw:
        return [str(item) for item in [*(raw.get("core") or []), *(raw.get("optional") or [])]]
    return [str(item) for item in (raw.get("typical") or raw.get("intents") or [])]


def _permitted_intent_ids(vocab: _Vocabulary) -> set[str]:
    permitted = list(getattr(vocab.intents, "permitted", None) or [])
    if permitted:
        return set(permitted)
    return set(vocab.intents.core) | set(vocab.intents.optional)


def assemble_slot_guidance(
    *,
    resource_spec: _ResourceSpecLike,
    skeleton_slot: Mapping[str, Any],
    intent_catalogue: dict[str, dict[str, Any]],
    object_catalogue: dict[str, dict[str, Any]],
    implemented_objects: set[str] | None = None,
) -> SlotGuidance:
    if resource_spec.vocabulary is None:
        raise CandidateConfigurationError(
            f"resource={resource_spec.id!r} has no page vocabulary; "
            "cannot assemble lesson guidance"
        )

    implemented = set(implemented_objects or FIRST_SLICE_OBJECTS)
    vocab = resource_spec.vocabulary
    excluded = _excluded_reasons(vocab.intents.excluded)
    resource_intents = _permitted_intent_ids(vocab) - set(excluded.keys())
    resource_objects = set(vocab.objects.allowed) - _as_id_set(vocab.objects.excluded)
    resource_objects -= ALWAYS_EXCLUDED_OBJECTS

    slot_id = str(
        skeleton_slot.get("slot_id")
        or skeleton_slot.get("id")
        or skeleton_slot.get("role")
        or "<unknown>"
    )
    typical = _slot_typical_intents(skeleton_slot)
    typical_set = set(typical)

    permitted_rows: list[IntentCandidate] = []
    for intent_id in sorted(resource_intents):
        intent = intent_catalogue.get(intent_id)
        if not intent or intent.get("selectable", True) is False:
            continue
        valid_objects = [
            object_id
            for object_id in intent.get("valid_objects", [])
            if object_id in resource_objects
            and object_id in implemented
            and object_id not in ALWAYS_EXCLUDED_OBJECTS
            and object_id in object_catalogue
        ]
        permitted_rows.append(
            IntentCandidate(
                id=intent_id,
                record=intent,
                objects=tuple(
                    ObjectCandidate(id=object_id, record=object_catalogue[object_id])
                    for object_id in valid_objects
                ),
                typical=intent_id in typical_set,
            )
        )

    # Preserve typical order first, then remaining permitted.
    ordered: list[IntentCandidate] = []
    seen: set[str] = set()
    by_id = {row.id: row for row in permitted_rows}
    for intent_id in typical:
        row = by_id.get(intent_id)
        if row is None or intent_id in seen:
            continue
        ordered.append(row)
        seen.add(intent_id)
    for row in permitted_rows:
        if row.id in seen:
            continue
        ordered.append(row)
        seen.add(row.id)

    return SlotGuidance(
        slot_id=slot_id,
        typical_intents=tuple(intent_id for intent_id in typical if intent_id in by_id),
        permitted_intents=tuple(ordered),
        excluded_intents=tuple(sorted(excluded.items())),
    )


def assemble_lesson_guidance(
    *,
    resource_spec: _ResourceSpecLike,
    skeleton_slots: Mapping[str, Mapping[str, Any]],
    intent_catalogue: dict[str, dict[str, Any]],
    object_catalogue: dict[str, dict[str, Any]],
    implemented_objects: set[str] | None = None,
) -> LessonGuidance:
    if resource_spec.vocabulary is None:
        raise CandidateConfigurationError(
            f"resource={resource_spec.id!r} has no page vocabulary"
        )
    vocab = resource_spec.vocabulary
    excluded = _excluded_reasons(vocab.intents.excluded)
    permitted_intent_ids = frozenset(_permitted_intent_ids(vocab) - set(excluded.keys()))
    permitted_object_ids = frozenset(
        set(vocab.objects.allowed)
        - _as_id_set(vocab.objects.excluded)
        - ALWAYS_EXCLUDED_OBJECTS
    )
    slots: list[SlotGuidance] = []
    for slot_id, slot in skeleton_slots.items():
        payload = dict(slot)
        payload["slot_id"] = slot_id
        slots.append(
            assemble_slot_guidance(
                resource_spec=resource_spec,
                skeleton_slot=payload,
                intent_catalogue=intent_catalogue,
                object_catalogue=object_catalogue,
                implemented_objects=implemented_objects,
            )
        )
    return LessonGuidance(
        slots=tuple(slots),
        permitted_intent_ids=permitted_intent_ids,
        excluded_intents=excluded,
        permitted_object_ids=permitted_object_ids,
    )


def resolve_block_candidates(
    *,
    resource_spec: _ResourceSpecLike,
    skeleton_slot: Mapping[str, Any],
    intent_catalogue: dict[str, dict[str, Any]],
    object_catalogue: dict[str, dict[str, Any]],
    implemented_objects: set[str] | None = None,
) -> tuple[IntentCandidate, ...]:
    """Compatibility wrapper — returns permitted intents that still have objects.

    Empty matrices no longer raise; departure-rate patterns surface config issues.
    Prefer ``assemble_slot_guidance`` / ``assemble_lesson_guidance`` for new code.
    """
    guidance = assemble_slot_guidance(
        resource_spec=resource_spec,
        skeleton_slot=skeleton_slot,
        intent_catalogue=intent_catalogue,
        object_catalogue=object_catalogue,
        implemented_objects=implemented_objects,
    )
    return tuple(intent for intent in guidance.permitted_intents if intent.objects)

"""Deterministic page-block candidate matrix resolver.

Intersects resource vocabulary with skeleton slot candidate intents.
Does not call an LLM. Does not introduce StanceSpec.
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


class _IntentBuckets(Protocol):
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


def _slot_candidate_intents(skeleton_slot: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    raw = skeleton_slot.get("candidate_intents") or {}
    if not isinstance(raw, Mapping):
        return [], []
    core = list(raw.get("core") or [])
    optional = list(raw.get("optional") or [])
    return core, optional


def resolve_block_candidates(
    *,
    resource_spec: _ResourceSpecLike,
    skeleton_slot: Mapping[str, Any],
    intent_catalogue: dict[str, dict[str, Any]],
    object_catalogue: dict[str, dict[str, Any]],
    implemented_objects: set[str] | None = None,
) -> tuple[IntentCandidate, ...]:
    """Return ordered intent→object candidate matrix for one section slot."""
    if resource_spec.vocabulary is None:
        raise CandidateConfigurationError(
            f"resource={resource_spec.id!r} has no page vocabulary; "
            "cannot resolve block candidates"
        )

    implemented = set(implemented_objects or FIRST_SLICE_OBJECTS)
    vocab = resource_spec.vocabulary

    resource_intents = set(vocab.intents.core) | set(vocab.intents.optional)
    excluded_intents = _as_id_set(vocab.intents.excluded)
    resource_objects = set(vocab.objects.allowed) - _as_id_set(vocab.objects.excluded)
    resource_objects -= ALWAYS_EXCLUDED_OBJECTS

    core_intents, optional_intents = _slot_candidate_intents(skeleton_slot)
    slot_intents = set(core_intents) | set(optional_intents)
    slot_id = str(
        skeleton_slot.get("slot_id")
        or skeleton_slot.get("id")
        or skeleton_slot.get("role")
        or "<unknown>"
    )

    result: list[IntentCandidate] = []
    for intent_id in [*core_intents, *optional_intents]:
        if intent_id not in resource_intents or intent_id in excluded_intents:
            continue
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
        if valid_objects:
            result.append(
                IntentCandidate(
                    id=intent_id,
                    record=intent,
                    objects=tuple(
                        ObjectCandidate(id=object_id, record=object_catalogue[object_id])
                        for object_id in valid_objects
                    ),
                )
            )

    if not result:
        raise CandidateConfigurationError(
            f"No page-block candidates for resource={resource_spec.id!r}, "
            f"slot={slot_id!r}; resource_intents={sorted(resource_intents)}, "
            f"slot_intents={sorted(slot_intents)}, implemented_objects={sorted(implemented)}"
        )
    return tuple(result)

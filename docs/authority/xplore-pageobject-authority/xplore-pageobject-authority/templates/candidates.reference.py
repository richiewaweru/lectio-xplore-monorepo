from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


def resolve_block_candidates(
    *,
    resource_spec,
    skeleton_slot,
    intent_catalogue: dict[str, dict[str, Any]],
    object_catalogue: dict[str, dict[str, Any]],
    implemented_objects: set[str],
) -> tuple[IntentCandidate, ...]:
    resource_intents = set(resource_spec.vocabulary.intents.core) | set(
        resource_spec.vocabulary.intents.optional
    )
    excluded_intents = set(resource_spec.vocabulary.intents.excluded)
    slot_intents = set(skeleton_slot.candidate_intents.core) | set(
        skeleton_slot.candidate_intents.optional
    )
    resource_objects = set(resource_spec.vocabulary.objects.allowed)
    resource_objects -= set(resource_spec.vocabulary.objects.excluded)

    result: list[IntentCandidate] = []
    for intent_id in [
        *skeleton_slot.candidate_intents.core,
        *skeleton_slot.candidate_intents.optional,
    ]:
        if intent_id not in resource_intents or intent_id in excluded_intents:
            continue
        intent = intent_catalogue.get(intent_id)
        if not intent or intent.get("selectable", True) is False:
            continue
        valid_objects = [
            object_id
            for object_id in intent.get("valid_objects", [])
            if object_id in resource_objects
            and object_id in implemented_objects
            and object_id != "heading"
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
            f"slot={skeleton_slot.slot_id!r}; resource_intents={sorted(resource_intents)}, "
            f"slot_intents={sorted(slot_intents)}, implemented_objects={sorted(implemented_objects)}"
        )
    return tuple(result)

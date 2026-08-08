"""Canonical lesson legality snapshot — computed once, persisted, reused.

schema v1 page state: no lesson_legality; fat FormPlan may exist.
schema v2 page state: slim FormDecision + persisted LessonLegalitySnapshot.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from contracts.lectio_page import get_intent_catalogue, get_object_catalogue
from planning.catalogue_projections import (
    _IMPLEMENTED_FORM_OBJECTS,
    _NEVER_SELECTABLE_OBJECTS,
)
from planning.whole_lesson.packet import ImmutableLessonPacket
from resource_specs.candidates import assemble_lesson_guidance
from resource_specs.loader import get_spec
from v3_blueprint.skeletons import load_skeleton_catalog


class LessonLegalitySnapshot(BaseModel):
    """Code-owned legality fence for one prepared lesson."""

    model_config = ConfigDict(extra="forbid")

    resource_id: str
    catalogue_version: str
    catalogue_hash: str

    permitted_intents: list[str] = Field(default_factory=list)
    excluded_intents: list[str] = Field(default_factory=list)
    typical_by_slot: dict[str, list[str]] = Field(default_factory=dict)
    permitted_objects: list[str] = Field(default_factory=list)
    compatible_objects_by_intent: dict[str, list[str]] = Field(default_factory=dict)


class LessonLegalityError(RuntimeError):
    """Fail-closed legality load/build failure."""

    def __init__(self, message: str, *, code: str = "LESSON_LEGALITY_INVALID") -> None:
        self.code = code
        super().__init__(message)


def _sorted_unique(values: list[str] | set[str] | frozenset[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(item) for item in values if str(item)})


def _legality_hash_payload(
    snapshot: LessonLegalitySnapshot | dict[str, Any],
) -> dict[str, Any]:
    """Deterministic payload for snapshot integrity hashing (excludes catalogue_hash)."""
    if isinstance(snapshot, LessonLegalitySnapshot):
        data = snapshot.model_dump(mode="json")
    else:
        data = dict(snapshot)

    typical_raw = data.get("typical_by_slot") or {}
    typical_by_slot = {
        str(slot_id): _sorted_unique(list(intents or []))
        for slot_id, intents in sorted(typical_raw.items(), key=lambda item: str(item[0]))
    }
    compat_raw = data.get("compatible_objects_by_intent") or {}
    compatible_objects_by_intent = {
        str(intent_id): _sorted_unique(list(objects or []))
        for intent_id, objects in sorted(
            compat_raw.items(), key=lambda item: str(item[0])
        )
    }
    return {
        "resource_id": str(data.get("resource_id") or ""),
        "catalogue_version": str(data.get("catalogue_version") or ""),
        "permitted_intents": _sorted_unique(list(data.get("permitted_intents") or [])),
        "excluded_intents": _sorted_unique(list(data.get("excluded_intents") or [])),
        "typical_by_slot": typical_by_slot,
        "permitted_objects": _sorted_unique(list(data.get("permitted_objects") or [])),
        "compatible_objects_by_intent": compatible_objects_by_intent,
    }


def legality_hash(snapshot: LessonLegalitySnapshot | dict[str, Any]) -> str:
    """Stable hash of snapshot content (excluding catalogue_hash itself)."""
    payload = _legality_hash_payload(snapshot)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_lesson_legality_snapshot(
    packet: ImmutableLessonPacket,
) -> LessonLegalitySnapshot:
    """Call assemble_lesson_guidance exactly once and freeze the result."""
    intents = get_intent_catalogue()["intents"]
    objects = get_object_catalogue()["objects"]
    spec = get_spec(packet.resource_id)
    catalog = load_skeleton_catalog()
    slots = {
        slot.slot_id: {
            **dict(catalog.slots.get(slot.slot_id) or {}),
            "slot_id": slot.slot_id,
            "typical_intents": list(slot.typical_intents),
        }
        for slot in packet.slots
    }
    guidance = assemble_lesson_guidance(
        resource_spec=spec,
        skeleton_slots=slots,
        intent_catalogue=intents,
        object_catalogue=objects,
    )
    typical_by_slot = {
        slot.slot_id: _sorted_unique(slot.typical_intents) for slot in guidance.slots
    }
    # Prefer packet slot order; fill any guidance slots not already present.
    for slot in packet.slots:
        typical_by_slot.setdefault(
            slot.slot_id, _sorted_unique(slot.typical_intents)
        )

    catalogue_version = str(
        get_intent_catalogue().get("catalogue_version")
        or get_object_catalogue().get("catalogue_version")
        or "unknown"
    )
    permitted_intents = _sorted_unique(guidance.permitted_intent_ids)
    permitted_objects = _sorted_unique(guidance.permitted_object_ids)
    permitted_object_set = set(permitted_objects)
    implemented = set(_IMPLEMENTED_FORM_OBJECTS) - set(_NEVER_SELECTABLE_OBJECTS)

    compatible_objects_by_intent: dict[str, list[str]] = {}
    for intent_id in permitted_intents:
        record = intents.get(intent_id) if isinstance(intents, dict) else None
        valid = set()
        if isinstance(record, dict):
            valid = {
                str(object_id)
                for object_id in (record.get("valid_objects") or [])
                if object_id
            }
        compatible = sorted(
            (valid & permitted_object_set & implemented) - set(_NEVER_SELECTABLE_OBJECTS)
        )
        compatible_objects_by_intent[intent_id] = compatible

    draft = {
        "resource_id": packet.resource_id,
        "catalogue_version": catalogue_version,
        "permitted_intents": permitted_intents,
        "excluded_intents": _sorted_unique(guidance.excluded_intents.keys()),
        "typical_by_slot": {
            key: typical_by_slot[key] for key in sorted(typical_by_slot.keys())
        },
        "permitted_objects": permitted_objects,
        "compatible_objects_by_intent": compatible_objects_by_intent,
    }
    digest = legality_hash(draft)
    return LessonLegalitySnapshot(
        resource_id=draft["resource_id"],
        catalogue_version=draft["catalogue_version"],
        catalogue_hash=digest,
        permitted_intents=draft["permitted_intents"],
        excluded_intents=draft["excluded_intents"],
        typical_by_slot=draft["typical_by_slot"],
        permitted_objects=draft["permitted_objects"],
        compatible_objects_by_intent=draft["compatible_objects_by_intent"],
    )


def validate_legality_snapshot(
    packet: ImmutableLessonPacket,
    snapshot: LessonLegalitySnapshot,
) -> None:
    """Fail closed if persisted/built legality does not match the packet fence."""
    if snapshot.resource_id != packet.resource_id:
        raise LessonLegalityError(
            f"lesson_legality resource_id mismatch: "
            f"snapshot={snapshot.resource_id!r} packet={packet.resource_id!r}",
            code="LESSON_LEGALITY_RESOURCE_MISMATCH",
        )

    expected_hash = legality_hash(snapshot)
    if snapshot.catalogue_hash != expected_hash:
        raise LessonLegalityError(
            "lesson_legality catalogue_hash mismatch; snapshot integrity failed",
            code="LESSON_LEGALITY_HASH_MISMATCH",
        )

    for slot in packet.slots:
        if slot.slot_id not in snapshot.typical_by_slot:
            raise LessonLegalityError(
                f"lesson_legality missing typical intents for slot {slot.slot_id!r}",
                code="MISSING_SLOT_LEGALITY",
            )

    permitted = set(snapshot.permitted_intents)
    excluded = set(snapshot.excluded_intents)
    for slot_id, intents in snapshot.typical_by_slot.items():
        for intent_id in intents:
            if intent_id not in permitted and intent_id not in excluded:
                raise LessonLegalityError(
                    f"typical intent {intent_id!r} in slot {slot_id!r} is neither "
                    "permitted nor excluded",
                    code="LESSON_LEGALITY_INTENT_COVERAGE",
                )

    for intent_id in snapshot.permitted_intents:
        if intent_id not in snapshot.compatible_objects_by_intent:
            raise LessonLegalityError(
                f"permitted intent {intent_id!r} missing compatible_objects_by_intent key",
                code="LESSON_LEGALITY_MISSING_COMPATIBILITY",
            )

    permitted_objects = set(snapshot.permitted_objects)
    for intent_id, objects in snapshot.compatible_objects_by_intent.items():
        for object_id in objects:
            if object_id in _NEVER_SELECTABLE_OBJECTS:
                raise LessonLegalityError(
                    f"compatible object {object_id!r} for intent {intent_id!r} "
                    "is never selectable",
                    code="LESSON_LEGALITY_FORBIDDEN_OBJECT",
                )
            if object_id not in permitted_objects:
                raise LessonLegalityError(
                    f"compatible object {object_id!r} for intent {intent_id!r} "
                    "is outside permitted_objects",
                    code="LESSON_LEGALITY_OBJECT_FENCE",
                )


def snapshot_as_teaching_sets(
    legality: LessonLegalitySnapshot,
) -> tuple[set[str], set[str], dict[str, set[str]]]:
    return (
        set(legality.permitted_intents),
        set(legality.excluded_intents),
        {
            slot_id: set(values)
            for slot_id, values in legality.typical_by_slot.items()
        },
    )


_DEPARTURE_RULE = (
    "A permitted non-typical intent requires a specific departure_reason. "
    "Excluded intents are never legal."
)


def project_slot_intent_policy(
    snapshot: LessonLegalitySnapshot,
) -> dict[str, Any]:
    """Deterministic prompt policy projected from the persisted legality snapshot.

    Validator and prompt must derive from this same snapshot/hash. Do not invent
    a second persisted legal_intents contract.
    """
    permitted = set(snapshot.permitted_intents)
    excluded = set(snapshot.excluded_intents)
    legal = permitted - excluded
    policy: dict[str, Any] = {}
    for slot_id in sorted(snapshot.typical_by_slot.keys()):
        typical = list(snapshot.typical_by_slot.get(slot_id) or [])
        typical_set = set(typical)
        policy[slot_id] = {
            "typical_intents": typical,
            "permitted_departures": sorted(legal - typical_set),
            "departure_rule": _DEPARTURE_RULE,
        }
    return {
        "slot_intent_policy": policy,
        "catalogue_hash": snapshot.catalogue_hash,
        "catalogue_version": snapshot.catalogue_version,
    }

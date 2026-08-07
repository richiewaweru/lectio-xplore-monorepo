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


class LessonLegalityError(RuntimeError):
    """Fail-closed legality load/build failure."""


def _sorted_unique(values: list[str] | set[str] | frozenset[str] | tuple[str, ...]) -> list[str]:
    return sorted({str(item) for item in values if str(item)})


def legality_hash(snapshot: LessonLegalitySnapshot | dict[str, Any]) -> str:
    """Stable hash of snapshot content (excluding catalogue_hash itself)."""
    if isinstance(snapshot, LessonLegalitySnapshot):
        payload = snapshot.model_dump(mode="json")
    else:
        payload = dict(snapshot)
    payload.pop("catalogue_hash", None)
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
    draft = {
        "resource_id": packet.resource_id,
        "catalogue_version": catalogue_version,
        "permitted_intents": _sorted_unique(guidance.permitted_intent_ids),
        "excluded_intents": _sorted_unique(guidance.excluded_intents.keys()),
        "typical_by_slot": {
            key: typical_by_slot[key] for key in sorted(typical_by_slot.keys())
        },
        "permitted_objects": _sorted_unique(guidance.permitted_object_ids),
    }
    digest = hashlib.sha256(
        json.dumps(draft, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    return LessonLegalitySnapshot(
        resource_id=draft["resource_id"],
        catalogue_version=draft["catalogue_version"],
        catalogue_hash=digest,
        permitted_intents=draft["permitted_intents"],
        excluded_intents=draft["excluded_intents"],
        typical_by_slot=draft["typical_by_slot"],
        permitted_objects=draft["permitted_objects"],
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

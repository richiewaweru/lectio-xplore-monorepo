"""Catalogue projections — structural information barrier for whole-lesson planning.

One master catalogue produces three typed views. Teaching guidance must never
contain page-object IDs, schemas, capacity, or form names.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from contracts.lectio_page import (
    PAGE_OBJECT_IDS,
    get_intent_catalogue,
    get_object_catalogue,
)


@dataclass(frozen=True)
class TeachingIntentGuidance:
    id: str
    teaching_role: str
    choose_when: str
    not_when: str
    status: str  # permitted | excluded
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class TeachingGuidanceProjection:
    intents: tuple[TeachingIntentGuidance, ...]
    catalogue_version: str
    projection_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalogue_version": self.catalogue_version,
            "projection_hash": self.projection_hash,
            "intents": [asdict(item) for item in self.intents],
        }

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class FormObjectGuidance:
    id: str
    compatible_intents: tuple[str, ...]
    earns_its_place_when: str
    choose_when: str
    not_when: str
    capacity_summary: str
    placement_restrictions: str


@dataclass(frozen=True)
class FormGuidanceProjection:
    objects: tuple[FormObjectGuidance, ...]
    by_intent: dict[str, tuple[str, ...]]
    catalogue_version: str
    projection_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalogue_version": self.catalogue_version,
            "projection_hash": self.projection_hash,
            "objects": [asdict(item) for item in self.objects],
            "by_intent": {key: list(value) for key, value in self.by_intent.items()},
        }


@dataclass(frozen=True)
class WriterContractProjection:
    object_id: str
    generation_guidance: str
    content_schema: dict[str, Any]
    capacity: dict[str, Any]
    object_validation: tuple[str, ...]
    failure_examples: tuple[str, ...]
    catalogue_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "generation_guidance": self.generation_guidance,
            "content_schema": self.content_schema,
            "capacity": self.capacity,
            "object_validation": list(self.object_validation),
            "failure_examples": list(self.failure_examples),
            "catalogue_version": self.catalogue_version,
        }


def _catalogue_version(intents_doc: Mapping[str, Any], objects_doc: Mapping[str, Any]) -> str:
    return str(
        intents_doc.get("catalogue_version")
        or objects_doc.get("catalogue_version")
        or "unknown"
    )


def _hash_payload(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _excluded_map(excluded: list[str] | dict[str, str] | None) -> dict[str, str]:
    if excluded is None:
        return {}
    if isinstance(excluded, dict):
        return {str(key): str(value) for key, value in excluded.items()}
    return {str(item): "excluded by resource vocabulary" for item in excluded}


def project_teaching_guidance(
    *,
    permitted_intent_ids: set[str] | None = None,
    excluded_intents: list[str] | dict[str, str] | None = None,
    intent_catalogue: Mapping[str, Any] | None = None,
    object_catalogue: Mapping[str, Any] | None = None,
) -> TeachingGuidanceProjection:
    intents_doc = intent_catalogue or get_intent_catalogue()
    objects_doc = object_catalogue or get_object_catalogue()
    intents = intents_doc.get("intents") or {}
    excluded = _excluded_map(excluded_intents)
    # Empty set must fail closed. Only None means "all catalogue intents".
    if permitted_intent_ids is None:
        permitted = set(intents.keys()) - set(excluded.keys())
    else:
        permitted = set(permitted_intent_ids) - set(excluded.keys())

    rows: list[TeachingIntentGuidance] = []
    for intent_id, record in sorted(intents.items()):
        if not isinstance(record, dict):
            continue
        if intent_id in excluded:
            rows.append(
                TeachingIntentGuidance(
                    id=intent_id,
                    teaching_role=str(record.get("pedagogical_role") or ""),
                    choose_when=str(record.get("choose_when") or record.get("generation_guidance") or ""),
                    not_when=str(record.get("not_when") or record.get("do_not_choose_when") or ""),
                    status="excluded",
                    exclusion_reason=excluded[intent_id],
                )
            )
            continue
        if intent_id not in permitted:
            continue
        if record.get("selectable", True) is False:
            continue
        rows.append(
            TeachingIntentGuidance(
                id=intent_id,
                teaching_role=str(record.get("pedagogical_role") or ""),
                choose_when=str(record.get("choose_when") or record.get("generation_guidance") or ""),
                not_when=str(record.get("not_when") or record.get("do_not_choose_when") or ""),
                status="permitted",
                exclusion_reason=None,
            )
        )

    version = _catalogue_version(intents_doc, objects_doc)
    payload = {
        "catalogue_version": version,
        "intents": [asdict(item) for item in rows],
    }
    return TeachingGuidanceProjection(
        intents=tuple(rows),
        catalogue_version=version,
        projection_hash=_hash_payload(payload),
    )


def project_form_guidance(
    *,
    permitted_object_ids: set[str] | None = None,
    intent_catalogue: Mapping[str, Any] | None = None,
    object_catalogue: Mapping[str, Any] | None = None,
) -> FormGuidanceProjection:
    intents_doc = intent_catalogue or get_intent_catalogue()
    objects_doc = object_catalogue or get_object_catalogue()
    intents = intents_doc.get("intents") or {}
    objects = objects_doc.get("objects") or {}
    # Empty set must fail closed (no catalogue widen). Only None means "all objects".
    if permitted_object_ids is None:
        allowed_objects = set(objects.keys()) - {"heading", "answer-key"}
    else:
        allowed_objects = set(permitted_object_ids) - {"heading", "answer-key"}

    by_intent: dict[str, tuple[str, ...]] = {}
    for intent_id, record in intents.items():
        if not isinstance(record, dict):
            continue
        valid = [
            object_id
            for object_id in record.get("valid_objects") or []
            if object_id in allowed_objects and object_id in objects
        ]
        by_intent[intent_id] = tuple(valid)

    rows: list[FormObjectGuidance] = []
    for object_id, record in sorted(objects.items()):
        if object_id not in allowed_objects or not isinstance(record, dict):
            continue
        capacity = record.get("capacity") or {}
        rows.append(
            FormObjectGuidance(
                id=object_id,
                compatible_intents=tuple(
                    intent_id
                    for intent_id, object_ids in by_intent.items()
                    if object_id in object_ids
                ),
                earns_its_place_when=str(
                    record.get("earns_its_place_when") or record.get("choose_when") or ""
                ),
                choose_when=str(record.get("choose_when") or ""),
                not_when=str(record.get("not_when") or record.get("reject_when") or ""),
                capacity_summary=json.dumps(capacity, sort_keys=True) if capacity else "",
                placement_restrictions=str(record.get("placement") or record.get("placement_restrictions") or ""),
            )
        )

    version = _catalogue_version(intents_doc, objects_doc)
    payload = {
        "catalogue_version": version,
        "objects": [asdict(item) for item in rows],
        "by_intent": {key: list(value) for key, value in by_intent.items()},
    }
    return FormGuidanceProjection(
        objects=tuple(rows),
        by_intent=by_intent,
        catalogue_version=version,
        projection_hash=_hash_payload(payload),
    )


def project_writer_contract(
    object_id: str,
    *,
    intent_catalogue: Mapping[str, Any] | None = None,
    object_catalogue: Mapping[str, Any] | None = None,
) -> WriterContractProjection:
    intents_doc = intent_catalogue or get_intent_catalogue()
    objects_doc = object_catalogue or get_object_catalogue()
    objects = objects_doc.get("objects") or {}
    record = objects.get(object_id)
    if not isinstance(record, dict):
        raise KeyError(f"unknown page object {object_id!r}")

    version = _catalogue_version(intents_doc, objects_doc)
    capacity = record.get("capacity") if isinstance(record.get("capacity"), dict) else {}
    schema = record.get("content_schema") if isinstance(record.get("content_schema"), dict) else {}
    validation = record.get("validation") or record.get("object_validation") or []
    failures = record.get("failure_examples") or []
    return WriterContractProjection(
        object_id=object_id,
        generation_guidance=str(record.get("generation_guidance") or ""),
        content_schema=dict(schema),
        capacity=dict(capacity),
        object_validation=tuple(str(item) for item in validation),
        failure_examples=tuple(str(item) for item in failures),
        catalogue_version=version,
    )


def assert_teaching_guidance_has_no_object_ids(
    projection: TeachingGuidanceProjection,
    *,
    object_ids: tuple[str, ...] | None = None,
) -> None:
    payload = projection.to_dict()
    serialized = json.dumps(payload, sort_keys=True)
    forbidden_keys = {"valid_objects", "content_schema", "capacity", "objects", "object"}
    found_keys = forbidden_keys.intersection(_all_keys(payload))
    if found_keys:
        raise AssertionError(
            f"teaching guidance contains object-bearing keys: {sorted(found_keys)}"
        )
    known = object_ids or PAGE_OBJECT_IDS
    # Hyphenated catalogue ids must never appear; bare English words are checked
    # only as exact JSON string values (not substrings inside prose).
    leaks: list[str] = []
    for object_id in known:
        if "-" in object_id and object_id in serialized:
            leaks.append(object_id)
            continue
        if f'"{object_id}"' in serialized:
            # Allow intent ids that happen to share words? Object ids as values only.
            # Teaching intent ids never equal page-object ids in current catalogues.
            if any(
                intent.id == object_id for intent in projection.intents
            ):
                continue
            leaks.append(object_id)
    if leaks:
        raise AssertionError(
            f"teaching guidance leaked page-object IDs: {sorted(set(leaks))}"
        )


def _all_keys(value: Any, acc: set[str] | None = None) -> set[str]:
    keys = acc if acc is not None else set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            _all_keys(child, keys)
    elif isinstance(value, list):
        for child in value:
            _all_keys(child, keys)
    return keys


def registered_page_object_ids() -> tuple[str, ...]:
    return tuple(PAGE_OBJECT_IDS)


# Objects the native Xplore writer registry can materialize.
_IMPLEMENTED_FORM_OBJECTS: frozenset[str] = frozenset(
    {
        "prose",
        "list",
        "table",
        "figure",
        "aside",
        "worked-example",
        "questions",
        "choices",
    }
)
_NEVER_SELECTABLE_OBJECTS: frozenset[str] = frozenset({"heading", "answer-key"})


def build_form_candidate_map(
    teaching_plan: Any,
    *,
    compatible_objects_by_intent: Mapping[str, Sequence[str]],
    approved_items: Sequence[Any],
    implemented_objects: set[str] | frozenset[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Per-block legal object set from a frozen snapshot compatibility map.

    Same map must feed the form prompt envelope and validate_form_plan.
    Live catalogue compatibility must not widen this set.
    """
    implemented = set(implemented_objects or _IMPLEMENTED_FORM_OBJECTS)
    implemented -= set(_NEVER_SELECTABLE_OBJECTS)

    from planning.approved_items import approved_item_kind

    approved_by_id = {
        str(getattr(item, "id", "") or ""): item for item in approved_items
    }
    candidates: dict[str, tuple[str, ...]] = {}
    for section in teaching_plan.sections:
        for block in section.blocks:
            frozen = {
                str(object_id)
                for object_id in compatible_objects_by_intent.get(block.intent, ())
                if object_id
            }
            legal = sorted(
                (frozen & implemented) - set(_NEVER_SELECTABLE_OBJECTS)
            )
            source_question_ids = tuple(getattr(block, "source_question_ids", ()) or ())
            # Assessment forms bind deterministically to teaching-owned items.
            # Once ownership is present, non-assessment objects are not legal:
            # form planning may choose representation, never discard item IDs.
            if not source_question_ids:
                legal = [
                    object_id
                    for object_id in legal
                    if object_id not in {"questions", "choices"}
                ]
            else:
                selected = [approved_by_id.get(str(item_id)) for item_id in source_question_ids]
                if any(item is None for item in selected):
                    legal = []
                else:
                    kinds = [approved_item_kind(item) for item in selected]
                    if len(kinds) == 1 and kinds[0] == "multiple_choice":
                        legal = [object_id for object_id in legal if object_id == "choices"]
                    elif 1 <= len(kinds) <= 6 and set(kinds) == {"open_response"}:
                        legal = [object_id for object_id in legal if object_id == "questions"]
                    else:
                        # Mixed sources, >6 open responses, and multiple MCQs
                        # are teaching-plan repair failures, not form choices.
                        legal = []
            candidates[block.id] = tuple(legal)
    return candidates

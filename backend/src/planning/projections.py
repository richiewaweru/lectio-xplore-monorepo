from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LessonProvenanceModel,
    PackItemModel,
    PathLessonModel,
    PathVersionModel,
    ResourceCompositionModel,
    TeachingPeriodLessonModel,
    TeachingPeriodModel,
    UnitGroupModel,
    UnitModel,
)
from generation.pdf_export.components.answers_v3 import build_diagnostic_answer_key_content
from planning.models import ResourceComposeRequest


TEMPLATE_VERSION = "resource-projection.v1"
ASSESSMENT_PROJECTIONS = {"quiz", "answer_key", "unit_exam"}
ROLE_FILTERS = {
    "homework": {"guided", "independent", "apply", "practice", "check"},
    "revision_sheet": {"organise", "explain", "contrast", "model", "close"},
}


class ProjectionUnavailable(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _document_hash(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _grade_band(grade_level: str) -> str:
    digits = "".join(character for character in grade_level if character.isdigit())
    grade = int(digits) if digits else 8
    return "primary" if grade <= 6 else "advanced" if grade >= 11 else "secondary"


def _ready_document(generation: GenerationModel) -> dict[str, Any] | None:
    document = generation.document_json
    if not isinstance(document, dict):
        return None
    document_status = str(document.get("status") or "")
    generation_status = str(generation.status or "")
    allowed = {"completed", "final_ready", "final_with_warnings", "ready"}
    return document if document_status in allowed or generation_status in allowed else None


def _section_roles(generation: GenerationModel) -> dict[str, str]:
    state = generation.chunked_state_json
    if not isinstance(state, dict):
        return {}
    plan = state.get("structural_plan")
    sections = plan.get("sections") if isinstance(plan, dict) else None
    if not isinstance(sections, list):
        return {}
    return {
        str(section.get("id")): str(section.get("role") or section.get("id"))
        for section in sections
        if isinstance(section, dict) and section.get("id")
    }


def _component_title(section: dict[str, Any], fallback: str) -> str:
    header = section.get("header")
    if isinstance(header, dict) and isinstance(header.get("title"), str):
        return header["title"]
    return fallback.replace("_", " ").replace("-", " ").title()


def _item_payload(item: PackItemModel) -> dict[str, Any]:
    return {
        "id": item.id,
        "card_id": item.card_id,
        "stem": item.stem,
        "options": deepcopy(item.options if isinstance(item.options, list) else []),
        "correct_key": item.correct_key,
    }


def _quiz_sections(
    *,
    items: list[dict[str, Any]],
    subject: str,
    grade_band: str,
) -> list[dict[str, Any]]:
    return [
        {
            "section_id": f"projected-question-{index:03d}",
            "template_id": "guided-concept-path",
            "card_id": item["card_id"],
            "header": {
                "title": "Projected assessment" if index == 1 else f"Question {index}",
                "subject": subject,
                "grade_band": grade_band,
            },
            "quiz": {
                "question": item["stem"],
                "quiz_type": "multiple-choice",
                "options": [
                    {
                        "text": str(option.get("text") or ""),
                        "correct": bool(option.get("correct")),
                        "explanation": (
                            "Correct."
                            if option.get("correct")
                            else "Review this idea with your teacher."
                        ),
                        "diagnoses": option.get("diagnoses"),
                    }
                    for option in item["options"]
                    if isinstance(option, dict)
                ],
                "feedback_correct": "Correct.",
                "feedback_incorrect": "Check the concept and try again.",
                "show_explanations": False,
            },
        }
        for index, item in enumerate(items, start=1)
    ]


def _answer_key(
    items: list[dict[str, Any]],
    cards: list[ConceptCardModel],
) -> dict[str, Any]:
    labels = {
        (card.id, str(misconception.get("id"))): str(
            misconception.get("description") or misconception.get("id")
        )
        for card in cards
        for misconception in (card.misconceptions or [])
        if isinstance(misconception, dict) and misconception.get("id")
    }
    return build_diagnostic_answer_key_content(items=items, misconception_labels=labels)


def _copy_component_section(component: dict[str, Any], index: int) -> dict[str, Any]:
    section = deepcopy(component["section"])
    section["section_id"] = f"projection-{index:03d}-{component['section_id']}"
    section["_projection_source"] = {
        "component_ref": component["ref"],
        "generation_id": component["generation_id"],
        "path_lesson_id": component["path_lesson_id"],
        "group_id": component["group_id"],
    }
    return section


def _revision_sections(
    lessons: list[PathLessonModel],
    components: list[dict[str, Any]],
    unit: UnitModel,
) -> list[dict[str, Any]]:
    grade_band = _grade_band(unit.grade_level)
    sections: list[dict[str, Any]] = []
    for lesson in lessons:
        lesson_components = [item for item in components if item["path_lesson_id"] == lesson.id]
        selected_fields: dict[str, Any] = {}
        for component in lesson_components:
            for field in ("definition", "definition_family", "key_fact", "comparison_grid", "pitfall", "pitfalls", "worked_example", "worked_examples"):
                if field in component["section"] and field not in selected_fields:
                    selected_fields[field] = deepcopy(component["section"][field])
        sections.append(
            {
                "section_id": f"revision-{lesson.id}",
                "template_id": "guided-concept-path",
                "card_id": lesson.concept_id,
                "header": {
                    "title": lesson.title,
                    "subject": unit.subject,
                    "grade_band": grade_band,
                    "objectives": [lesson.objective],
                },
                "summary": {
                    "heading": "What to remember",
                    "items": [
                        {"text": statement}
                        for statement in (lesson.must_establish or [lesson.objective])
                    ],
                    "closing": (
                        f"Keep outside scope: {', '.join(lesson.exclusions)}"
                        if lesson.exclusions
                        else None
                    ),
                },
                **selected_fields,
            }
        )
    return sections


def _flashcard_sections(
    lessons: list[PathLessonModel],
    cards_by_concept: dict[str, ConceptCardModel],
    unit: UnitModel,
) -> list[dict[str, Any]]:
    grade_band = _grade_band(unit.grade_level)
    sections: list[dict[str, Any]] = []
    for lesson in lessons:
        card = cards_by_concept.get(lesson.concept_id)
        corrections = [
            str(item.get("description") or "")
            for item in (card.misconceptions if card else [])
            if isinstance(item, dict) and item.get("description")
        ]
        sections.append(
            {
                "section_id": f"flashcard-{lesson.id}",
                "template_id": "guided-concept-path",
                "card_id": lesson.concept_id,
                "header": {
                    "title": lesson.title,
                    "subject": unit.subject,
                    "grade_band": grade_band,
                },
                "definition": {
                    "term": lesson.title,
                    "plain": lesson.objective,
                    "formal": "; ".join(lesson.must_establish or [lesson.objective]),
                    "related_terms": [],
                },
                **(
                    {
                        "callout": {
                            "variant": "warning",
                            "heading": "Correct the misconception",
                            "body": corrections[0],
                        }
                    }
                    if corrections
                    else {}
                ),
            }
        )
    return sections


async def _resolve_scope(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    request: ResourceComposeRequest,
) -> dict[str, Any]:
    lessons = list(
        await session.scalars(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id, PathLessonModel.skipped.is_(False))
            .order_by(PathLessonModel.position)
        )
    )
    lessons_by_id = {lesson.id: lesson for lesson in lessons}
    selected_ids = set(request.path_lesson_ids)
    periods = list(
        await session.scalars(
            select(TeachingPeriodModel)
            .where(TeachingPeriodModel.path_version_id == version.id)
            .order_by(TeachingPeriodModel.position)
        )
    )
    periods_by_id = {period.id: period for period in periods}
    unknown_periods = set(request.period_ids) - set(periods_by_id)
    if unknown_periods:
        raise ProjectionUnavailable(f"Unknown teaching periods: {', '.join(sorted(unknown_periods))}")
    if request.period_ids:
        links = list(
            await session.scalars(
                select(TeachingPeriodLessonModel).where(
                    TeachingPeriodLessonModel.teaching_period_id.in_(request.period_ids)
                )
            )
        )
        selected_ids.update(link.path_lesson_id for link in links)
    if not selected_ids:
        selected_ids.update(lessons_by_id)
    unknown_lessons = selected_ids - set(lessons_by_id)
    if unknown_lessons:
        raise ProjectionUnavailable(f"Unknown path lessons: {', '.join(sorted(unknown_lessons))}")
    selected_lessons = [lesson for lesson in lessons if lesson.id in selected_ids]
    if not selected_lessons:
        raise ProjectionUnavailable("Select at least one active path lesson")

    groups = list(
        await session.scalars(
            select(UnitGroupModel)
            .where(UnitGroupModel.unit_id == unit.id, UnitGroupModel.active.is_(True))
            .order_by(UnitGroupModel.position)
        )
    )
    groups_by_id = {group.id: group for group in groups}
    selected_group_ids = set(request.group_ids or groups_by_id)
    unknown_groups = selected_group_ids - set(groups_by_id)
    if unknown_groups:
        raise ProjectionUnavailable(f"Unknown unit groups: {', '.join(sorted(unknown_groups))}")
    selected_groups = [group for group in groups if group.id in selected_group_ids]
    return {
        "lessons": selected_lessons,
        "all_lessons": lessons,
        "groups": selected_groups,
        "all_groups": groups,
        "periods": periods,
    }


async def _collect_sources(
    session: AsyncSession,
    *,
    lessons: list[PathLessonModel],
    groups: list[UnitGroupModel],
) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    cards: list[ConceptCardModel] = []
    source_snapshots: list[dict[str, Any]] = []
    unavailable: list[str] = []
    seen_items: set[str] = set()
    for lesson in lessons:
        if not lesson.pack_id:
            unavailable.append(f"{lesson.title}: lesson is not prepared")
            continue
        coordinator = await session.get(GenerationModel, lesson.pack_id)
        provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
        if coordinator is None or provenance is None or provenance.invalidated_at is not None:
            unavailable.append(f"{lesson.title}: active preparation provenance is unavailable")
            continue
        if provenance.path_lesson_revision != lesson.revision or provenance.objective_hash != lesson.objective_hash:
            unavailable.append(f"{lesson.title}: preparation is stale")
            continue
        pack_id = coordinator.pack_id
        source_generations: list[tuple[UnitGroupModel | None, GenerationModel]] = []
        if groups:
            if not pack_id:
                unavailable.append(f"{lesson.title}: differentiated pack is unavailable")
                continue
            children = list(
                await session.scalars(
                    select(GenerationModel).where(GenerationModel.pack_id == pack_id)
                )
            )
            children_by_label = {child.pack_resource_label: child for child in children}
            for group in groups:
                child = children_by_label.get(group.label)
                if child is None:
                    unavailable.append(f"{lesson.title} · {group.label}: variant is unavailable")
                else:
                    source_generations.append((group, child))
        else:
            source_generations.append((None, coordinator))

        for group, generation in source_generations:
            document = _ready_document(generation)
            label = group.label if group else "Canonical"
            if document is None:
                unavailable.append(f"{lesson.title} · {label}: approved document is unavailable")
                continue
            roles = _section_roles(generation)
            generation_components: list[str] = []
            for index, raw in enumerate(document.get("sections", [])):
                if not isinstance(raw, dict):
                    continue
                section_id = str(raw.get("section_id") or f"section-{index + 1}")
                ref = f"{generation.id}:{section_id}"
                generation_components.append(ref)
                components.append(
                    {
                        "ref": ref,
                        "generation_id": generation.id,
                        "path_lesson_id": lesson.id,
                        "lesson_title": lesson.title,
                        "group_id": group.id if group else None,
                        "group_label": label,
                        "section_id": section_id,
                        "role": roles.get(section_id, section_id),
                        "title": _component_title(raw, section_id),
                        "section": raw,
                    }
                )
            source_snapshots.append(
                {
                    "source_pack_id": pack_id or coordinator.id,
                    "coordinator_generation_id": coordinator.id,
                    "source_generation_id": generation.id,
                    "source_document_hash": _document_hash(document),
                    "source_document_version": document.get("doc_version"),
                    "path_lesson_id": lesson.id,
                    "path_lesson_revision": lesson.revision,
                    "objective_hash": lesson.objective_hash,
                    "group_id": group.id if group else None,
                    "group_label": label,
                    "component_refs": generation_components,
                }
            )
        item_pack_id = pack_id or coordinator.id
        pack_items = list(
            await session.scalars(
                select(PackItemModel)
                .where(PackItemModel.pack_id == item_pack_id, PackItemModel.stale.is_(False))
                .order_by(PackItemModel.card_id, PackItemModel.id)
            )
        )
        for item in pack_items:
            if item.id not in seen_items:
                items.append(_item_payload(item))
                seen_items.add(item.id)
        cards.extend(
            list(
                await session.scalars(
                    select(ConceptCardModel).where(ConceptCardModel.pack_id == item_pack_id)
                )
            )
        )
    return {
        "components": components,
        "items": items,
        "cards": cards,
        "source_snapshots": source_snapshots,
        "unavailable": unavailable,
    }


def _compose_document(
    *,
    composition_id: str,
    unit: UnitModel,
    projection: str,
    lessons: list[PathLessonModel],
    components: list[dict[str, Any]],
    items: list[dict[str, Any]],
    cards: list[ConceptCardModel],
    include_keys: bool,
) -> dict[str, Any]:
    grade_band = _grade_band(unit.grade_level)
    if projection in {"quiz", "unit_exam"}:
        sections = _quiz_sections(items=items, subject=unit.subject, grade_band=grade_band)
    elif projection == "answer_key":
        sections = []
    elif projection == "revision_sheet":
        sections = _revision_sections(lessons, components, unit)
    elif projection == "flashcards":
        cards_by_concept = {
            str(card.canonical_concept_id): card
            for card in cards
            if card.canonical_concept_id
        }
        sections = _flashcard_sections(lessons, cards_by_concept, unit)
    else:
        sections = [
            _copy_component_section(component, index)
            for index, component in enumerate(components, start=1)
        ]
    document: dict[str, Any] = {
        "kind": "resource_projection",
        "generation_id": composition_id,
        "template_id": "guided-concept-path",
        "subject": unit.subject,
        "title": f"{unit.title} · {projection.replace('_', ' ').title()}",
        "status": "final_ready",
        "projection": projection,
        "projection_template_version": TEMPLATE_VERSION,
        "sections": sections,
    }
    if items and (include_keys or projection == "answer_key"):
        document["answer_key"] = _answer_key(items, cards)
    if projection == "unit_exam":
        covered_cards = sorted({str(item["card_id"]) for item in items})
        document["coverage_report"] = {
            "selected_concepts": len(lessons),
            "covered_concept_cards": len(covered_cards),
            "item_count": len(items),
            "card_ids": covered_cards,
        }
    return document


async def build_composition_payload(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    request: ResourceComposeRequest,
    persist: bool,
) -> dict[str, Any]:
    if request.path_version_id != version.id or request.path_revision != version.revision:
        raise ProjectionUnavailable("The active path changed; refresh resource selections")
    scope = await _resolve_scope(session, unit=unit, version=version, request=request)
    lessons: list[PathLessonModel] = scope["lessons"]
    sources = await _collect_sources(session, lessons=lessons, groups=scope["groups"])
    component_refs = {component["ref"] for component in sources["components"]}
    unknown_components = set(request.component_refs) - component_refs
    if unknown_components:
        raise ProjectionUnavailable("Selected components are not owned by the approved source revisions")
    item_ids = {item["id"] for item in sources["items"]}
    unknown_items = set(request.item_ids) - item_ids
    if unknown_items:
        raise ProjectionUnavailable("Selected items are not owned by the approved source packs")

    components = [
        component
        for component in sources["components"]
        if not request.component_refs or component["ref"] in request.component_refs
    ]
    if not request.component_refs and request.projection in ROLE_FILTERS:
        roles = set(ROLE_FILTERS[request.projection])
        if request.projection == "homework" and request.include_support_notes:
            roles.update({"explain", "model"})
        components = [component for component in components if component["role"] in roles]
    items = [
        item
        for item in sources["items"]
        if not request.item_ids or item["id"] in request.item_ids
    ]
    reasons = list(sources["unavailable"])
    if request.projection in ASSESSMENT_PROJECTIONS and not items:
        reasons.append("No approved, non-stale shared diagnostic items are available")
    if request.projection in {"full_lesson", "homework"} and not components:
        reasons.append("No approved components match this projection")
    status = "projection_unavailable" if reasons else "ready"
    composition_id = str(uuid.uuid4()) if persist else "preview"
    document = _compose_document(
        composition_id=composition_id,
        unit=unit,
        projection=request.projection,
        lessons=lessons,
        components=components,
        items=items,
        cards=sources["cards"],
        include_keys=request.include_keys,
    )
    payload = {
        "id": composition_id if persist else None,
        "unit_id": unit.id,
        "path_version_id": version.id,
        "path_version": version.version,
        "path_revision": version.revision,
        "projection": request.projection,
        "status": status,
        "can_create": not reasons,
        "unavailable_reasons": reasons,
        "lesson_ids": [lesson.id for lesson in lessons],
        "period_ids": request.period_ids,
        "group_ids": [group.id for group in scope["groups"]],
        "selected_component_refs": [component["ref"] for component in components],
        "selected_item_ids": [item["id"] for item in items],
        "template_version": TEMPLATE_VERSION,
        "source_snapshots": sources["source_snapshots"],
        "available_lessons": [
            {"id": lesson.id, "title": lesson.title, "position": lesson.position}
            for lesson in scope["all_lessons"]
        ],
        "available_periods": [
            {"id": period.id, "title": period.title, "position": period.position}
            for period in scope["periods"]
        ],
        "available_groups": [
            {"id": group.id, "label": group.label, "profile": group.profile}
            for group in scope["all_groups"]
        ],
        "available_components": [
            {key: component[key] for key in ("ref", "path_lesson_id", "lesson_title", "group_id", "group_label", "section_id", "role", "title")}
            for component in sources["components"]
        ],
        "available_items": [
            {"id": item["id"], "card_id": item["card_id"], "stem": item["stem"]}
            for item in sources["items"]
        ],
        "document": document,
    }
    if persist:
        if reasons:
            raise ProjectionUnavailable("; ".join(reasons))
        session.add(
            ResourceCompositionModel(
                id=composition_id,
                unit_id=unit.id,
                owner_id=unit.owner_id,
                path_version_id=version.id,
                path_version=version.version,
                path_revision=version.revision,
                projection=request.projection,
                status="ready",
                lesson_ids=payload["lesson_ids"],
                period_ids=request.period_ids,
                group_ids=payload["group_ids"],
                selected_component_refs=payload["selected_component_refs"],
                selected_item_ids=payload["selected_item_ids"],
                include_keys=request.include_keys,
                template_version=TEMPLATE_VERSION,
                source_snapshots=sources["source_snapshots"],
                document_json=document,
                created_at=_utcnow(),
            )
        )
        await session.flush()
    return payload


def composition_payload(model: ResourceCompositionModel) -> dict[str, Any]:
    return {
        "id": model.id,
        "unit_id": model.unit_id,
        "path_version_id": model.path_version_id,
        "path_version": model.path_version,
        "path_revision": model.path_revision,
        "projection": model.projection,
        "status": model.status,
        "lesson_ids": model.lesson_ids,
        "period_ids": model.period_ids,
        "group_ids": model.group_ids,
        "selected_component_refs": model.selected_component_refs,
        "selected_item_ids": model.selected_item_ids,
        "include_keys": model.include_keys,
        "template_version": model.template_version,
        "source_snapshots": model.source_snapshots,
        "document": model.document_json,
        "created_at": model.created_at.isoformat(),
    }

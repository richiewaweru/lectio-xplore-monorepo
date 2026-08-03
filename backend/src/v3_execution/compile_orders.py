from __future__ import annotations

import re
import logging

from v3_blueprint.models import ProductionBlueprint, QuestionPlanItem
from v3_blueprint.compiler import BlueprintCompiler

from v3_execution.component_aliases import canonical_component_id
from contracts.lectio import _EXTERNAL_FIELDS, get_section_field_for_component
from v3_execution.models import (
    AnswerKeyExecutorWorkOrder,
    AnswerKeyPlanSpec,
    CompiledWorkOrders,
    LearnerProfileSpec,
    QuestionWriterWorkOrder,
    RegisterSpec,
    SectionWriterWorkOrder,
    SourceOfTruthEntry,
    VisualDependency,
    VisualFrameSpec,
    VisualGeneratorWorkOrder,
    VisualPlanItem,
    WriterQuestion,
    WriterSection,
    WriterSectionComponent,
)
from generation.v3_studio.signal_map import derive_support_adaptations

logger = logging.getLogger(__name__)

COMPONENT_TO_VISUAL_MODE: dict[str, str] = {
    "diagram-block": "diagram",
    "diagram-series": "diagram_series",
    "diagram-compare": "diagram_compare",
    "timeline-block": "diagram",
    "worked-example-card": "diagram",
}


def _norm_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _has_long_caption_overlap(item: str, reference_texts: list[str]) -> bool:
    item_words = _norm_words(item)
    if len(item_words) < 6:
        return False
    item_norm = " ".join(item_words)
    for reference in reference_texts:
        ref_words = _norm_words(reference)
        if len(ref_words) < 6:
            continue
        ref_norm = " ".join(ref_words)
        if item_norm in ref_norm or ref_norm in item_norm:
            return True
    return False


def _drop_caption_like_must_show(
    items: list[str],
    *,
    reference_texts: list[str],
    visual_id: str,
) -> list[str]:
    kept: list[str] = []
    for item in items:
        if _has_long_caption_overlap(item, reference_texts):
            logger.warning(
                "Dropped caption-like must_show item for visual_id=%s item=%r",
                visual_id,
                item[:160],
            )
            continue
        kept.append(item)
    return kept


def _sanitize_visual_constraints(
    must_show: list[str],
    must_not_show: list[str],
    *,
    visual_id: str,
) -> tuple[list[str], list[str]]:
    """Move negative requirements out of the positive must-show list."""
    positive: list[str] = []
    exclusions = list(must_not_show)
    for item in must_show:
        cleaned = item.strip()
        match = re.match(r"^(no|without|never|avoid)\b\s*(.*)$", cleaned, re.IGNORECASE)
        if not match:
            positive.append(item)
            continue
        migrated = match.group(2).strip() or cleaned
        exclusions.append(migrated)
        logger.warning(
            "Moved negative must_show item to must_not_show for visual_id=%s item=%r",
            visual_id,
            item[:160],
        )
    return positive, exclusions


def _truth_from_blueprint(blueprint: ProductionBlueprint) -> list[SourceOfTruthEntry]:
    entries: list[SourceOfTruthEntry] = []
    for line in blueprint.prior_knowledge:
        entries.append(SourceOfTruthEntry(key=f"prior:{line}", text=line))
    if blueprint.repair_focus is not None:
        entries.append(
            SourceOfTruthEntry(
                key="fault_line",
                text=blueprint.repair_focus.fault_line,
            )
        )
        for w in blueprint.repair_focus.what_not_to_teach:
            entries.append(SourceOfTruthEntry(key=f"avoid:{w}", text=w))
    return entries


def _register_from_blueprint(blueprint: ProductionBlueprint) -> RegisterSpec:
    return RegisterSpec(
        level=blueprint.voice.register_name,
        tone=blueprint.voice.tone or "instructional_clear",
    )


def _component_cards_for_components(component_ids: list[str]) -> dict[str, dict]:
    """
    Fetch Lectio component cards for the given component IDs from
    lectio-content-contract.json. Raises ValueError for any unknown component.
    """
    from contracts.lectio import get_component_card

    cards: dict[str, dict] = {}
    for cid in component_ids:
        card = get_component_card(cid)
        if card is None:
            raise ValueError(
                f"Unknown Lectio component: '{cid}'. "
                "The component is not present in lectio-content-contract.json. "
                "Check that Lectio is at 0.4.2 and contracts are up to date: "
                "uv run python tools/update_lectio_contracts.py"
            )
        cards[cid] = card
    return cards


def resolve_visual_dependency(
    *,
    component_id: str,
    section_role: str,
    visual_job: str,
    section_id: str,
    question_plan: list[QuestionPlanItem],
    source_question_ids: list[str],
) -> VisualDependency:
    if source_question_ids:
        return "question_text"

    has_diagram_questions = any(
        getattr(q, "diagram_required", False)
        for q in question_plan
        if getattr(q, "section_id", None) == section_id
    )
    if has_diagram_questions:
        return "question_text"

    job = visual_job.lower()
    if "question" in job or "practice" in job:
        return "question_text"
    if any(kw in job for kw in ("summarize", "recap", "section explanation", "generated")):
        return "section_text"
    if component_id == "worked-example-card":
        return "section_text"
    if section_role in ("model", "explain") and any(
        kw in job for kw in ("after", "summary", "walkthrough")
    ):
        return "section_text"
    return "blueprint_only"


def _extract_series_frames_legacy(
    blueprint: ProductionBlueprint,
    section_id: str,
    fallback_description: str,
) -> list[VisualFrameSpec]:
    """Derive per-frame specs from diagram-series content intent markers."""
    for sec in blueprint.sections:
        if sec.section_id != section_id:
            continue
        for comp in sec.components:
            if canonical_component_id(comp.component) != "diagram-series":
                continue
            panels = re.split(
                r"(?:Panel|Step|Frame)\s*\d+\s*[\-:\u2014]",
                comp.content_intent,
                flags=re.IGNORECASE,
            )
            panel_descriptions = [part.strip() for part in panels[1:] if part.strip()]
            if len(panel_descriptions) >= 2:
                return [VisualFrameSpec(description=desc) for desc in panel_descriptions]
    return [VisualFrameSpec(description=fallback_description)]


def _resolve_frames(vis, blueprint: ProductionBlueprint) -> list[VisualFrameSpec]:
    if vis.frames and len(vis.frames) >= 2:
        return [
            VisualFrameSpec(
                description=frame.description,
                must_show=frame.must_show,
            )
            for frame in vis.frames
        ]
    return _extract_series_frames_legacy(blueprint, vis.section_id, vis.strategy)


def _section_role(blueprint: ProductionBlueprint, section_id: str) -> str:
    for sec in blueprint.sections:
        if sec.section_id == section_id:
            return sec.role
    return "unknown"


def compile_execution_bundle(
    blueprint: ProductionBlueprint,
    *,
    generation_id: str,
    blueprint_id: str,
    template_id: str,
) -> CompiledWorkOrders:
    """Map foundation blueprint + Lectio contracts → proposal-2 execution work orders."""
    BlueprintCompiler().compile_all(blueprint)  # validate blueprint shape early
    register = _register_from_blueprint(blueprint)
    truth = _truth_from_blueprint(blueprint)
    consistency_rules = [
        "Do not change anchor facts or fixed units.",
        "Do not add or remove planned components or questions.",
    ]

    section_orders: list[SectionWriterWorkOrder] = []
    for sec in blueprint.sections:
        writer_comps: list[WriterSectionComponent] = []
        for c in sec.components:
            canonical = canonical_component_id(c.component)
            field = get_section_field_for_component(canonical)
            if field in _EXTERNAL_FIELDS:
                continue
            writer_comps.append(
                WriterSectionComponent(
                    component_id=canonical,
                    teacher_label=c.component.replace("_", " ").title(),
                    content_intent=c.content_intent,
                )
            )
        if not writer_comps:
            learning_intent = sec.title
        else:
            learning_intent = "; ".join(c.content_intent for c in writer_comps) or sec.title
        wo = SectionWriterWorkOrder(
            work_order_id=f"sec-{sec.section_id}",
            section=WriterSection(
                id=sec.section_id,
                title=sec.title,
                learning_intent=learning_intent,
                role=sec.role,
                transition_note=sec.transition_note,
                card_id=sec.card_id,
                constraints=[f"role:{sec.role}"],
                register_notes=[],
                components=writer_comps,
            ),
            register=register,
            learner_profile=LearnerProfileSpec(),
            support_adaptations=derive_support_adaptations(blueprint),
            source_of_truth=truth,
            consistency_rules=consistency_rules,
            component_cards=_component_cards_for_components(
                [c.component_id for c in writer_comps],
            ),
            template_id=template_id,
        )
        section_orders.append(wo)

    question_orders: list[QuestionWriterWorkOrder] = []
    by_section: dict[str, list[QuestionPlanItem]] = {}
    for q in blueprint.question_plan:
        by_section.setdefault(q.section_id, []).append(q)
    for sec_id, items in by_section.items():
        qs = [
            WriterQuestion(
                id=item.question_id,
                difficulty="extension" if item.temperature == "transfer" else item.temperature,
                diagram_required=item.diagram_required,
                expected_answer=item.expected_answer,
                uses_anchor_id=None,
                skill_target="lesson_objective",
                purpose="practice",
            )
            for item in items
        ]
        question_orders.append(
            QuestionWriterWorkOrder(
                work_order_id=f"q-{sec_id}",
                section_id=sec_id,
                questions=qs,
                source_of_truth=truth,
                register=register,
                consistency_rules=consistency_rules,
            )
        )

    visual_orders: list[VisualGeneratorWorkOrder] = []
    for idx, vis in enumerate(blueprint.visual_strategy.visuals):
        mode = COMPONENT_TO_VISUAL_MODE.get(vis.component_id, "diagram")
        frames: list[VisualFrameSpec] = []
        if mode == "diagram_series":
            frames = _resolve_frames(vis, blueprint)
            if len(frames) < 2:
                mode = "diagram"
                frames = []

        dependency = resolve_visual_dependency(
            component_id=vis.component_id,
            section_role=_section_role(blueprint, vis.section_id),
            visual_job=vis.visual_job,
            section_id=vis.section_id,
            question_plan=blueprint.question_plan,
            source_question_ids=vis.source_question_ids,
        )
        visual_id = f"vis-{vis.section_id}-{idx}"
        caption_references = [vis.subject, vis.visual_job, vis.strategy]
        must_show = _drop_caption_like_must_show(
            vis.must_show,
            reference_texts=caption_references,
            visual_id=visual_id,
        )
        must_show, must_not_show = _sanitize_visual_constraints(
            must_show,
            vis.must_not_show,
            visual_id=visual_id,
        )
        plan = VisualPlanItem(
            id=visual_id,
            attaches_to=vis.section_id,
            component_id=vis.component_id,
            mode=mode,
            visual_style=vis.visual_style,
            purpose=vis.subject,
            must_show=must_show,
            must_not_show=must_not_show,
            frames=frames,
        )
        visual_orders.append(
            VisualGeneratorWorkOrder(
                work_order_id=visual_id,
                resource_type=blueprint.lesson.resource_type,
                dependency=dependency,
                visual=plan,
                source_of_truth=truth,
            )
        )

    mapped_style = _map_answer_key_style(blueprint.answer_key.style)
    aq_questions = [
        WriterQuestion(
            id=item.question_id,
            difficulty="extension" if item.temperature == "transfer" else item.temperature,
            diagram_required=item.diagram_required,
            expected_answer=item.expected_answer,
        )
        for item in blueprint.question_plan
    ]
    answer_key_order = AnswerKeyExecutorWorkOrder(
        work_order_id="answer-key-main",
        questions=aq_questions,
        answer_key_plan=AnswerKeyPlanSpec(
            style=mapped_style,
            include_question_ids=[q.id for q in aq_questions],
        ),
        source_of_truth=truth,
    )

    return CompiledWorkOrders(
        generation_id=generation_id,
        blueprint_id=blueprint_id,
        template_id=template_id,
        section_orders=section_orders,
        question_orders=question_orders,
        visual_orders=visual_orders,
        answer_key_order=answer_key_order,
    )


def _map_answer_key_style(raw: str) -> str:
    lowered = raw.strip().lower().replace(" ", "_")
    if lowered in {"full_working"}:
        return "full_working"
    if lowered in {"answers_only"}:
        return "answers_only"
    if lowered in {"brief_explanations", "explanation_focused"}:
        return "brief_explanations"
    return "brief_explanations"


__all__ = ["compile_execution_bundle"]

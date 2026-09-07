"""Component-aware Lectio content assemblers and production coverage strategies.

Strategies are a small lane+component dispatch map — not a second legality registry.
Legality still comes from lesson.yaml + candidate resolver + Lectio cards.
"""

from __future__ import annotations

from typing import Any, Callable, get_args

from contracts.section_content import ReflectionType
from generation.component_lectio.errors import (
    AnswerKeyMappingError,
    UnsupportedProductionComponent,
)
from v3_blueprint.planning.work_orders import ExactWorkOrder
from v3_execution.models import GeneratedQuestionBlock, GeneratedVisualBlock, WriterQuestion

Assembler = Callable[..., dict[str, Any]]

ITEM_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "practice-stack",
        "quiz-check",
        "short-answer",
        "fill-in-blank",
        "reflection-prompt",
        "student-textbox",
    }
)

VISUAL_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "diagram-block",
        "diagram-compare",
        "diagram-series",
    }
)

CONTENT_COMPONENT_IDS: frozenset[str] = frozenset(
    {
        "section-header",
        "hook-hero",
        "prerequisite-strip",
        "explanation-block",
        "callout-block",
        "what-next-bridge",
        "section-divider",
        "definition-card",
        "definition-family",
        "glossary-rail",
        "insight-strip",
        "key-fact",
        "comparison-grid",
        "worked-example-card",
        "process-steps",
        "pitfall-alert",
        "summary-block",
    }
)

_REFLECTION_TYPES = "|".join(get_args(ReflectionType))


SCHEMA_SUMMARIES: dict[str, str] = {
    "practice-stack": (
        "PracticeContent: {problems:[{difficulty, question, hints:[{level,text}], "
        "solution?:{approach,answer,worked?}}], hints_visible_default?, solutions_available?, label?}"
    ),
    "quiz-check": (
        "QuizContent: {question, quiz_type?, options:[{text,correct,explanation,diagnoses?}], "
        "feedback_correct, feedback_incorrect, show_explanations?}"
    ),
    "short-answer": "ShortAnswerContent: {question, marks?, lines?, mark_scheme?}",
    "fill-in-blank": (
        "FillInBlankContent: {instruction?, segments:[{text,is_blank,answer?}], word_bank?}"
    ),
    "reflection-prompt": (
        f"ReflectionContent: {{prompt, type({_REFLECTION_TYPES}), "
        "space?, sentence_stem?, time_minutes?, pair_instruction?}"
    ),
    "student-textbox": "StudentTextboxContent: {prompt, lines?, label?}",
}


def _envelope(order: ExactWorkOrder, content: dict[str, Any], **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "content": content,
        "component_id": order.locked_component_id,
        "block_id": order.block_id,
        "work_order_id": order.work_order_id,
        "lane": order.lane,
        "section_field": order.section_field,
    }
    payload.update(extra)
    return payload


def assemble_content_payload(
    order: ExactWorkOrder, content: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    """Content lane: executor already emits Lectio field content in block.data."""
    return _envelope(order, content, **extra)


def _question_refs_from_practice(content: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    problems = content.get("problems") if isinstance(content.get("problems"), list) else []
    for idx, problem in enumerate(problems, start=1):
        if not isinstance(problem, dict):
            continue
        solution = problem.get("solution") if isinstance(problem.get("solution"), dict) else {}
        refs.append(
            {
                "id": f"p{idx}",
                "question": str(problem.get("question") or ""),
                "expected_answer": str(solution.get("answer") or ""),
                "difficulty": str(problem.get("difficulty") or "medium"),
            }
        )
    return refs


def _question_refs_from_quiz(content: dict[str, Any]) -> list[dict[str, Any]]:
    correct = ""
    options = content.get("options") if isinstance(content.get("options"), list) else []
    for option in options:
        if isinstance(option, dict) and option.get("correct") is True:
            correct = str(option.get("text") or "")
            break
    return [
        {
            "id": "q1",
            "question": str(content.get("question") or ""),
            "expected_answer": correct,
            "difficulty": "core",
        }
    ]


def _question_refs_from_short_answer(content: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "q1",
            "question": str(content.get("question") or ""),
            "expected_answer": str(content.get("mark_scheme") or ""),
            "difficulty": "core",
        }
    ]


def _question_refs_from_fill_in_blank(content: dict[str, Any]) -> list[dict[str, Any]]:
    segments = content.get("segments") if isinstance(content.get("segments"), list) else []
    answers = [
        str(seg.get("answer") or "")
        for seg in segments
        if isinstance(seg, dict) and seg.get("is_blank")
    ]
    instruction = str(content.get("instruction") or "Fill in the blanks")
    return [
        {
            "id": "q1",
            "question": instruction,
            "expected_answer": " / ".join(a for a in answers if a),
            "difficulty": "core",
        }
    ]


def _question_refs_from_promptish(
    content: dict[str, Any], *, key: str = "prompt"
) -> list[dict[str, Any]]:
    return [
        {
            "id": "q1",
            "question": str(content.get(key) or ""),
            "expected_answer": "",
            "difficulty": "core",
        }
    ]


def extract_question_refs(component_id: str, content: dict[str, Any]) -> list[dict[str, Any]]:
    if component_id == "practice-stack":
        return _question_refs_from_practice(content)
    if component_id == "quiz-check":
        return _question_refs_from_quiz(content)
    if component_id == "short-answer":
        return _question_refs_from_short_answer(content)
    if component_id == "fill-in-blank":
        return _question_refs_from_fill_in_blank(content)
    if component_id in {"reflection-prompt", "student-textbox"}:
        return _question_refs_from_promptish(content, key="prompt")
    return []


def assemble_items_content(
    order: ExactWorkOrder,
    blocks: list[GeneratedQuestionBlock],
) -> dict[str, Any]:
    """Convert question-writer output into exact Lectio item-component content."""
    component_id = order.locked_component_id
    if component_id not in ITEM_COMPONENT_IDS:
        raise UnsupportedProductionComponent(f"No items payload strategy for {component_id}")
    if not blocks:
        raise ValueError(f"items executor returned no blocks for {order.block_id}")

    # Component-aware path stores the full Lectio object on the first block.data
    primary = blocks[0]
    content = dict(primary.data) if isinstance(primary.data, dict) else {}

    # Reject legacy generic wrappers early (exact validator will also catch).
    if set(content.keys()) == {"items"} or (
        "items" in content and "problems" not in content and component_id == "practice-stack"
    ):
        raise ValueError(f"Generic items wrapper is not valid Lectio content for {component_id}")

    refs = extract_question_refs(component_id, content)
    if not refs and primary.expected_answer:
        refs = [
            {
                "id": primary.question_id,
                "question": str(content.get("question") or content.get("prompt") or ""),
                "expected_answer": primary.expected_answer,
                "difficulty": primary.difficulty,
            }
        ]
    return _envelope(order, content, question_refs=refs)


def assemble_visual_content(
    order: ExactWorkOrder,
    blocks: list[GeneratedVisualBlock],
) -> dict[str, Any]:
    """Map generated visual frames into the exact selected Lectio visual schema."""
    component_id = order.locked_component_id
    if not blocks:
        raise ValueError("visual executor returned no blocks")

    for block in blocks:
        if block.component_id and block.component_id != order.locked_component_id:
            from generation.component_lectio.errors import WorkOrderIdentityError

            raise WorkOrderIdentityError(
                f"Visual writer changed component_id from '{order.locked_component_id}' "
                f"to '{block.component_id}'"
            )
        if block.status in {"failed", "omitted_quality"}:
            raise ValueError(
                f"visual executor returned unusable status '{block.status}' for {order.block_id}"
            )

    def usable_source(block: GeneratedVisualBlock) -> bool:
        return bool(
            (isinstance(block.image_url, str) and block.image_url.strip())
            or (isinstance(block.html_content, str) and block.html_content.strip())
        )

    flagged = [block for block in blocks if block.status == "flagged_quality"]
    quality_metadata: dict[str, Any] = {}
    if flagged:
        reasons = [reason for block in flagged for reason in block.qc_reasons]
        correction_hints = [
            block.qc_correction_hint.strip()
            for block in flagged
            if block.qc_correction_hint and block.qc_correction_hint.strip()
        ]
        quality_metadata["visual_quality"] = {
            "status": "flagged_quality",
            "reasons": list(dict.fromkeys(reasons)),
            "correction_hint": "\n".join(dict.fromkeys(correction_hints)) or None,
        }

    if component_id == "diagram-block":
        block = blocks[0]
        if not usable_source(block):
            raise ValueError("diagram-block missing usable visual source")
        content = {
            "caption": block.caption or order.purpose or "Diagram",
            "alt_text": block.alt_text or block.caption or order.purpose or "Diagram",
        }
        if block.image_url:
            content["image_url"] = block.image_url
        if block.html_content:
            content["svg_content"] = block.html_content
        return _envelope(order, content, **quality_metadata)

    if component_id == "diagram-compare":
        if len(blocks) < 2:
            raise ValueError(
                "diagram-compare requires before/after visual sources; "
                "generic single-image output is insufficient"
            )
        before, after = blocks[0], blocks[1]
        if not usable_source(before) or not usable_source(after):
            raise ValueError("diagram-compare missing before/after visual source")
        content: dict[str, Any] = {
            "before_label": "Before",
            "after_label": "After",
            "caption": before.caption or after.caption or order.purpose or "Compare",
            "alt_text": before.alt_text or after.alt_text or order.purpose or "Compare",
        }
        if before.image_url:
            content["before_image_url"] = before.image_url
        if after.image_url:
            content["after_image_url"] = after.image_url
        if before.html_content:
            content["before_svg"] = before.html_content
        if after.html_content:
            content["after_svg"] = after.html_content
        return _envelope(order, content, **quality_metadata)

    if component_id == "diagram-series":
        if len(blocks) < 2:
            raise ValueError(
                "diagram-series requires diagrams[]; generic single-image output is insufficient"
            )
        diagrams = []
        for idx, block in enumerate(blocks, start=1):
            if not usable_source(block):
                raise ValueError(f"diagram-series frame {idx} missing usable visual source")
            step: dict[str, Any] = {
                "step_label": f"Step {idx}",
                "caption": block.caption or f"Step {idx}",
            }
            if block.image_url:
                step["image_url"] = block.image_url
            if block.html_content:
                step["svg_content"] = block.html_content
            diagrams.append(step)
        content = {
            "title": order.purpose or "Diagram series",
            "diagrams": diagrams,
        }
        return _envelope(order, content, **quality_metadata)

    raise UnsupportedProductionComponent(f"No visual payload strategy for {component_id}")


def assemble_answer_key_content(
    order: ExactWorkOrder,
    *,
    question_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministically map approved question source data to Lectio AnswerKeyContent."""
    if order.locked_component_id != "answer-key" and order.lane != "answer_key":
        # Still allow when section uses answer-key component id.
        pass
    entries: list[dict[str, Any]] = []
    for idx, ref in enumerate(question_refs, start=1):
        if not isinstance(ref, dict):
            continue
        question = str(ref.get("question") or "").strip()
        correct = str(ref.get("expected_answer") or ref.get("correct_answer") or "").strip()
        if not question:
            raise AnswerKeyMappingError(f"answer-key mapping missing question text for entry {idx}")
        if not correct:
            raise AnswerKeyMappingError(
                f"answer-key mapping missing correct_answer for entry {idx}"
            )
        entry: dict[str, Any] = {
            "question_number": float(idx),
            "question": question,
            "correct_answer": correct,
        }
        if ref.get("correct_key"):
            entry["correct_key"] = str(ref["correct_key"])
        if isinstance(ref.get("diagnostics"), list):
            entry["diagnostics"] = ref["diagnostics"]
        entries.append(entry)
    if not entries:
        raise AnswerKeyMappingError("answer-key mapping requires at least one question_ref")
    return _envelope(order, {"entries": entries})


def questions_from_refs(refs: list[dict[str, Any]]) -> list[WriterQuestion]:
    questions: list[WriterQuestion] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        qid = str(ref.get("id") or "")
        if not qid:
            continue
        questions.append(
            WriterQuestion(
                id=qid,
                difficulty=str(ref.get("difficulty") or "core"),
                expected_answer=str(ref.get("expected_answer") or ""),
                purpose="practice",
            )
        )
    return questions


def question_refs_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    refs = payload.get("question_refs")
    if isinstance(refs, list):
        return [item for item in refs if isinstance(item, dict)]
    return []


# --- Coverage: lane + component_id → strategy name (not a legality registry)

PAYLOAD_STRATEGIES: dict[tuple[str, str], str] = {}

for _cid in CONTENT_COMPONENT_IDS:
    PAYLOAD_STRATEGIES[("content", _cid)] = "content_section_writer"
for _cid in ITEM_COMPONENT_IDS:
    PAYLOAD_STRATEGIES[("items", _cid)] = "items_component_aware"
for _cid in VISUAL_COMPONENT_IDS:
    PAYLOAD_STRATEGIES[("visual", _cid)] = "visual_component_aware"
PAYLOAD_STRATEGIES[("answer_key", "answer-key")] = "answer_key_deterministic"

# Exact-contract test markers referenced by the coverage audit
EXACT_CONTRACT_TEST_MARKERS: dict[str, str] = {
    "practice-stack": "test_gate_c_valid_practice_stack_passes",
    "quiz-check": "test_gate_d_quiz_check_repair_feedback",
    "short-answer": "test_gate_e_short_answer",
    "fill-in-blank": "test_gate_f_fill_in_blank",
    "reflection-prompt": "test_gate_g_reflection_and_student_textbox",
    "student-textbox": "test_gate_g_reflection_and_student_textbox",
    "answer-key": "test_gate_h_answer_key_deterministic_mapping",
    "diagram-block": "test_gate_i_diagram_block",
    "diagram-compare": "test_gate_j_diagram_compare",
    "diagram-series": "test_gate_k_diagram_series",
    "hook-hero": "test_gate_p_final_document_round_trip",
    "explanation-block": "test_gate_p_final_document_round_trip",
    "worked-example-card": "test_gate_p_final_document_round_trip",
    "summary-block": "test_gate_p_final_document_round_trip",
    "section-header": "test_content_lane_exact_validation",
    "prerequisite-strip": "test_content_lane_exact_validation",
    "callout-block": "test_content_lane_exact_validation",
    "what-next-bridge": "test_content_lane_exact_validation",
    "section-divider": "test_content_lane_exact_validation",
    "definition-card": "test_content_lane_exact_validation",
    "definition-family": "test_content_lane_exact_validation",
    "glossary-rail": "test_content_lane_exact_validation",
    "insight-strip": "test_content_lane_exact_validation",
    "key-fact": "test_content_lane_exact_validation",
    "comparison-grid": "test_content_lane_exact_validation",
    "process-steps": "test_content_lane_exact_validation",
    "pitfall-alert": "test_content_lane_exact_validation",
}


def strategy_for(lane: str, component_id: str) -> str | None:
    return PAYLOAD_STRATEGIES.get((lane, component_id))


__all__ = [
    "CONTENT_COMPONENT_IDS",
    "EXACT_CONTRACT_TEST_MARKERS",
    "ITEM_COMPONENT_IDS",
    "PAYLOAD_STRATEGIES",
    "SCHEMA_SUMMARIES",
    "VISUAL_COMPONENT_IDS",
    "assemble_answer_key_content",
    "assemble_content_payload",
    "assemble_items_content",
    "assemble_visual_content",
    "extract_question_refs",
    "question_refs_from_payload",
    "questions_from_refs",
    "strategy_for",
]

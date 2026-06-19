from __future__ import annotations

import json
from typing import Any

from v3_blueprint.models import ProductionBlueprint
from v3_execution.models import DraftPack

COHERENCE_SYSTEM_PROMPT = """You are a coherence reviewer, not a lesson designer.

Review the generated draft pack against the approved Production Blueprint.
Do not suggest improvements beyond what the blueprint requires.
Do not redesign the lesson.
Do not add sections, questions, or visuals that are not in the blueprint.

For each issue you identify, state:
- The specific blueprint field that was not followed (blueprint_ref)
- The specific generated content that failed to follow it (generated_ref)
- The severity (minor / major / blocking)
- suggested_repair_executor as one of:
  section_writer, question_writer, visual_executor, answer_key_generator, assembler

Return JSON matching the schema: { "issues": [ ReviewIssue, ... ] }.
Each ReviewIssue must include: issue_id (uuid string), severity, category, message,
optional blueprint_ref, optional generated_ref, suggested_repair_executor, optional repair_target_id.

Categories must be one of:
missing_planned_content, extra_unplanned_content, anchor_drift, visual_mismatch,
question_mismatch, answer_key_mismatch, register_mismatch,
practice_progression_mismatch, internal_artifact_leak, schema_violation, print_risk

Return { "issues": [] } if no issues are found. Do not return prose outside JSON."""


def build_llm_review_payload(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
    deterministic_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compressed text-only briefing for LLM coherence review — no image bytes."""

    section_summaries: list[dict[str, Any]] = []
    for sec in draft_pack.sections:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("section_id")
        keys = sorted(k for k in sec.keys() if k not in {"section_id", "template_id"})
        text_samples: list[str] = []
        practice = sec.get("practice")
        if isinstance(practice, dict):
            probs = practice.get("problems")
            if isinstance(probs, list) and probs:
                q0 = probs[0]
                if isinstance(q0, dict) and isinstance(q0.get("question"), str):
                    text_samples.append(q0["question"][:240])
        for k in keys[:6]:
            val = sec.get(k)
            if isinstance(val, dict):
                blob = json.dumps(val, ensure_ascii=False)[:400]
                text_samples.append(f"{k}:{blob}")
        section_summaries.append(
            {
                "id": sid,
                "fields": keys,
                "text_sample": " | ".join(text_samples)[:1200],
            }
        )

    question_list: list[dict[str, Any]] = []
    for sec in draft_pack.sections:
        if not isinstance(sec, dict):
            continue
        practice = sec.get("practice")
        if not isinstance(practice, dict):
            continue
        probs = practice.get("problems")
        if not isinstance(probs, list):
            continue
        for idx, prob in enumerate(probs):
            if isinstance(prob, dict):
                question_list.append(
                    {
                        "section_id": sec.get("section_id"),
                        "index": idx,
                        "difficulty": prob.get("difficulty"),
                        "text_sample": str(prob.get("question", ""))[:200],
                    }
                )

    visual_metadata: list[dict[str, Any]] = []
    for sec in draft_pack.sections:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("section_id")
        diag = sec.get("diagram")
        if isinstance(diag, dict):
            visual_metadata.append(
                {
                    "scope": "diagram",
                    "section_id": sid,
                    "caption": str(diag.get("caption", ""))[:300],
                    "alt_text": str(diag.get("alt_text", ""))[:300],
                }
            )
        ds = sec.get("diagram_series")
        if isinstance(ds, dict):
            diagrams = ds.get("diagrams")
            if isinstance(diagrams, list):
                for i, step in enumerate(diagrams[:6]):
                    if isinstance(step, dict):
                        visual_metadata.append(
                            {
                                "scope": "diagram_series",
                                "section_id": sid,
                                "frame": i,
                                "caption": str(step.get("caption", ""))[:240],
                            }
                        )

    ak_summary: dict[str, Any] = {"style": None, "entry_count": 0}
    if draft_pack.answer_key:
        ak_summary["style"] = draft_pack.answer_key.style
        ak_summary["entry_count"] = len(draft_pack.answer_key.entries)

    payload: dict[str, Any] = {
        "blueprint_summary": {
            "lesson_mode": blueprint.lesson.lesson_mode,
            "resource_type": blueprint.lesson.resource_type,
            "register": blueprint.voice.register_name,
            "tone": blueprint.voice.tone,
            "learner_profile_level": blueprint.metadata.subject,
            "question_plan": [
                {
                    "id": q.question_id,
                    "section_id": q.section_id,
                    "temperature": q.temperature,
                    "expected_answer": q.expected_answer[:120],
                }
                for q in blueprint.question_plan
            ],
            "visual_strategy": [v.strategy for v in blueprint.visual_strategy.visuals],
            "consistency_expectations": [
                "Obey register and blueprint temperatures.",
                "Preserve anchor facts and expected answers.",
            ],
            "prior_knowledge_count": len(blueprint.prior_knowledge),
            "repair_focus": blueprint.repair_focus.model_dump(mode="json")
            if blueprint.repair_focus
            else None,
        },
        "section_summaries": section_summaries,
        "question_list": question_list,
        "visual_metadata": visual_metadata,
        "answer_key_summary": ak_summary,
        "deterministic_issues": deterministic_issues,
    }
    return payload


def build_llm_review_user_prompt(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
    deterministic_issues_json: list[dict[str, Any]],
) -> str:
    payload = build_llm_review_payload(blueprint, draft_pack, deterministic_issues_json)
    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["COHERENCE_SYSTEM_PROMPT", "build_llm_review_payload", "build_llm_review_user_prompt"]

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from contracts.lectio import (
    MANUAL_ONLY_COMPONENT_IDS,
    get_component_card,
    get_section_field_for_component,
)
from v3_blueprint.models import ProductionBlueprint
from v3_execution.component_aliases import canonical_component_id
from v3_execution.models import DraftPack

from v3_review.models import IssueCategory, RepairExecutor, ReviewIssue, Severity


def _issue(
    *,
    severity: Severity,
    category: IssueCategory,
    message: str,
    blueprint_ref: str | None = None,
    generated_ref: str | None = None,
    executor: RepairExecutor = "assembler",
    repair_target_id: str | None = None,
) -> ReviewIssue:
    return ReviewIssue(
        severity=severity,
        category=category,
        message=message,
        blueprint_ref=blueprint_ref,
        generated_ref=generated_ref,
        suggested_repair_executor=executor,
        repair_target_id=repair_target_id,
    )


LEAK_PATTERN_STRINGS = [
    r"section-[a-f0-9]{8}",
    r"wo_[a-z_]+_\d+",
    r"anchor_[a-z_]+_\d+",
    r"\bundefined\b",
    r"\bnull\b",
    r"\bTODO\b",
    r"\[object Object\]",
    r"\bNaN\b",
    r"source_work_order_id",
    r"component_id",
    r"blueprint_id",
    r"generation_id",
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
]
_LEAK_RES = [re.compile(p, re.IGNORECASE) for p in LEAK_PATTERN_STRINGS]

_SKIP_TEXT_KEYS = frozenset(
    {
        "image_url",
        "fallback_image_url",
        "html_fragment",
        "diagram",
        "step_label",
        "type",
    }
)
_VISUAL_COMPONENT_IDS = frozenset(
    {"diagram-block", "diagram-series", "diagram-compare", "simulation-block"}
)
_VISUAL_REFERENCE_RE = re.compile(
    r"\b(this|the)\s+(shape|figure|diagram|image|picture)\b|shown\s+(below|above)|look\s+at\b",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _walk_student_strings(obj: Any, key: str | None = None) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        lk = (key or "").lower()
        if lk in _SKIP_TEXT_KEYS or lk.endswith("_url"):
            return out
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in {"section_id", "template_id"}:
                continue
            if kl.endswith("_id") and kl not in {"question_id"}:
                continue
            out.extend(_walk_student_strings(v, k))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_walk_student_strings(item, key))
    return out


def collect_student_facing_text(draft_pack: DraftPack) -> str:
    parts: list[str] = []
    for sec in draft_pack.sections:
        parts.extend(_walk_student_strings(sec))
    if draft_pack.answer_key:
        for ent in draft_pack.answer_key.entries:
            if isinstance(ent, dict):
                for fld in ("student_answer", "explanation", "working"):
                    val = ent.get(fld)
                    if isinstance(val, str):
                        parts.append(val)
    return "\n".join(parts)


def _normalize_question_text(text: str) -> str:
    return re.sub(r"\s+", " ", _PUNCT_RE.sub(" ", text.lower())).strip()


def _question_strings(draft_pack: DraftPack) -> list[tuple[str, str, str, int | None, dict[str, Any]]]:
    out: list[tuple[str, str, str, int | None, dict[str, Any]]] = []
    for sec in draft_pack.sections:
        if not isinstance(sec, dict):
            continue
        sid = str(sec.get("section_id") or "<unknown>")
        practice = sec.get("practice")
        if isinstance(practice, dict):
            problems = practice.get("problems")
            if isinstance(problems, list):
                for idx, item in enumerate(problems):
                    if isinstance(item, dict) and isinstance(item.get("question"), str):
                        out.append(
                            (
                                sid,
                                f"{sid}.practice.problems[{idx}].question",
                                item["question"],
                                idx,
                                item,
                            )
                        )
        short_answer = sec.get("short_answer")
        if isinstance(short_answer, dict) and isinstance(short_answer.get("question"), str):
            out.append((sid, f"{sid}.short_answer.question", short_answer["question"], None, short_answer))
        quiz = sec.get("quiz")
        if isinstance(quiz, dict) and isinstance(quiz.get("question"), str):
            out.append((sid, f"{sid}.quiz.question", quiz["question"], None, quiz))
        reflection = sec.get("reflection")
        if isinstance(reflection, dict) and isinstance(reflection.get("prompt"), str):
            out.append((sid, f"{sid}.reflection.prompt", reflection["prompt"], None, reflection))
    return out


def check_planned_sections_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    planned = [s.section_id for s in blueprint.sections]
    present = {s.get("section_id") for s in draft_pack.sections if isinstance(s, dict)}
    issues: list[ReviewIssue] = []
    for sid in planned:
        if sid not in present:
            issues.append(
                _issue(
                    severity="blocking",
                    category="missing_planned_content",
                    message=f"Planned section '{sid}' missing from draft pack.",
                    blueprint_ref=f"sections[{sid}]",
                    generated_ref=sid,
                    executor="section_writer",
                    repair_target_id=f"section:{sid}",
                )
            )
    return issues


def check_no_extra_sections(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    planned = {s.section_id for s in blueprint.sections}
    issues: list[ReviewIssue] = []
    for sec in draft_pack.sections:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("section_id")
        if sid not in planned:
            issues.append(
                _issue(
                    severity="blocking",
                    category="extra_unplanned_content",
                    message=f"Draft contains unplanned section '{sid}'.",
                    blueprint_ref="sections",
                    generated_ref=str(sid),
                    executor="assembler",
                )
            )
    return issues


def check_planned_components_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    by_section = {s["section_id"]: s for s in draft_pack.sections if isinstance(s, dict)}
    for sec_plan in blueprint.sections:
        bucket = by_section.get(sec_plan.section_id)
        if bucket is None:
            continue
        for comp in sec_plan.components:
            cid = canonical_component_id(comp.component)
            if cid in _VISUAL_COMPONENT_IDS:
                # Visual components are filled by visual executor, not section writer.
                continue
            field = get_section_field_for_component(cid)
            if field is None:
                issues.append(
                    _issue(
                        severity="blocking",
                        category="schema_violation",
                        message=f"No manifest field mapping for component '{cid}'.",
                        blueprint_ref=f"sections[{sec_plan.section_id}].components",
                        generated_ref=cid,
                        executor="section_writer",
                        repair_target_id=f"component:{sec_plan.section_id}:{cid}",
                    )
                )
                continue
            if field not in bucket or bucket[field] in (None, "", {}):
                issues.append(
                    _issue(
                        severity="blocking",
                        category="missing_planned_content",
                        message=f"Missing planned component output '{cid}' ({field}).",
                        blueprint_ref=f"sections[{sec_plan.section_id}].components",
                        generated_ref=f"{sec_plan.section_id}.{field}",
                        executor="section_writer",
                        repair_target_id=f"component:{sec_plan.section_id}:{cid}",
                    )
                )
    return issues


def _questions_per_section(blueprint: ProductionBlueprint) -> dict[str, int]:
    out: dict[str, int] = {}
    for q in blueprint.question_plan:
        out[q.section_id] = out.get(q.section_id, 0) + 1
    return out


def check_planned_questions_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    want = _questions_per_section(blueprint)
    by_section = {s["section_id"]: s for s in draft_pack.sections if isinstance(s, dict)}
    for sid, n in want.items():
        bucket = by_section.get(sid)
        practice = (bucket or {}).get("practice") if bucket else None
        probs = practice.get("problems") if isinstance(practice, dict) else None
        got = len(probs) if isinstance(probs, list) else 0
        if got < n:
            issues.append(
                _issue(
                    severity="blocking",
                    category="missing_planned_content",
                    message=f"Section '{sid}' expected {n} practice questions, found {got}.",
                    blueprint_ref=f"question_plan:{sid}",
                    generated_ref=f"{sid}.practice",
                    executor="question_writer",
                    repair_target_id=f"questions:{sid}",
                )
            )
    return issues


def check_no_extra_questions(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    want = _questions_per_section(blueprint)
    got_by_section: dict[str, int] = {}
    for sid, _path, _text, _idx, _payload in _question_strings(draft_pack):
        got_by_section[sid] = got_by_section.get(sid, 0) + 1
    for sid, got in got_by_section.items():
        expected = want.get(sid, 0)
        if got > expected:
            issues.append(
                _issue(
                    severity="minor",
                    category="extra_unplanned_content",
                    message=f"Section '{sid}' has {got} question-bearing items but blueprint plans {expected}.",
                    blueprint_ref="question_plan",
                    generated_ref=f"{sid}.practice",
                    executor="question_writer",
                    repair_target_id=f"questions:{sid}",
                )
            )
    return issues


def _section_has_visual_media(bucket: dict[str, Any]) -> bool:
    if not isinstance(bucket, dict):
        return False
    diag = bucket.get("diagram")
    if isinstance(diag, dict) and diag.get("image_url"):
        return True
    compare = bucket.get("diagram_compare")
    if isinstance(compare, dict) and (
        compare.get("before_image_url") or compare.get("after_image_url")
    ):
        return True
    ds = bucket.get("diagram_series")
    if isinstance(ds, dict):
        diagrams = ds.get("diagrams")
        if isinstance(diagrams, list) and any(
            isinstance(d, dict) and d.get("image_url") for d in diagrams
        ):
            return True
    sim = bucket.get("simulation")
    if isinstance(sim, dict) and (sim.get("html_fragment") or "").strip():
        return True
    return False


def check_planned_visuals_exist(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    by_section = {s["section_id"]: s for s in draft_pack.sections if isinstance(s, dict)}
    for sec_plan in blueprint.sections:
        if not sec_plan.visual_required:
            continue
        bucket = by_section.get(sec_plan.section_id)
        if not _section_has_visual_media(bucket or {}):
            issues.append(
                _issue(
                    severity="blocking",
                    category="missing_planned_content",
                    message=f"Section '{sec_plan.section_id}' requires a visual but none is attached.",
                    blueprint_ref=f"sections[{sec_plan.section_id}].visual_required",
                    generated_ref=sec_plan.section_id,
                    executor="visual_executor",
                    repair_target_id=f"visual:{sec_plan.section_id}",
                )
            )
    return issues


def check_visuals_attach_to_valid_targets(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    section_ids = {s.section_id for s in blueprint.sections}
    for idx, vis in enumerate(blueprint.visual_strategy.visuals):
        if vis.section_id not in section_ids:
            issues.append(
                _issue(
                    severity="blocking",
                    category="visual_mismatch",
                    message=f"Visual strategy entry #{idx} references unknown section '{vis.section_id}'.",
                    blueprint_ref=f"visual_strategy.visuals[{idx}]",
                    generated_ref=vis.section_id,
                    executor="assembler",
                )
            )
    return issues


def check_duplicate_questions(draft_pack: DraftPack) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    seen: dict[str, str] = {}
    for _sid, path, text, _idx, _payload in _question_strings(draft_pack):
        normalized = _normalize_question_text(text)
        if not normalized:
            continue
        first_path = seen.get(normalized)
        if first_path:
            issues.append(
                _issue(
                    severity="minor",
                    category="repeated_content",
                    message=f"Question appears twice: {first_path} and {path}.",
                    generated_ref=path,
                    executor="question_writer",
                )
            )
        else:
            seen[normalized] = path
    return issues


def check_visual_failures(
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    """Flag visual blocks that failed to generate after all retries."""
    issues: list[ReviewIssue] = []
    for block in getattr(draft_pack, "visual_blocks", []):
        if getattr(block, "status", "ready") == "failed":
            issues.append(
                _issue(
                    severity="minor",
                    category="visual_generation_failed",
                    message=(
                        f"Visual '{block.visual_id}' failed to generate "
                        f"for section '{block.attaches_to}'. "
                        f"Error: {block.error_message or 'unknown'}. "
                        "Section rendered without it."
                    ),
                )
            )
        if getattr(block, "status", "ready") == "omitted_quality":
            issues.append(
                _issue(
                    severity="minor",
                    category="visual_generation_failed",
                    message=(
                        "image omitted by quality gate: "
                        f"{block.error_message or 'quality criteria not met'}"
                    ),
                )
            )
    return issues


def check_visual_text_references(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    planned_by_section: dict[str, list[bool]] = {}
    for item in blueprint.question_plan:
        planned_by_section.setdefault(item.section_id, []).append(item.diagram_required)

    issues: list[ReviewIssue] = []
    for sid, path, text, index, payload in _question_strings(draft_pack):
        if isinstance(payload, dict) and isinstance(payload.get("diagram"), dict):
            continue
        planned = planned_by_section.get(sid, [])
        diagram_required = False
        if index is not None and index < len(planned):
            diagram_required = planned[index]
        elif planned:
            diagram_required = any(planned)
        if diagram_required:
            continue
        match = _VISUAL_REFERENCE_RE.search(text)
        if match:
            issues.append(
                _issue(
                    severity="minor",
                    category="visual_mismatch",
                    message=f"Question references a visual without a planned diagram: '{match.group(0)}' at {path}.",
                    blueprint_ref=f"question_plan:{sid}",
                    generated_ref=path,
                    executor="question_writer",
                    repair_target_id=f"questions:{sid}",
                )
            )
    return issues


def check_answer_key_entries(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    if not blueprint.question_plan:
        return issues
    ak = draft_pack.answer_key
    if ak is None:
        issues.append(
            _issue(
                severity="blocking",
                category="answer_key_mismatch",
                message="Answer key missing but questions are planned.",
                blueprint_ref="answer_key",
                executor="answer_key_generator",
                repair_target_id="answer_key:main",
            )
        )
        return issues
    include = {q.question_id for q in blueprint.question_plan}
    present = set()
    for ent in ak.entries:
        if isinstance(ent, dict) and ent.get("question_id"):
            present.add(str(ent["question_id"]))
    for missing in sorted(include - present):
        issues.append(
            _issue(
                severity="blocking",
                category="answer_key_mismatch",
                message=f"Answer key missing entry for question '{missing}'.",
                blueprint_ref="answer_key_plan.include_question_ids",
                generated_ref=missing,
                executor="answer_key_generator",
                repair_target_id=f"answer_key:{missing}",
            )
        )
    return issues


def check_expected_answers_preserved(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    ak = draft_pack.answer_key
    if ak is None:
        return issues
    by_q: dict[str, dict[str, Any]] = {}
    for ent in ak.entries:
        if isinstance(ent, dict) and ent.get("question_id"):
            by_q[str(ent["question_id"])] = ent
    for pq in blueprint.question_plan:
        ent = by_q.get(pq.question_id)
        if not ent:
            continue
        student = str(ent.get("student_answer", "")).strip()
        expected = pq.expected_answer.strip()
        if expected and expected not in student:
            issues.append(
                _issue(
                    severity="blocking",
                    category="answer_key_mismatch",
                    message=(
                        f"Answer key for '{pq.question_id}' does not preserve blueprint expected answer."
                    ),
                    blueprint_ref=f"question_plan[{pq.question_id}].expected_answer",
                    generated_ref=pq.question_id,
                    executor="answer_key_generator",
                    repair_target_id=f"answer_key:{pq.question_id}",
                )
            )
    return issues


def check_anchor_facts(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    corpus = collect_student_facing_text(draft_pack).lower()
    issues: list[ReviewIssue] = []
    if blueprint.lesson.lesson_mode == "repair" and blueprint.repair_focus is not None:
        fault = blueprint.repair_focus.fault_line.strip().lower()
        if fault and fault not in corpus:
            issues.append(
                _issue(
                    severity="blocking",
                    category="anchor_drift",
                    message="Repair-lesson fault line does not appear in generated student-facing text.",
                    blueprint_ref="repair_focus.fault_line",
                    executor="section_writer",
                    repair_target_id="repair_focus",
                )
            )
    for pk in blueprint.prior_knowledge:
        fragment = pk.strip().lower()
        if len(fragment) < 8:
            continue
        if fragment not in corpus:
            issues.append(
                _issue(
                    severity="major",
                    category="anchor_drift",
                    message=f"Prior knowledge anchor may be missing from draft: '{pk[:80]}'",
                    blueprint_ref="prior_knowledge",
                    executor="section_writer",
                )
            )
    return issues


def check_internal_artifact_leaks(draft_pack: DraftPack) -> list[ReviewIssue]:
    texts = _walk_student_strings(draft_pack.sections)
    if draft_pack.answer_key:
        for ent in draft_pack.answer_key.entries:
            if isinstance(ent, dict):
                for fld in ("student_answer", "explanation", "working"):
                    val = ent.get(fld)
                    if isinstance(val, str):
                        texts.append(val)
    issues: list[ReviewIssue] = []
    for text in texts:
        for rx in _LEAK_RES:
            if rx.search(text):
                issues.append(
                    _issue(
                        severity="blocking",
                        category="internal_artifact_leak",
                        message=f"Internal artifact pattern matched in student-facing text: {rx.pattern!r}",
                        generated_ref=text[:120],
                        executor="section_writer",
                    )
                )
                break
    return issues


def check_lectio_schema_validity(
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    from v3_execution.runtime.lectio_validation import validate_section_content

    issues: list[ReviewIssue] = []
    for sec in draft_pack.sections:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("section_id", "<unknown>")
        for warn in sec.get("_schema_warnings", []):
            if isinstance(warn, str) and warn.startswith("trimmed:"):
                continue
            issues.append(
                _issue(
                    severity="minor",
                    category="schema_violation",
                    message=f"Section '{sid}' assembly schema warning: {warn}",
                    generated_ref=sid,
                    executor="assembler",
                )
            )
        _, errors = validate_section_content(sec)
        for err in errors[:12]:
            issues.append(
                _issue(
                    severity="major",
                    category="schema_violation",
                    message=f"Section '{sid}': {err}",
                    generated_ref=sid,
                    executor="assembler",
                )
            )
    return issues


def check_component_ids_in_lectio_contract(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    _ = draft_pack
    issues: list[ReviewIssue] = []
    seen: set[str] = set()
    for sec in blueprint.sections:
        for comp in sec.components:
            cid = canonical_component_id(comp.component)
            if cid in seen:
                continue
            seen.add(cid)
            if get_component_card(cid) is None:
                issues.append(
                    _issue(
                        severity="blocking",
                        category="unknown_component",
                        message=(
                            f"Component '{cid}' in blueprint section '{sec.section_id}' "
                            "is not present in lectio-content-contract.json. "
                            "Check component slugs and Lectio version."
                        ),
                        blueprint_ref=f"sections[{sec.section_id}].components",
                        generated_ref=cid,
                        executor="assembler",
                        repair_target_id=sec.section_id,
                    )
                )
    return issues


def _manual_only_issue(component_id: str, *, ref: str) -> ReviewIssue:
    return _issue(
        severity="major",
        category="extra_unplanned_content",
        message=f"component '{component_id}' is manual-only and must not be AI-planned",
        blueprint_ref=ref,
        generated_ref=component_id,
        executor="assembler",
    )


def check_manual_only_components(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    seen_refs: set[tuple[str, str]] = set()
    for sec in blueprint.sections:
        for comp in sec.components:
            cid = canonical_component_id(comp.component)
            if cid in MANUAL_ONLY_COMPONENT_IDS:
                key = (cid, f"sections[{sec.section_id}].components")
                if key not in seen_refs:
                    seen_refs.add(key)
                    issues.append(_manual_only_issue(cid, ref=key[1]))

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            component_id = value.get("component_id")
            if isinstance(component_id, str) and component_id in MANUAL_ONLY_COMPONENT_IDS:
                key = (component_id, path)
                if key not in seen_refs:
                    seen_refs.add(key)
                    issues.append(_manual_only_issue(component_id, ref=path))
            for child_key, child_value in value.items():
                visit(child_value, f"{path}.{child_key}")
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                visit(item, f"{path}[{idx}]")

    visit(draft_pack.sections, "sections")
    return issues


CheckFn = Callable[..., list[ReviewIssue]]

RECHECK_MAP: dict[str, list[CheckFn]] = {
    "section_component": [
        lambda bp, dp: check_planned_components_exist(bp, dp),
        lambda bp, dp: check_anchor_facts(bp, dp),
        lambda bp, dp: check_internal_artifact_leaks(dp),
        lambda bp, dp: check_lectio_schema_validity(dp),
    ],
    "question": [
        lambda bp, dp: check_planned_questions_exist(bp, dp),
        lambda bp, dp: check_duplicate_questions(dp),
        lambda bp, dp: check_visual_text_references(bp, dp),
        lambda bp, dp: check_expected_answers_preserved(bp, dp),
        lambda bp, dp: check_anchor_facts(bp, dp),
    ],
    "visual": [
        lambda bp, dp: check_planned_visuals_exist(bp, dp),
        lambda bp, dp: check_visuals_attach_to_valid_targets(bp, dp),
        lambda bp, dp: check_visual_failures(dp),
        lambda bp, dp: check_anchor_facts(bp, dp),
    ],
    "answer_key": [
        lambda bp, dp: check_answer_key_entries(bp, dp),
        lambda bp, dp: check_expected_answers_preserved(bp, dp),
    ],
    "assembly": [
        lambda bp, dp: check_planned_sections_exist(bp, dp),
        lambda bp, dp: check_planned_components_exist(bp, dp),
    ],
}


def run_rechecks_for_target(
    target_type: str,
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    checks = RECHECK_MAP.get(target_type, [])
    out: list[ReviewIssue] = []
    for fn in checks:
        out.extend(fn(blueprint, draft_pack))
    return out


__all__ = [
    "RECHECK_MAP",
    "check_anchor_facts",
    "check_answer_key_entries",
    "check_component_ids_in_lectio_contract",
    "check_duplicate_questions",
    "check_expected_answers_preserved",
    "check_internal_artifact_leaks",
    "check_lectio_schema_validity",
    "check_manual_only_components",
    "check_no_extra_questions",
    "check_no_extra_sections",
    "check_planned_components_exist",
    "check_planned_questions_exist",
    "check_planned_sections_exist",
    "check_planned_visuals_exist",
    "check_visual_failures",
    "check_visual_text_references",
    "check_visuals_attach_to_valid_targets",
    "collect_student_facing_text",
    "run_rechecks_for_target",
]

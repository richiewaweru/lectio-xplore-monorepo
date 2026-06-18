from __future__ import annotations

from collections.abc import Iterable

from planning.models import (
    NormalizedBrief,
    PlanningTemplateContract,
    TemplateAlternative,
    TemplateDecision,
)

_WEIGHTS = {
    "topic_type": 0.25,
    "learning_outcome": 0.30,
    "class_style": 0.25,
    "format": 0.20,
}
_OPEN_CANVAS_FALLBACK_THRESHOLD = 0.45


def _clamp(score: float, *, floor: float = 0.0, ceiling: float = 1.0) -> float:
    return max(floor, min(ceiling, score))


def _normalized_words(values: Iterable[str]) -> set[str]:
    words: set[str] = set()
    for value in values:
        for word in value.lower().replace("/", " ").replace(",", " ").split():
            cleaned = word.strip(" .:-_()[]{}'\"")
            if len(cleaned) >= 4:
                words.add(cleaned)
    return words


def _metadata_score(brief: NormalizedBrief, contract: PlanningTemplateContract) -> float:
    score = 0.28

    intent_bonus = {
        "concept": {
            "introduce-concept": 0.22,
            "build-rigor": 0.14,
            "reduce-overload": 0.12,
        },
        "process": {
            "teach-procedure": 0.24,
            "teach-sequence": 0.21,
        },
        "facts": {
            "compare-ideas": 0.2,
            "reinforce-learning": 0.12,
        },
        "mixed": {
            "compare-ideas": 0.18,
            "teach-sequence": 0.12,
            "introduce-concept": 0.1,
        },
    }
    score += intent_bonus.get(brief.resolved_topic_type, {}).get(contract.intent, 0.0)

    if (
        brief.resolved_learning_outcome == "be-able-to-do"
        and any(
            component in contract.available_components
            for component in ("practice-stack", "process-steps", "simulation-block")
        )
    ):
        score += 0.09
    if (
        brief.resolved_learning_outcome in {"remember-terms", "apply-to-new"}
        and any(
            component in contract.available_components
            for component in ("comparison-grid", "definition-family", "glossary-rail")
        )
    ):
        score += 0.08
    if brief.brief.constraints.keep_short and any(
        marker in " ".join(contract.tags).lower()
        for marker in ("compact", "focus", "low-load", "short")
    ):
        score += 0.08
    if brief.brief.constraints.more_practice and any(
        component in contract.available_components
        for component in ("practice-stack", "short-answer", "fill-in-blank")
    ):
        score += 0.08
    if brief.brief.constraints.use_visuals and any(
        component in contract.available_components
        for component in ("diagram-block", "diagram-series", "diagram-compare", "simulation-block")
    ):
        score += 0.08
    if brief.resolved_format == "printed-booklet" and contract.print_rules:
        score += 0.06
    if brief.resolved_format == "screen-based" and contract.interaction_level in {"medium", "high"}:
        score += 0.05

    contract_words = _normalized_words(
        [
            contract.name,
            contract.tagline,
            contract.family,
            contract.intent,
            *contract.tags,
            *contract.best_for,
            *contract.subjects,
            *contract.learner_fit,
        ]
    )
    keyword_overlap = len(contract_words.intersection(set(brief.keyword_profile)))
    score += min(keyword_overlap * 0.04, 0.16)

    return round(_clamp(score, floor=0.18, ceiling=0.95), 4)


def _affinity_score(brief: NormalizedBrief, contract: PlanningTemplateContract) -> tuple[float, int]:
    signals = contract.signal_affinity
    score = 0.0
    coverage = 0

    if signals.topic_type:
        coverage += 1
        score += _WEIGHTS["topic_type"] * signals.topic_type.get(brief.resolved_topic_type, 0.35)

    if signals.learning_outcome:
        coverage += 1
        score += _WEIGHTS["learning_outcome"] * signals.learning_outcome.get(
            brief.resolved_learning_outcome, 0.35
        )

    if brief.brief.signals.class_style and signals.class_style:
        coverage += 1
        class_scores = [
            signals.class_style.get(style, 0.35) for style in brief.brief.signals.class_style
        ]
        score += _WEIGHTS["class_style"] * (sum(class_scores) / len(class_scores))
    elif signals.class_style:
        coverage += 1
        score += _WEIGHTS["class_style"] * 0.5

    if signals.format:
        coverage += 1
        score += _WEIGHTS["format"] * signals.format.get(brief.resolved_format, 0.45)

    return round(score, 4), coverage


def _score_contract(brief: NormalizedBrief, contract: PlanningTemplateContract) -> float:
    affinity_score, coverage = _affinity_score(brief, contract)
    metadata_score = _metadata_score(brief, contract)

    if coverage == 0:
        return metadata_score
    if coverage < len(_WEIGHTS):
        return round((affinity_score * 0.55) + (metadata_score * 0.45), 4)
    return round((affinity_score * 0.75) + (metadata_score * 0.25), 4)


def _why_not_chosen(contract: PlanningTemplateContract, score: float) -> str:
    if contract.not_ideal_for:
        return contract.not_ideal_for[0]
    if contract.best_for:
        return f"Strong fit for {contract.best_for[0]}, but the top option scored higher."
    return f"Scored {score:.2f}, but another template matched the brief more closely."


def _decision_rationale(contract: PlanningTemplateContract, brief: NormalizedBrief) -> str:
    reasons: list[str] = []
    if contract.best_for:
        reasons.append(contract.best_for[0])
    if brief.resolved_learning_outcome == "be-able-to-do":
        reasons.append("it supports a doing-oriented outcome")
    elif brief.resolved_learning_outcome == "understand-why":
        reasons.append("it fits explanation-first teaching")
    if brief.brief.constraints.keep_short:
        reasons.append("it can stay compact without losing structure")
    if not reasons:
        return f"{contract.name} is the best overall fit for this lesson."
    return f"{contract.name} is the best fit because {'; '.join(reasons[:2])}."


def choose_template(
    brief: NormalizedBrief,
    contracts: list[PlanningTemplateContract],
) -> tuple[PlanningTemplateContract, TemplateDecision]:
    scored = [(contract, _score_contract(brief, contract)) for contract in contracts]
    scored.sort(key=lambda item: item[1], reverse=True)

    chosen_contract, chosen_score = scored[0]
    if chosen_score < _OPEN_CANVAS_FALLBACK_THRESHOLD:
        fallback_contract = next((contract for contract in contracts if contract.id == "open-canvas"), None)
        if fallback_contract is not None:
            chosen_contract = fallback_contract
            chosen_score = _score_contract(brief, fallback_contract)

    alternatives = [
        (contract, score)
        for contract, score in scored
        if contract.id != chosen_contract.id
    ][:3]

    decision = TemplateDecision(
        chosen_id=chosen_contract.id,
        chosen_name=chosen_contract.name,
        rationale=_decision_rationale(chosen_contract, brief),
        fit_score=chosen_score,
        alternatives=[
            TemplateAlternative(
                template_id=contract.id,
                template_name=contract.name,
                fit_score=score,
                why_not_chosen=_why_not_chosen(contract, score),
            )
            for contract, score in alternatives
        ],
    )
    return chosen_contract, decision

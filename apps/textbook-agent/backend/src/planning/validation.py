from __future__ import annotations

from planning.models import PathPlan


class PathValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PathApprovalBlocked(ValueError):
    pass


def _raise(code: str, message: str) -> None:
    raise PathValidationError(code, message)


def normalize_declared_external_prerequisites(plan: PathPlan) -> PathPlan:
    """Repair the planner's unambiguous internal/external field mix-up.

    The model occasionally copies an explicitly declared starting capability into
    ``prerequisites`` even though that field only accepts earlier lesson slugs.
    Moving exact, case-insensitive matches is deterministic and preserves strict
    validation for every undeclared or forward reference.
    """
    normalized = plan.model_copy(deep=True)
    declared = {
        value.casefold(): value
        for value in [
            *normalized.scope_contract.assumed_prerequisites,
            *normalized.starting_knowledge,
        ]
    }
    for lesson in normalized.lessons:
        internal: list[str] = []
        external = list(lesson.external_prerequisites)
        external_folded = {value.casefold() for value in external}
        for prerequisite in lesson.prerequisites:
            canonical = declared.get(prerequisite.casefold())
            if canonical is None:
                internal.append(prerequisite)
                continue
            if canonical.casefold() not in external_folded:
                external.append(canonical)
                external_folded.add(canonical.casefold())
        lesson.prerequisites = internal
        lesson.external_prerequisites = external
    return normalized


def validate_path_plan(plan: PathPlan) -> None:
    seen: set[str] = set()
    prohibited = [term for term in plan.scope_contract.must_not_introduce if term.strip()]

    for lesson in plan.lessons:
        slug = lesson.concept_candidate.slug
        if slug in seen:
            _raise("duplicate_concept_slug", f"Duplicate concept candidate slug: {slug}")
        for prerequisite in lesson.prerequisites:
            if prerequisite not in seen:
                _raise(
                    "prerequisite_not_earlier",
                    f"Prerequisite {prerequisite!r} for {slug!r} does not resolve to an earlier lesson",
                )
        # Undeclared external prerequisites are teacher-owned confirmations, not
        # hard halts. They surface as open_assumptions and block approve_path.
        inspected_text = "\n".join([lesson.objective, *lesson.must_establish]).casefold()
        for term in prohibited:
            if term.casefold() in inspected_text:
                _raise(
                    "must_not_introduce_violation",
                    f"Lesson {slug!r} introduces prohibited term {term!r}",
                )
        seen.add(slug)

    if plan.prerequisite_risks and plan.completeness.reaches_destination:
        _raise(
            "risks_require_unreachable",
            "A path with prerequisite risks cannot claim to reach its destination",
        )


def open_assumptions(
    *,
    starting_knowledge: list[str] | None,
    assumed_prerequisites: list[str] | None,
    lessons: list[object],
    prerequisite_risks: list[object] | None,
) -> list[dict[str, str]]:
    """Derive undeclared external prerequisites awaiting teacher confirmation.

    An assumption is open when a lesson claims an external prerequisite that is
    neither in unit/scope starting knowledge nor already recorded as a
    prerequisite risk (e.g. after the teacher answers ``teach``).
    """
    declared = {
        value.casefold()
        for value in [*(assumed_prerequisites or []), *(starting_knowledge or [])]
        if isinstance(value, str) and value.strip()
    }
    answered_as_risk: set[str] = set()
    for risk in prerequisite_risks or []:
        if isinstance(risk, dict):
            missing = risk.get("missing")
        else:
            missing = getattr(risk, "missing", None)
        if isinstance(missing, str) and missing.strip():
            answered_as_risk.add(missing.casefold())

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for lesson in lessons:
        if getattr(lesson, "skipped", False):
            continue
        slug = getattr(lesson, "concept_slug", None)
        if not isinstance(slug, str) or not slug:
            candidate = getattr(lesson, "concept_candidate", None)
            slug = getattr(candidate, "slug", None) if candidate is not None else None
        if not isinstance(slug, str) or not slug:
            continue
        for prerequisite in getattr(lesson, "external_prerequisites", None) or []:
            if not isinstance(prerequisite, str) or not prerequisite.strip():
                continue
            folded = prerequisite.casefold()
            if folded in declared or folded in answered_as_risk or folded in seen:
                continue
            seen.add(folded)
            result.append({"claimed": prerequisite, "needed_by": slug})
    return result


_PLAIN_VALIDATION_MESSAGES: dict[str, str] = {
    "duplicate_concept_slug": (
        "Two lessons ended up covering the same capability. Try rephrasing your "
        "request so each lesson stays distinct."
    ),
    "prerequisite_not_earlier": (
        "That change would make a lesson depend on something taught later in the "
        "path. Try reordering, or rephrase what you'd like changed."
    ),
    "undeclared_external_prerequisite": (
        "That change assumes prior knowledge the class isn't recorded as already "
        "having. Add it to starting knowledge first, or rephrase the request."
    ),
    "must_not_introduce_violation": (
        "That change introduces a term or idea this unit was scoped to avoid."
    ),
    "risks_require_unreachable": (
        "That change leaves open prerequisite risks while still claiming the "
        "path reaches its destination."
    ),
}


def plain_validation_message(exc: PathValidationError) -> str:
    """Human-readable rendering of a `PathValidationError` for teacher-facing UI."""
    return _PLAIN_VALIDATION_MESSAGES.get(exc.code, str(exc))


def assert_approvable(plan: PathPlan) -> None:
    validate_path_plan(plan)
    if plan.prerequisite_risks or not plan.completeness.reaches_destination:
        raise PathApprovalBlocked(
            "Path approval blocked: prerequisite risks prevent reaching the destination"
        )
    if not plan.completeness.forward_verified:
        raise PathApprovalBlocked("Path approval blocked: forward verification is incomplete")

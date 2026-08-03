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
    allowed_external = {
        value.casefold()
        for value in [
            *plan.scope_contract.assumed_prerequisites,
            *plan.starting_knowledge,
        ]
    }
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
        for prerequisite in lesson.external_prerequisites:
            if prerequisite.casefold() not in allowed_external:
                _raise(
                    "undeclared_external_prerequisite",
                    f"External prerequisite {prerequisite!r} is not declared",
                )
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

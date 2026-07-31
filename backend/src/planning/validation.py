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


def assert_approvable(plan: PathPlan) -> None:
    validate_path_plan(plan)
    if plan.prerequisite_risks or not plan.completeness.reaches_destination:
        raise PathApprovalBlocked(
            "Path approval blocked: prerequisite risks prevent reaching the destination"
        )
    if not plan.completeness.forward_verified:
        raise PathApprovalBlocked("Path approval blocked: forward verification is incomplete")

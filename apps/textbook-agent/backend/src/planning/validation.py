from __future__ import annotations

import re
from typing import Iterable

from planning.models import (
    CanonicalPathLesson,
    CanonicalPathPlan,
    CanonicalPathScope,
    PathPlan,
    PathPlanDraft,
)

_KNOWLEDGE_TYPES: frozenset[str] = frozenset(
    {"procedural", "conceptual", "factual", "evaluative"}
)

_OBJECTIVE_PREFIXES = (
    "by the end, students can ",
    "by the end students can ",
    "students can ",
    "learners can ",
)

_STARTING_KNOWLEDGE_PREFIXES = (
    "we're assuming students already know ",
    "we're assuming they already know ",
    "i'm assuming they already know ",
    "i am assuming they already know ",
    "assuming students already know ",
    "assuming they already know ",
)


class PathValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PathApprovalBlocked(ValueError):
    pass


class PathPlanningError(ValueError):
    """Recoverable planner failure after the repair budget is exhausted."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) if self.errors else "Path planning failed")


def _raise(code: str, message: str) -> None:
    raise PathValidationError(code, message)


def slugify(value: str) -> str:
    """Lowercase, extract alphanumeric segments, join with dots."""
    segments = re.findall(r"[a-z0-9]+", value.casefold())
    return ".".join(segments)


def concept_slug_for(subject: str, title: str) -> str:
    subject_slug = slugify(subject)
    title_slug = slugify(title)
    if not subject_slug or not title_slug:
        _raise(
            "invalid_concept_slug",
            f"Cannot build concept slug from subject={subject!r} title={title!r}",
        )
    return f"{subject_slug}.{title_slug}"


def _strip_known_prefix(text: str, prefixes: Iterable[str]) -> str:
    """Strip repeated known UI prefixes without rewriting legitimate teacher text."""
    value = text.strip()
    if not value:
        return value
    changed = True
    while changed:
        changed = False
        folded = value.casefold()
        for prefix in prefixes:
            if folded.startswith(prefix):
                value = value[len(prefix) :].lstrip(" :,-")
                changed = True
                break
    return value.strip()


def normalize_constructor_objective(text: str) -> str:
    return _strip_known_prefix(text, _OBJECTIVE_PREFIXES)


def normalize_constructor_starting_knowledge(items: list[str]) -> list[str]:
    return [
        _strip_known_prefix(item, _STARTING_KNOWLEDGE_PREFIXES)
        for item in items
        if isinstance(item, str) and item.strip()
    ]


def normalize_constructor_fields(
    *,
    destination_objective: str,
    starting_knowledge: list[str],
) -> tuple[str, list[str]]:
    return (
        normalize_constructor_objective(destination_objective),
        normalize_constructor_starting_knowledge(starting_knowledge),
    )


def validate_canonical_path_plan(plan: CanonicalPathPlan) -> list[str]:
    """Return deterministic validation errors for a normalized canonical plan."""
    errors: list[str] = []
    if not plan.lessons:
        errors.append("empty lesson list")
        return errors

    keys = [lesson.key for lesson in plan.lessons]
    if len(keys) != len(set(keys)):
        errors.append("duplicate lesson keys after normalization")

    key_index = {lesson.key: index for index, lesson in enumerate(plan.lessons)}
    seen_objectives: dict[str, str] = {}
    for index, lesson in enumerate(plan.lessons):
        if not lesson.title.strip():
            errors.append(f"{lesson.key}: empty title")
        if not lesson.objective.strip():
            errors.append(f"{lesson.key}: empty objective")
        if not lesson.must_establish:
            errors.append(f"{lesson.key}: empty must_establish")
        elif any(not item.strip() for item in lesson.must_establish):
            errors.append(f"{lesson.key}: must_establish contains empty entries")
        if lesson.knowledge_type not in _KNOWLEDGE_TYPES:
            errors.append(f"{lesson.key}: invalid knowledge_type {lesson.knowledge_type!r}")

        objective_key = lesson.objective.strip().casefold()
        if objective_key:
            prior = seen_objectives.get(objective_key)
            if prior is not None:
                errors.append(
                    f"exact duplicate lesson objectives after normalization: "
                    f"{prior} and {lesson.key}"
                )
            else:
                seen_objectives[objective_key] = lesson.key

        for required in lesson.requires:
            if required == lesson.key:
                errors.append(f"{lesson.key}: self dependency on {required!r}")
                continue
            if required not in key_index:
                errors.append(f"{lesson.key}: unknown dependency {required!r}")
                continue
            if key_index[required] >= index:
                errors.append(
                    f"{lesson.key}: forward dependency on {required!r} "
                    f"(must reference an earlier lesson)"
                )

        inspected = "\n".join([lesson.objective, *lesson.must_establish]).casefold()
        for term in plan.scope.do_not_cover:
            if term.strip() and term.casefold() in inspected:
                errors.append(
                    f"{lesson.key}: introduces do_not_cover term {term!r}"
                )

    return errors


def normalize_path_plan_draft(draft: PathPlanDraft) -> CanonicalPathPlan:
    """Normalize a prompt-facing draft into a strict CanonicalPathPlan.

    Raises PathValidationError when the draft cannot be normalized into a
    usable structure (e.g. duplicate input keys, empty lessons).
    """
    if not draft.lessons:
        _raise("empty_lesson_list", "Path plan must contain at least one lesson")

    raw_keys = [lesson.key.strip() for lesson in draft.lessons]
    if any(not key for key in raw_keys):
        _raise("empty_lesson_key", "Every lesson must have a non-empty key")
    if len(raw_keys) != len(set(raw_keys)):
        _raise("duplicate_lesson_key", "Lesson keys must be unique in planner output")

    key_map = {old: f"L{index}" for index, old in enumerate(raw_keys, start=1)}

    must_cover = [item.strip() for item in draft.scope.must_cover if item and item.strip()]
    do_not_cover = [
        item.strip() for item in draft.scope.do_not_cover if item and item.strip()
    ]
    if not must_cover:
        _raise("empty_must_cover", "scope.must_cover must contain at least one item")
    if not do_not_cover:
        _raise("empty_do_not_cover", "scope.do_not_cover must contain at least one item")

    lessons: list[CanonicalPathLesson] = []
    for lesson in draft.lessons:
        old_key = lesson.key.strip()
        new_key = key_map[old_key]
        knowledge = lesson.knowledge_type.strip().casefold()
        if knowledge not in _KNOWLEDGE_TYPES:
            _raise(
                "invalid_knowledge_type",
                f"Lesson {old_key!r} has invalid knowledge_type {lesson.knowledge_type!r}",
            )
        title = lesson.title.strip()
        objective = lesson.objective.strip()
        must_establish = [
            item.strip() for item in lesson.must_establish if item and item.strip()
        ]
        if not title:
            _raise("empty_title", f"Lesson {old_key!r} has an empty title")
        if not objective:
            _raise("empty_objective", f"Lesson {old_key!r} has an empty objective")
        if not must_establish:
            _raise(
                "empty_must_establish",
                f"Lesson {old_key!r} has an empty must_establish list",
            )

        requires: list[str] = []
        for required in lesson.requires:
            required_key = required.strip()
            if not required_key:
                continue
            if required_key not in key_map:
                _raise(
                    "unknown_dependency",
                    f"Lesson {old_key!r} requires unknown key {required_key!r}",
                )
            mapped = key_map[required_key]
            if mapped == new_key:
                _raise(
                    "self_dependency",
                    f"Lesson {old_key!r} cannot require itself",
                )
            requires.append(mapped)

        lessons.append(
            CanonicalPathLesson(
                key=new_key,
                title=title,
                objective=objective,
                requires=requires,
                must_establish=must_establish,
                knowledge_type=knowledge,  # type: ignore[arg-type]
            )
        )

    # Forward-dependency check after key remap (order is draft order).
    key_index = {lesson.key: index for index, lesson in enumerate(lessons)}
    for index, lesson in enumerate(lessons):
        for required in lesson.requires:
            if key_index[required] >= index:
                _raise(
                    "forward_dependency",
                    f"Lesson {lesson.key} has forward dependency on {required}",
                )

    objectives = [lesson.objective.casefold() for lesson in lessons]
    if len(objectives) != len(set(objectives)):
        _raise(
            "duplicate_objectives",
            "Exact duplicate lesson objectives are not allowed",
        )

    plan = CanonicalPathPlan(
        scope=CanonicalPathScope(must_cover=must_cover, do_not_cover=do_not_cover),
        lessons=lessons,
    )
    errors = validate_canonical_path_plan(plan)
    if errors:
        _raise("canonical_validation_failed", "; ".join(errors))
    return plan


def assert_concept_slugs_unique(subject: str, plan: CanonicalPathPlan) -> dict[str, str]:
    """Build code-owned concept slugs; raise on in-plan collision."""
    slugs: dict[str, str] = {}
    seen: dict[str, str] = {}
    for lesson in plan.lessons:
        slug = concept_slug_for(subject, lesson.title)
        prior = seen.get(slug)
        if prior is not None:
            _raise(
                "duplicate_concept_slug",
                f"Concept slug collision between {prior} and {lesson.key}: {slug}",
            )
        seen[slug] = lesson.key
        slugs[lesson.key] = slug
    return slugs


_PLAIN_VALIDATION_MESSAGES: dict[str, str] = {
    "duplicate_lesson_key": (
        "Two lessons used the same key. Try rephrasing so each lesson stays distinct."
    ),
    "duplicate_concept_slug": (
        "Two lessons ended up covering the same capability. Try rephrasing your "
        "request so each lesson stays distinct."
    ),
    "forward_dependency": (
        "That change would make a lesson depend on something taught later in the "
        "path. Try reordering, or rephrase what you'd like changed."
    ),
    "unknown_dependency": (
        "A lesson depends on a capability that is not in this path. Add the missing "
        "lesson, or adjust the dependency."
    ),
    "self_dependency": "A lesson cannot depend on itself.",
    "empty_lesson_list": "The path needs at least one lesson.",
    "duplicate_objectives": (
        "Two lessons share the same objective. Combine them or make each distinct."
    ),
    "must_not_introduce_violation": (
        "That change introduces a term or idea this unit was scoped to avoid."
    ),
    "canonical_validation_failed": (
        "The planned lessons could not be validated. Try planning again."
    ),
}


def plain_validation_message(exc: PathValidationError) -> str:
    """Human-readable rendering of a `PathValidationError` for teacher-facing UI."""
    return _PLAIN_VALIDATION_MESSAGES.get(exc.code, str(exc))


# ── Legacy helpers (retained for old fixtures / assumption APIs) ───────────


def normalize_declared_external_prerequisites(plan: PathPlan) -> PathPlan:
    """Legacy repair for old PathPlan shapes. Not used by the active planner."""
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
    """Legacy PathPlan validator. Not used by the active planner."""
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
    """Legacy open-assumption derivation. New paths always return []."""
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


def assert_approvable(plan: PathPlan) -> None:
    """Legacy approve gate on PathPlan JSON. Active approve uses DB graph."""
    validate_path_plan(plan)
    if plan.prerequisite_risks or not plan.completeness.reaches_destination:
        raise PathApprovalBlocked(
            "Path approval blocked: prerequisite risks prevent reaching the destination"
        )
    if not plan.completeness.forward_verified:
        raise PathApprovalBlocked("Path approval blocked: forward verification is incomplete")

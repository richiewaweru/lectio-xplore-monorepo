"""D1: move Unit orchestration into application/unit_lesson."""

from __future__ import annotations

from pathlib import Path

SRC = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src")
UNIT = SRC / "application" / "unit_lesson"
UNIT.mkdir(parents=True, exist_ok=True)

CONTRACTS = '''"""Unit-lesson preparation contracts and type aliases."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from curriculum.models import (
    ComponentSelection,
    PathStructuralPagePlan,
    PathStructuralPlan,
)


class PathPreparationBlocked(ValueError):
    pass


StructuralPlanner = Callable[
    [dict[str, Any]], Awaitable[PathStructuralPlan | PathStructuralPagePlan]
]
ComponentSelector = Callable[[dict[str, Any]], Awaitable[ComponentSelection]]

__all__ = [
    "ComponentSelector",
    "PathPreparationBlocked",
    "StructuralPlanner",
]
'''

STATUS = '''"""Preparation reuse / stale-admission status helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.contracts import PathPreparationBlocked
from core.database.models import GenerationModel, LessonProvenanceModel, PathLessonModel
from curriculum.models import PrepareLessonRequest, PreparedLessonResponse
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.planning.persistence import load_chunked_state


async def try_reuse_existing_preparation(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    request: PrepareLessonRequest,
) -> tuple[PreparedLessonResponse, StructuralPlan] | None:
    """Return a reused preparation when the existing row is still valid.

    Raises PathPreparationBlocked when an existing preparation is stale or
    settings changed. Returns None when there is no reusable preparation and
    a fresh prepare should proceed.
    """
    previous_pack_id = lesson.pack_id
    if not previous_pack_id:
        return None

    generation = await session.get(GenerationModel, lesson.pack_id)
    provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
    if generation is None or provenance is None:
        return None

    if provenance.objective_hash != lesson.objective_hash:
        raise PathPreparationBlocked(
            "Existing preparation is stale; use explicit regeneration"
        )
    if provenance.path_lesson_revision not in {None, lesson.revision}:
        raise PathPreparationBlocked(
            "Existing preparation is for an earlier lesson revision; use explicit regeneration"
        )
    if provenance.lesson_mode not in {None, request.lesson_mode} or sorted(
        provenance.group_ids or []
    ) != sorted(request.group_ids):
        raise PathPreparationBlocked(
            "Preparation settings changed; use explicit regeneration"
        )
    try:
        state = await load_chunked_state(generation.id, session)
    except ValueError as exc:
        raise PathPreparationBlocked(
            "Existing preparation predates the resumable workflow; regenerate it explicitly"
        ) from exc
    # A failed pre-worker handoff can leave the lesson pointing at an
    # `awaiting_visuals` row before execution ever started. Treat that
    # empty row as stale so the normal Prepare action creates a fresh
    # native run instead of reopening a document that can never make
    # progress. A visual handoff with saved execution/document output
    # remains reusable and can still take the targeted visual retry path.
    stale_empty_visual_handoff = (
        state.get("stage") == "awaiting_visuals"
        and not bool(state.get("execution_started"))
        and not (
            isinstance(generation.document_json, dict)
            and isinstance(generation.document_json.get("sections"), list)
            and generation.document_json.get("sections")
        )
    )
    if stale_empty_visual_handoff:
        return None

    plan = StructuralPlan.model_validate(state.get("structural_plan"))
    slots = [section.role for section in plan.sections]
    return (
        PreparedLessonResponse(
            generation_id=generation.id,
            path_lesson_id=lesson.id,
            objective=lesson.objective,
            objective_hash=lesson.objective_hash,
            skeleton_id=provenance.skeleton_id or "",
            skeleton_version=provenance.skeleton_version or 0,
            slots=slots,
            section_roles=slots,
            status="awaiting_review",
            reused=True,
        ),
        plan,
    )


__all__ = ["try_reuse_existing_preparation"]
'''

INIT = '''"""Unit-path lesson preparation orchestration.

Real ownership lives here (D1). Historical planning.bridge /
generation.path_preparation are temporary re-export shims.
"""

from __future__ import annotations

from application.unit_lesson.contracts import PathPreparationBlocked
from application.unit_lesson.dispatch import (
    enforce_path_owned_card_objective,
    initialise_path_generation,
)
from application.unit_lesson.prepare import prepare_path_lesson

__all__ = [
    "PathPreparationBlocked",
    "enforce_path_owned_card_objective",
    "initialise_path_generation",
    "prepare_path_lesson",
]
'''

BRIDGE_SHIM = '''"""Compatibility shim — use ``application.unit_lesson``.

Temporary (D1). Remove when all call sites import application.unit_lesson.
"""

from __future__ import annotations

from application.unit_lesson.contracts import PathPreparationBlocked
from application.unit_lesson.prepare import (  # noqa: F401
    _build_structural_plan,
    _normalize_page_concept_card_payload,
    prepare_path_lesson,
)

__all__ = [
    "PathPreparationBlocked",
    "_build_structural_plan",
    "_normalize_page_concept_card_payload",
    "prepare_path_lesson",
]
'''

PATH_PREP_SHIM = '''"""Compatibility shim — use ``application.unit_lesson.dispatch``.

Temporary (D1). Remove when all call sites import application.unit_lesson.
"""

from __future__ import annotations

from application.unit_lesson.dispatch import (  # noqa: F401
    enforce_path_owned_card_objective,
    initialise_path_generation,
)

__all__ = ["enforce_path_owned_card_objective", "initialise_path_generation"]
'''


def build_prepare() -> str:
    old = (SRC / "planning" / "bridge.py").read_text(encoding="utf-8")
    # Replace header through type aliases (now in contracts / status).
    # Keep helpers + prepare_path_lesson, but rewrite imports and reuse block.
    body_start = old.index("# Fields the strict")
    helpers_and_rest = old[body_start:]

    # Replace reuse block with status helper call.
    old_reuse = '''    previous_pack_id = lesson.pack_id
    if regenerate and not previous_pack_id:
        raise PathPreparationBlocked("No existing preparation is available to regenerate")
    if regenerate and not (regeneration_reason or "").strip():
        raise PathPreparationBlocked("Regeneration requires a recorded reason")
    if previous_pack_id and not regenerate:
        generation = await session.get(GenerationModel, lesson.pack_id)
        provenance = await session.get(LessonProvenanceModel, lesson.pack_id)
        if generation is not None and provenance is not None:
            if provenance.objective_hash != lesson.objective_hash:
                raise PathPreparationBlocked(
                    "Existing preparation is stale; use explicit regeneration"
                )
            if provenance.path_lesson_revision not in {None, lesson.revision}:
                raise PathPreparationBlocked(
                    "Existing preparation is for an earlier lesson revision; use explicit regeneration"
                )
            if provenance.lesson_mode not in {None, request.lesson_mode} or sorted(
                provenance.group_ids or []
            ) != sorted(request.group_ids):
                raise PathPreparationBlocked(
                    "Preparation settings changed; use explicit regeneration"
                )
            try:
                state = await load_chunked_state(generation.id, session)
            except ValueError as exc:
                raise PathPreparationBlocked(
                    "Existing preparation predates the resumable workflow; regenerate it explicitly"
                ) from exc
            # A failed pre-worker handoff can leave the lesson pointing at an
            # `awaiting_visuals` row before execution ever started. Treat that
            # empty row as stale so the normal Prepare action creates a fresh
            # native run instead of reopening a document that can never make
            # progress. A visual handoff with saved execution/document output
            # remains reusable and can still take the targeted visual retry path.
            stale_empty_visual_handoff = (
                state.get("stage") == "awaiting_visuals"
                and not bool(state.get("execution_started"))
                and not (
                    isinstance(generation.document_json, dict)
                    and isinstance(generation.document_json.get("sections"), list)
                    and generation.document_json.get("sections")
                )
            )
            if not stale_empty_visual_handoff:
                plan = StructuralPlan.model_validate(state.get("structural_plan"))
                slots = [section.role for section in plan.sections]
                return (
                    PreparedLessonResponse(
                        generation_id=generation.id,
                        path_lesson_id=lesson.id,
                        objective=lesson.objective,
                        objective_hash=lesson.objective_hash,
                        skeleton_id=provenance.skeleton_id or "",
                        skeleton_version=provenance.skeleton_version or 0,
                        slots=slots,
                        section_roles=slots,
                        status="awaiting_review",
                        reused=True,
                    ),
                    plan,
                )
'''
    new_reuse = '''    previous_pack_id = lesson.pack_id
    if regenerate and not previous_pack_id:
        raise PathPreparationBlocked("No existing preparation is available to regenerate")
    if regenerate and not (regeneration_reason or "").strip():
        raise PathPreparationBlocked("Regeneration requires a recorded reason")
    if previous_pack_id and not regenerate:
        reused = await try_reuse_existing_preparation(
            session,
            lesson=lesson,
            request=request,
        )
        if reused is not None:
            return reused
'''
    if old_reuse not in helpers_and_rest:
        raise SystemExit("reuse block not found in bridge.py")
    helpers_and_rest = helpers_and_rest.replace(old_reuse, new_reuse, 1)
    helpers_and_rest = helpers_and_rest.replace(
        "from generation.path_preparation import initialise_path_generation\n",
        "",
    )
    # The helpers section doesn't have those imports - they're in the header.
    # Fix PathPreparationBlocked references - they come from contracts.
    # Replace initialise_path_generation call to use local dispatch import.

    header = '''"""Unit-path lesson preparation (application ownership).

Moved from planning.bridge in D1. Cross-domain orchestration only.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson.contracts import (
    ComponentSelector,
    PathPreparationBlocked,
    StructuralPlanner,
)
from application.unit_lesson.dispatch import initialise_path_generation
from application.unit_lesson.status import try_reuse_existing_preparation
from core.database.models import (
    GenerationModel,
    LearningPackModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    PathVersionModel,
    UnitModel,
    UnitScopeContractModel,
)
from contracts.lectio import get_component_card
from curriculum.models import (
    ComponentSelection,
    PathStructuralPagePlan,
    PathStructuralPlan,
    PrepareLessonRequest,
    PreparedLessonResponse,
    SelectedComponent,
)
from curriculum.outcomes import actual_context_for_lessons
from curriculum.schedule import selected_unit_groups
from curriculum.shapes import (
    approved_deviation_contracts,
    deviation_payload,
    lesson_deviations,
)
from planning.agents import run_component_selector, run_path_structural_planner
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    ConceptCard,
    LessonIntent,
    QPlanItem,
    SectionPlan,
    StructuralPlan,
    VariantSpec,
)
from v3_blueprint.planning.objective_ownership import ObjectiveOwnership, ObjectiveOwnershipError
from v3_blueprint.skeletons import (
    SkeletonPreviewRequest,
    SkeletonVariantPreview,
    load_skeleton_catalog,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _preparation_key(*, version_id: str, lesson_id: str, revision: int) -> str:
    raw = json.dumps(
        {"path_version_id": version_id, "path_lesson_id": lesson_id, "revision": revision},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clip_advisory_text(value: str, *, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


async def _preparation_context(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
) -> tuple[dict[str, Any], list[str], list[dict[str, str]], list[dict[str, Any]]]:
    scope = await session.get(UnitScopeContractModel, unit.id)
    scope_contract = {
        "must_establish": list(scope.must_establish or []) if scope else [],
        "may_include": list(scope.may_include or []) if scope else [],
        "must_not_introduce": list(scope.must_not_introduce or []) if scope else [],
        "assumed_prerequisites": list(scope.assumed_prerequisites or []) if scope else [],
        "terminology": list(scope.terminology or []) if scope else [],
        "notation": scope.notation if scope else None,
    }
    earlier = list(
        await session.scalars(
            select(PathLessonModel)
            .where(
                PathLessonModel.path_version_id == version.id,
                PathLessonModel.position < lesson.position,
            )
            .order_by(PathLessonModel.position)
        )
    )
    prior_established = list(dict.fromkeys([
        *list(unit.starting_knowledge or []),
        *(capability for prior in earlier if not prior.skipped for capability in (prior.must_establish or [])),
    ]))
    prerequisite_ids = list(
        await session.scalars(
            select(PathLessonPrerequisiteModel.prerequisite_lesson_id).where(
                PathLessonPrerequisiteModel.path_lesson_id == lesson.id
            )
        )
    )
    prerequisite_by_id = {prior.id: prior for prior in earlier}
    prerequisites = [
        {
            "path_lesson_id": prerequisite_id,
            "concept_id": prerequisite_by_id[prerequisite_id].concept_id,
            "objective": prerequisite_by_id[prerequisite_id].objective,
        }
        for prerequisite_id in prerequisite_ids
        if prerequisite_id in prerequisite_by_id
    ]
    actuals = await actual_context_for_lessons(
        session, path_lesson_ids=[prior.id for prior in earlier]
    )
    return scope_contract, prior_established, prerequisites, actuals


'''
    # helpers_and_rest still has PathPreparationBlocked / StructuralPlan etc which is fine
    # but also still has class PathPreparationBlocked? No - we started at "# Fields the strict"
    # Remove unused load_chunked_state if present in helpers - it's not in helpers section.
    return header + helpers_and_rest


def build_dispatch() -> str:
    old = (SRC / "generation" / "path_preparation.py").read_text(encoding="utf-8")
    return (
        '"""Unit-path generation admission / dispatch after prepare.\n\n'
        "Owned by application.unit_lesson (D1). Historical generation.path_preparation\n"
        'is a temporary re-export shim.\n"""\n\n'
        + old
    )


def main() -> None:
    (UNIT / "contracts.py").write_text(CONTRACTS, encoding="utf-8")
    (UNIT / "status.py").write_text(STATUS, encoding="utf-8")
    (UNIT / "dispatch.py").write_text(build_dispatch(), encoding="utf-8")
    (UNIT / "prepare.py").write_text(build_prepare(), encoding="utf-8")
    (UNIT / "__init__.py").write_text(INIT, encoding="utf-8")
    (SRC / "planning" / "bridge.py").write_text(BRIDGE_SHIM, encoding="utf-8")
    (SRC / "generation" / "path_preparation.py").write_text(PATH_PREP_SHIM, encoding="utf-8")
    print("D1 move complete")


if __name__ == "__main__":
    main()

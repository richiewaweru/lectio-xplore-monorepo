"""Load the inputs for one lesson's Issues payload and manage "Mark as fine".

The Issues tab reads the same persisted advisory store as Quality Notes (the
document-QA work item's quality flags). ``collect_lesson_issues`` stays pure;
this module is the only place that touches the database for it.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from application.unit_lesson import resolve_by_path, to_identity
from core.database.models import (
    GenerationModel,
    LessonIssueDismissalModel,
    PathLessonModel,
)
from curriculum.lesson_review import LessonIssuesResponse, collect_lesson_issues
from document.shared_lesson.qa_runtime import load_run_quality_flags
from document.shared_lesson.section_index import load_run_sections

ArtifactPath = Literal["learn", "print"]


class IssueNotDismissible(ValueError):
    """The issue is unknown for this lesson output, or is not a needs-look item."""


def dismissal_scope_key(output_id: str | None, shared_document_run_id: str | None) -> str:
    """Regenerating the output or the document changes the key, so a regenerated
    lesson starts with every advisory undismissed."""
    return f"{output_id or ''}|{shared_document_run_id or ''}"


async def build_lesson_issues(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    path: ArtifactPath,
    owner_id: str,
) -> tuple[LessonIssuesResponse, str]:
    """Return the issues payload and the dismissal scope key for one lesson path."""
    realization = await resolve_by_path(session, path_lesson_id=lesson.id, path=path)
    preparation = (
        await session.get(GenerationModel, lesson.pack_id) if lesson.pack_id else None
    )
    output = (
        await session.get(GenerationModel, realization.output_id)
        if realization is not None and realization.output_id
        else None
    )
    states = [
        state
        for state in (
            preparation.chunked_state_json if preparation is not None else None,
            output.chunked_state_json if output is not None else None,
            preparation.report_json if preparation is not None else None,
            output.report_json if output is not None else None,
        )
        if isinstance(state, dict)
    ]
    documents = [
        document
        for document in (
            preparation.document_json if preparation is not None else None,
            output.document_json if output is not None else None,
        )
        if isinstance(document, dict)
    ]
    booklet_issues: list[object] = []
    for document in documents:
        raw_issues = document.get("booklet_issues")
        if isinstance(raw_issues, list):
            booklet_issues.extend(raw_issues)
        nested = document.get("document")
        if isinstance(nested, dict) and isinstance(nested.get("booklet_issues"), list):
            booklet_issues.extend(nested["booklet_issues"])
    errors = [
        error
        for error in (
            output.error if output is not None else None,
            preparation.error if preparation is not None else None,
        )
        if isinstance(error, str) and error.strip()
    ]

    # Learn and Print share one shared-document run; its flags are lesson-level
    # and are tagged with the requested path. The run id may be NULL before ready.
    run_id = (
        getattr(realization, "shared_document_run_id", None)
        or (getattr(output, "shared_document_run_id", None) if output is not None else None)
    )
    flags = (
        await load_run_quality_flags(session, run_id=run_id, owner_user_id=owner_id)
        if run_id
        else ()
    )
    sections = await load_run_sections(session, run_id=run_id, owner_user_id=owner_id)
    scope_key = dismissal_scope_key(
        realization.output_id if realization is not None else None, run_id
    )
    dismissed = set(
        (
            await session.scalars(
                select(LessonIssueDismissalModel.issue_id).where(
                    LessonIssueDismissalModel.path_lesson_id == lesson.id,
                    LessonIssueDismissalModel.path == path,
                    LessonIssueDismissalModel.scope_key == scope_key,
                )
            )
        ).all()
    )
    response = collect_lesson_issues(
        path=path,
        realization=(
            to_identity(realization).model_dump(mode="json")
            if realization is not None
            else None
        ),
        states=states,
        documents=documents,
        booklet_issues=booklet_issues,
        generation_errors=errors,
        quality_flags=[flag.model_dump(mode="json") for flag in flags],
        shared_sections=sections,
        dismissed_issue_ids=dismissed,
    )
    return response, scope_key


async def set_issue_dismissed(
    session: AsyncSession,
    *,
    lesson: PathLessonModel,
    path: ArtifactPath,
    owner_id: str,
    issue_id: str,
    dismissed: bool,
) -> LessonIssuesResponse:
    """Mark an issue as fine (or restore it) and return the refreshed payload.

    Only a current ``needs_look`` item of this lesson output can be dismissed;
    restoring an unknown id is a harmless no-op.
    """
    response, scope_key = await build_lesson_issues(
        session, lesson=lesson, path=path, owner_id=owner_id
    )
    if dismissed:
        target = next((issue for issue in response.issues if issue.id == issue_id), None)
        if target is None or not target.dismissible:
            raise IssueNotDismissible("Only advisories that need a look can be marked as fine.")
        existing = await session.scalar(
            select(LessonIssueDismissalModel.id).where(
                LessonIssueDismissalModel.path_lesson_id == lesson.id,
                LessonIssueDismissalModel.path == path,
                LessonIssueDismissalModel.issue_id == issue_id,
                LessonIssueDismissalModel.scope_key == scope_key,
            )
        )
        if existing is None:
            session.add(
                LessonIssueDismissalModel(
                    owner_user_id=owner_id,
                    path_lesson_id=lesson.id,
                    path=path,
                    issue_id=issue_id,
                    scope_key=scope_key,
                )
            )
            try:
                await session.flush()
            except IntegrityError:  # concurrent identical dismissal: already stored
                await session.rollback()
    else:
        await session.execute(
            delete(LessonIssueDismissalModel).where(
                LessonIssueDismissalModel.path_lesson_id == lesson.id,
                LessonIssueDismissalModel.path == path,
                LessonIssueDismissalModel.issue_id == issue_id,
                LessonIssueDismissalModel.scope_key == scope_key,
            )
        )
    await session.commit()
    refreshed, _ = await build_lesson_issues(
        session, lesson=lesson, path=path, owner_id=owner_id
    )
    return refreshed


__all__ = [
    "IssueNotDismissible",
    "build_lesson_issues",
    "dismissal_scope_key",
    "set_issue_dismissed",
]

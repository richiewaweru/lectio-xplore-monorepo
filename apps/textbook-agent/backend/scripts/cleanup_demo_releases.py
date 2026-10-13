"""One-off: delete every published Learn release and everything hanging off it.

Work order 38 section 4. Editable lessons, units, paths, classes, learners and
learner sessions are NOT touched. Concept states (a rebuildable projection with
no FK to releases) are reported but not deleted.

Default is a DRY RUN: per-table counts and the release list are printed, nothing
is written. Real deletion needs ``--apply`` AND ``--confirm-db <database name>``
and runs in ONE transaction.

    python scripts/cleanup_demo_releases.py --target railway
    python scripts/cleanup_demo_releases.py --target railway --apply --confirm-db <db>
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from pathlib import Path

from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Importing the models loads app settings, which insist on a JWT secret. This script never uses it.
os.environ.setdefault("JWT_SECRET_KEY", secrets.token_hex(32))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from infra.database.models import (
    ConceptEvidenceModel,
    ConceptStateModel,
    LearnAssignmentModel,
    LearnAssignmentRecipientModel,
    LearnAssignmentTargetModel,
    LearnerAttemptModel,
    LearningInstanceModel,
    LearnReleaseModel,
    LessonProgressModel,
)

R = LearnReleaseModel
A = LearnAssignmentModel
I = LearningInstanceModel


def _release_ids():
    return select(R.id)


def _assignment_ids():
    return select(A.id).where(A.learn_release_id.in_(_release_ids()))


def _instance_ids():
    return select(I.id).where(
        I.learn_release_id.in_(_release_ids()) | I.assignment_id.in_(_assignment_ids())
    )


# FK-safe order (children first). Each entry: (label, model, where-clause factory).
STEPS = [
    (
        "concept_evidence",
        ConceptEvidenceModel,
        lambda: ConceptEvidenceModel.learn_release_id.in_(_release_ids())
        | ConceptEvidenceModel.learning_instance_id.in_(_instance_ids()),
    ),
    (
        "learner_attempts",
        LearnerAttemptModel,
        lambda: LearnerAttemptModel.learning_instance_id.in_(_instance_ids()),
    ),
    (
        "lesson_progress",
        LessonProgressModel,
        lambda: LessonProgressModel.learning_instance_id.in_(_instance_ids()),
    ),
    (
        "learn_assignment_recipients",
        LearnAssignmentRecipientModel,
        lambda: LearnAssignmentRecipientModel.assignment_id.in_(_assignment_ids())
        | LearnAssignmentRecipientModel.learning_instance_id.in_(_instance_ids()),
    ),
    ("learning_instances", I, lambda: I.id.in_(_instance_ids())),
    (
        "learn_assignment_targets",
        LearnAssignmentTargetModel,
        lambda: LearnAssignmentTargetModel.assignment_id.in_(_assignment_ids()),
    ),
    ("learn_assignments", A, lambda: A.id.in_(_assignment_ids())),
    ("learn_releases", R, lambda: R.id.in_(_release_ids())),
]


async def list_releases(session: AsyncSession) -> list[tuple]:
    rows = await session.execute(
        select(R.id, R.title, R.release_number, R.path_lesson_id).order_by(
            R.editable_lesson_id, R.release_number
        )
    )
    return [tuple(r) for r in rows]


async def count_rows(session: AsyncSession) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label, model, where in STEPS:
        counts[label] = (
            await session.execute(select(func.count()).select_from(model).where(where()))
        ).scalar_one()
    return counts


async def concept_state_report(session: AsyncSession) -> dict[str, int]:
    """Concept states have no FK to releases; report how many belong to affected learners."""
    affected = select(ConceptEvidenceModel.learner_id).where(
        ConceptEvidenceModel.learn_release_id.in_(_release_ids())
        | ConceptEvidenceModel.learning_instance_id.in_(_instance_ids())
    )
    total = (await session.execute(select(func.count()).select_from(ConceptStateModel))).scalar_one()
    linked = (
        await session.execute(
            select(func.count())
            .select_from(ConceptStateModel)
            .where(ConceptStateModel.learner_id.in_(affected))
        )
    ).scalar_one()
    return {"concept_states_total": total, "concept_states_for_affected_learners": linked}


async def run_cleanup(session: AsyncSession, *, apply: bool) -> dict:
    """Everything runs in ONE transaction. Dry run only reads, then rolls back."""
    try:
        if not apply and session.get_bind().dialect.name == "postgresql":
            await session.execute(text("SET TRANSACTION READ ONLY"))
        releases = await list_releases(session)
        counts = await count_rows(session)
        states = await concept_state_report(session)
        if apply:
            for _label, model, where in STEPS:
                await session.execute(
                    delete(model).where(where()).execution_options(synchronize_session=False)
                )
            await session.commit()
        else:
            await session.rollback()
    except BaseException:
        await session.rollback()
        raise
    return {"releases": releases, "counts": counts, "concept_states": states, "applied": apply}


def _read_env_key(env_file: Path, key: str) -> str | None:
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _to_async_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


def resolve_url(target: str, env_file: Path) -> str:
    key = "DATABASE_URL_RAILWAY" if target == "railway" else "DATABASE_URL"
    url = os.environ.get(key) or _read_env_key(env_file, key)
    if not url:
        raise SystemExit(f"{key} not found in environment or {env_file.name}")
    return _to_async_url(url)


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--target", choices=["railway", "local"], required=True)
    p.add_argument("--apply", action="store_true", help="really delete (needs --confirm-db)")
    p.add_argument("--confirm-db", default=None, help="database name, must match the target")
    p.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    return p.parse_args()


def print_report(result: dict) -> None:
    print(f"\nReleases ({len(result['releases'])}):")
    for rid, title, number, path_lesson_id in result["releases"]:
        print(f"  {rid}  #{number}  path_lesson_id={path_lesson_id}  {title!r}")
    verb = "DELETED" if result["applied"] else "WOULD BE deleted"
    print(f"\nRows {verb}:")
    for label, n in result["counts"].items():
        print(f"  {label}: {n}")
    print("\nConcept states (no FK to releases, NOT deleted):")
    for label, n in result["concept_states"].items():
        print(f"  {label}: {n}")
    print("\nWRITTEN." if result["applied"] else "\nDRY RUN: nothing written.")


async def main() -> None:
    args = _parse()
    url = make_url(resolve_url(args.target, args.env_file))
    print(f"Target: {args.target}  host={url.host}  database={url.database}")
    if args.apply and args.confirm_db != url.database:
        raise SystemExit(
            f"--apply requires --confirm-db {url.database!r} (got {args.confirm_db!r}). Aborting."
        )
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            result = await run_cleanup(session, apply=args.apply)
        print_report(result)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

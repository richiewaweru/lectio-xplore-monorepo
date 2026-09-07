"""reconcile development databases already stamped 20260806_0032

Revision ID: 20260806_0032
Revises: 20260803_0031

This revision reconciles an already-stamped development database after the
original migration file was lost. Schema inspection confirmed no delta from
current ORM expectations.

Background
----------
A development database was found stamped at ``20260806_0032`` while the
repository's newest revision was ``20260803_0031``. The file that performed that
stamp exists in no commit, branch, stash, or dangling object — it was applied and
then lost before being committed. Because ``run_migrations_on_startup`` defaults
to ``True``, every backend start failed with::

    alembic.util.exc.CommandError: Can't locate revision identified by '20260806_0032'

Before writing this file the live schema was compared against the full ORM
metadata at that commit: 29 model tables against 31 database tables, with **no
missing table and no missing column**. The database was a strict superset of what
the code expects, so the lost migration left no reachable schema delta.

Why a no-op revision rather than stamping backward
--------------------------------------------------
Re-stamping the database to ``20260803_0031`` would have edited data to match the
code and left no record of what happened. Declaring the revision instead means:

* the already-stamped database resolves its own current revision and starts;
* databases still at ``0031`` advance to ``0032`` safely, because there is
  nothing to apply;
* the gap is explicit and repeatable in migration history rather than being oral
  tradition.

If a real ``20260806_0032`` is ever recovered, its operations must be reviewed
against this no-op before being reintroduced.
"""

from __future__ import annotations

revision = "20260806_0032"
down_revision = "20260803_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op: the schema delta, if any ever existed, is already present."""


def downgrade() -> None:
    """No-op: nothing was applied, so nothing can be reverted."""

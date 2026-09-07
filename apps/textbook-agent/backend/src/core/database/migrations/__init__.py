"""Compatibility shim - use `infra.database.migrations`.

Temporary (R3). Remove when all call sites import the infra path (R7).
"""

from __future__ import annotations

from infra.database.migrations import *  # noqa: F401,F403
from infra.database.migrations.runner import upgrade_database  # noqa: F401

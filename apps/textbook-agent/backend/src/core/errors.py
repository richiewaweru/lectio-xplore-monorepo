"""Compatibility shim - use `infra.errors`.

Temporary (R3). Remove when all call sites import the infra path (R7).
"""

from __future__ import annotations

from infra.errors import *  # noqa: F401,F403

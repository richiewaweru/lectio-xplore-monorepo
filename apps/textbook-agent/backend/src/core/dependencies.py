"""Compatibility shim - use `infra.dependencies`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

from infra.dependencies import *  # noqa: F401,F403

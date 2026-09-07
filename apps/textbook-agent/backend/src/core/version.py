"""Compatibility shim - use `infra.version`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

from infra.version import *  # noqa: F401,F403

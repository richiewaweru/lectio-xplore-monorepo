"""Compatibility shim - use `curriculum.compatibility`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

from curriculum.compatibility import *  # noqa: F401,F403

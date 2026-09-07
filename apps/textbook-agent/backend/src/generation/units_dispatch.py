"""Compatibility shim — use ``learn.generation.units_dispatch``.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.generation.units_dispatch import *  # noqa: F401,F403

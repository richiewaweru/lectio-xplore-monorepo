"""Compatibility shim — use ``learn.resources.component_candidates``.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.resources.component_candidates import *  # noqa: F401,F403

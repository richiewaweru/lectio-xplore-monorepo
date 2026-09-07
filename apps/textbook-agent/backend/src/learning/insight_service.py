"""Compatibility shim — use `learn.insight_service`.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.insight_service import *  # noqa: F401,F403

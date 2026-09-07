"""Compatibility shim — use `learn.runtime_service`.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.runtime_service import *  # noqa: F401,F403

"""Compatibility shim — use `learn.models`.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.models import *  # noqa: F401,F403

"""Compatibility shim package — use `learn`.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn import *  # noqa: F401,F403

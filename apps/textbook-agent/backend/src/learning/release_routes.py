"""Compatibility shim — use `learn.release_routes`.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.release_routes import *  # noqa: F401,F403

"""Compatibility shim — use `learn.pack_repository`.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

from learn.pack_repository import *  # noqa: F401,F403

"""Compatibility shim — use `learn.runtime.runtime_models`.

Temporary (C2). Remove when all call sites import the learn subdomain path (C3).
"""

from __future__ import annotations

from learn.runtime.runtime_models import *  # noqa: F401,F403

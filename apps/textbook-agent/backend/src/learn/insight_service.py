"""Compatibility shim — use `learn.analytics.insight_service`.

Temporary (C2). Remove when all call sites import the learn subdomain path (C3).
"""

from __future__ import annotations

from learn.analytics.insight_service import *  # noqa: F401,F403

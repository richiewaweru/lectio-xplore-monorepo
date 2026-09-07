"""Compatibility shim - use `curriculum.approved_items`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

from curriculum.approved_items import *  # noqa: F401,F403

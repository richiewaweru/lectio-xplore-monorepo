"""Compatibility shim - use `infra.rate_limit`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

from infra.rate_limit import *  # noqa: F401,F403

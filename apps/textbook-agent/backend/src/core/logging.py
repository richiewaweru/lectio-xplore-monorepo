"""Compatibility shim - use `infra.logging`.

Temporary (R3). Remove when all call sites import the infra path (R7).
"""

from __future__ import annotations

from infra.logging import *  # noqa: F401,F403
from infra.logging import JSONFormatter, configure_logging  # noqa: F401

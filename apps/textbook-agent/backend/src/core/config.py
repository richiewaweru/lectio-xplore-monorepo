"""Compatibility shim - use `infra.config`.

Temporary (R3). Remove when all call sites import the infra path (R7).
"""

from __future__ import annotations

from infra.config import *  # noqa: F401,F403
from infra.config import (  # noqa: F401
    Settings,
    bootstrap_environment,
    settings,
    _ENV_FILE,
    GenerationPipeline,
)

"""Compatibility shim - use `infra.config`.

Temporary (R3). Remove when all call sites import the infra path (R7).
"""

from __future__ import annotations

from infra.config import *
from infra.config import (  # noqa: F401
    _ENV_FILE,
    GenerationPipeline,
    Settings,
    bootstrap_environment,
    settings,
)

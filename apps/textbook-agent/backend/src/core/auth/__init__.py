"""Compatibility shim - use `infra.auth`.

Temporary (R3). Remove when all call sites import the infra/curriculum path (R7).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("infra.auth")
sys.modules[__name__] = _mod

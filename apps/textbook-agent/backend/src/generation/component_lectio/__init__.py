"""Compatibility shim — use ``learn.generation.component_lectio``.

Temporary (R2). Remove when all call sites import the learn path (R7).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("learn.generation.component_lectio")
sys.modules[__name__] = _mod

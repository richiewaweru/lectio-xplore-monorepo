"""Compatibility shim — use ``print.generation.whole_lesson``.

Temporary (R1). Remove when all call sites import the print path (R7).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("print.generation.whole_lesson")
sys.modules[__name__] = _mod

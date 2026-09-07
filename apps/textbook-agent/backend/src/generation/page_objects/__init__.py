"""Compatibility shim — use ``print.rendering.page_objects``.

Temporary (R1). Remove when all call sites import the print path (R7).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("print.rendering.page_objects")
sys.modules[__name__] = _mod

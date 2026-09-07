"""Compatibility shim — use ``print.http.v3_studio``.

Temporary (C2). Remove when all call sites import the print path (C3).
"""

from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("print.http.v3_studio")
sys.modules[__name__] = _mod

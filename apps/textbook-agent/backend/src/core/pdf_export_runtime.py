"""Compatibility shim - use `print.rendering.pdf.runtime`.

Temporary (R4). Remove when all call sites import the domain path (R7).
"""

from __future__ import annotations

from print.rendering.pdf.runtime import *  # noqa: F401,F403

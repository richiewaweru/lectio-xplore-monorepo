"""Compatibility shim - use `print.contracts.lectio_page`.

Temporary (R4). Remove when all call sites import the domain path (R7).
"""

from __future__ import annotations

from print.contracts.lectio_page import *  # noqa: F401,F403

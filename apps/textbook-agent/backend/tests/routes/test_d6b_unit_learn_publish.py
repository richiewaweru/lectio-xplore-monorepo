"""D6B unit Learn publish closeout — retired with Component Lectio (Phase M).

Canonical Learn production is now LearnDocument v2 via
``produce_learn_from_approved_teaching``. Reintroduce a document-path closeout
in a later phase if needed.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Phase M: component_lectio unit Learn path retired")


def test_d6b_placeholder_retired() -> None:
    assert False, "unreachable"

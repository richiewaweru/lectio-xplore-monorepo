"""A00 regression for Print table writer failure falling back to fixed stub data."""

from __future__ import annotations

import pytest

from infra.authoring import AuthoringEngineError, AuthoringTransportError
from print.rendering.page_objects import WriterContext
from print.rendering.page_objects.registry import dispatch_writer_async
from v3_blueprint.planning.models import PlannedBlock


def _table_context() -> WriterContext:
    return WriterContext(
        planned=PlannedBlock.model_validate(
            {
                "id": "b-table",
                "position": 0,
                "intent": "compare",
                "object": "table",
                "evidence": "Compare fraction representations.",
                "brief": "Create a table comparing one-half, one-third, and one-quarter.",
            }
        ),
        use_llm=True,
        section_id="s-a00",
        generation_id="gen-a00-table",
    )


@pytest.mark.asyncio
async def test_a00_table_llm_failure_surfaces_typed_failure_not_lit_leaf_stub() -> None:
    """KNOWN_ANSWER_CASES print-table-failure: no fixed Lit/Covered leaf fallback."""

    class FailingProvider:
        async def invoke(self, _call):  # noqa: ANN001
            raise AuthoringTransportError("simulated table provider timeout")

    with pytest.raises(AuthoringEngineError) as caught:
        await dispatch_writer_async(_table_context(), provider=FailingProvider())
    assert caught.value.code == "NO_COMPATIBLE_CAPABILITY"
    assert "Lit leaf" not in str(caught.value)
    assert "Covered leaf" not in str(caught.value)

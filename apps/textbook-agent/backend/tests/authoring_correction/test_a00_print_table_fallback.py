"""A00 regression for Print table writer failure falling back to fixed stub data."""

from __future__ import annotations

import pytest

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
async def test_a00_table_llm_failure_surfaces_typed_failure_not_lit_leaf_stub(monkeypatch) -> None:
    """KNOWN_ANSWER_CASES print-table-failure: no fixed Lit/Covered leaf fallback."""

    async def fail_provider_boundary(*_args: object, **_kwargs: object) -> object:
        raise TimeoutError("simulated table provider timeout")

    monkeypatch.setattr(
        "print.rendering.page_objects.registry._llm_write",
        fail_provider_boundary,
    )

    with pytest.raises(TimeoutError, match="simulated table provider timeout"):
        await dispatch_writer_async(_table_context())

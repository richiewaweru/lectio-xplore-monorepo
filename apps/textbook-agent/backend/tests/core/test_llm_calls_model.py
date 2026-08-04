from __future__ import annotations

from core.database.models import LLMCallModel


def test_llm_calls_model_includes_user_and_endpoint_host_shape() -> None:
    table = LLMCallModel.__table__

    assert table.name == "llm_calls"
    assert "trace_id" in table.c
    assert "generation_id" in table.c
    assert "user_id" in table.c
    assert "endpoint_host" in table.c
    assert "status" in table.c
    assert table.c.user_id.nullable is False
    assert table.c.endpoint_host.nullable is True
    assert table.c.trace_id.nullable is False
    assert table.c.generation_id.nullable is True
    assert any(
        foreign_key.column.table.name == "users"
        for foreign_key in table.c.user_id.foreign_keys
    )

from __future__ import annotations

import pytest

from core.database.models import UserModel
from telemetry.repositories.sql_llm_call_repo import SqlLLMCallRepository


async def _seed_user(db_session_factory, user_id: str = "llm-usage-user") -> None:
    async with db_session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name="LLM Usage User",
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_aggregate_usage_reports_avg_and_thinking_tokens(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = SqlLLMCallRepository(db_session_factory)

    await repo.save_call(
        trace_id="trace-1",
        generation_id="gen-1",
        user_id="llm-usage-user",
        caller="planner",
        slot="standard",
        family="openai_compatible",
        model_name="deepseek-v4-pro",
        endpoint_host="api.deepseek.com",
        attempt=1,
        section_id=None,
        status="succeeded",
        latency_ms=100.0,
        tokens_in=100,
        tokens_out=50,
        thinking_tokens=40,
        cost_usd=0.1,
        error=None,
        node="v3_stage1_planner",
    )
    await repo.save_call(
        trace_id="trace-2",
        generation_id="gen-2",
        user_id="llm-usage-user",
        caller="planner",
        slot="standard",
        family="openai_compatible",
        model_name="deepseek-v4-pro",
        endpoint_host="api.deepseek.com",
        attempt=1,
        section_id=None,
        status="succeeded",
        latency_ms=100.0,
        tokens_in=100,
        tokens_out=60,
        thinking_tokens=60,
        cost_usd=0.1,
        error=None,
        node="v3_stage1_planner",
    )
    await repo.save_call(
        trace_id="trace-3",
        generation_id="gen-3",
        user_id="llm-usage-user",
        caller="planner",
        slot="standard",
        family="openai_compatible",
        model_name="deepseek-v4-pro",
        endpoint_host="api.deepseek.com",
        attempt=1,
        section_id=None,
        status="succeeded",
        latency_ms=100.0,
        tokens_in=100,
        tokens_out=70,
        thinking_tokens=80,
        cost_usd=0.1,
        error=None,
        node="v3_stage1_planner",
    )

    usage = await repo.aggregate_usage(user_id="llm-usage-user")

    assert usage.total_thinking_tokens == 180
    assert usage.avg_tokens_out == 60.0
    assert usage.avg_thinking_tokens == 60.0
    assert usage.by_node[0].key == "v3_stage1_planner"
    assert usage.by_node[0].total_thinking_tokens == 180
    assert usage.by_node[0].avg_thinking_tokens == 60.0


@pytest.mark.asyncio
async def test_aggregate_usage_by_node_groups_distinct_nodes(db_session_factory) -> None:
    await _seed_user(db_session_factory)
    repo = SqlLLMCallRepository(db_session_factory)

    await repo.save_call(
        trace_id="trace-stage1",
        generation_id="gen-stage1",
        user_id="llm-usage-user",
        caller="planner",
        slot="standard",
        family="openai_compatible",
        model_name="deepseek-v4-pro",
        endpoint_host="api.deepseek.com",
        attempt=1,
        section_id=None,
        status="succeeded",
        latency_ms=100.0,
        tokens_in=100,
        tokens_out=50,
        thinking_tokens=40,
        cost_usd=0.1,
        error=None,
        node="v3_stage1_planner",
    )
    await repo.save_call(
        trace_id="trace-stage2",
        generation_id="gen-stage2",
        user_id="llm-usage-user",
        caller="planner",
        slot="standard",
        family="openai_compatible",
        model_name="deepseek-v4-pro",
        endpoint_host="api.deepseek.com",
        attempt=1,
        section_id="intro",
        status="succeeded",
        latency_ms=100.0,
        tokens_in=100,
        tokens_out=80,
        thinking_tokens=20,
        cost_usd=0.1,
        error=None,
        node="v3_stage2_expander",
    )

    usage = await repo.aggregate_usage(user_id="llm-usage-user")
    by_node = {item.key: item for item in usage.by_node}

    assert set(by_node) == {"v3_stage1_planner", "v3_stage2_expander"}
    assert by_node["v3_stage1_planner"].avg_tokens_out == 50.0
    assert by_node["v3_stage2_expander"].avg_tokens_out == 80.0

"""Repair ownership at the pydantic-ai boundary.

pydantic-ai's in-library structured-output retry appends a corrective turn to the
*same* message history, so the model's own invalid reply is replayed to the
provider. On DeepSeek a reasoning-only reply has empty ``content``, and replaying
it returns HTTP 400 "Invalid assistant message: content or tool_calls must be
set" — the observed planning_forms failure.

Every constrained planner therefore disables that retry and owns repair in its
own outer loop. Call sites without such a loop must keep the library default.
"""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from pydantic_ai import Agent

from planning import agents
from planning.whole_lesson import form_agent, teaching_agent
from v3_execution import llm_helpers


class _Probe(BaseModel):
    value: str = ""


def test_no_output_retry_constant_disables_only_output_retries() -> None:
    default = Agent(model="test", output_type=_Probe)
    constrained = Agent(model="test", output_type=_Probe, retries=llm_helpers.NO_OUTPUT_RETRY)

    assert default._max_output_retries == 1
    assert constrained._max_output_retries == 0
    # Tool retries are a separate budget and must be left alone.
    assert constrained._max_tool_retries == default._max_tool_retries


def test_constrained_planner_modules_import_the_shared_constant() -> None:
    """Each site must use the shared constant, not a local literal that can drift."""
    for module in (agents, form_agent, teaching_agent):
        assert module.NO_OUTPUT_RETRY is llm_helpers.NO_OUTPUT_RETRY


def test_run_json_agent_delegates_to_structured_agent_with_output_retry() -> None:
    """Outer repair is owned by run_llm; pydantic-ai output retry stays enabled."""
    source = inspect.getsource(llm_helpers.run_json_agent)
    assert "run_structured_agent" in source
    assert 'retries={"output": 1}' in source


async def _assert_agent_disables_output_retry(module: object, call: object) -> None:
    captured: dict = {}

    class _SpyAgent:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    async def _stop(**_kwargs: object) -> None:
        raise RuntimeError("stop after construction")

    with patch.object(module, "Agent", _SpyAgent), patch.object(module, "run_llm", _stop):
        with pytest.raises(RuntimeError, match="stop after construction"):
            await call()

    assert captured["retries"] == {"output": 0}


async def test_structural_planner_agent_disables_output_retry() -> None:
    await _assert_agent_disables_output_retry(
        agents,
        lambda: agents._run_structured(
            node="v2_path_structural_planner",
            caller="test",
            output_type=_Probe,
            system_prompt="prompt",
            user_payload={},
            trace_id="t",
        ),
    )


async def test_form_planner_agent_disables_output_retry() -> None:
    await _assert_agent_disables_output_retry(
        form_agent,
        lambda: form_agent._call_form_model(
            prompt="prompt",
            user_payload={},
            trace_id="t",
            generation_id=None,
        ),
    )


async def test_teaching_planner_agent_disables_output_retry() -> None:
    await _assert_agent_disables_output_retry(
        teaching_agent,
        lambda: teaching_agent._call_teaching_model(
            prompt="prompt",
            user_payload={},
            trace_id="t",
            generation_id=None,
        ),
    )

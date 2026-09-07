"""Shared launch boundary for Component Lectio execution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from learn.generation.component_lectio.service import run_component_lectio_execution
from v3_blueprint.planning.models import adapt_legacy_structural_plan
from v3_blueprint.planning.persistence import load_chunked_state
from learn.generation.contracts import GenerationInputForm as V3InputForm
from learn.generation.contracts import GenerationSignalSummary as V3SignalSummary

EmitEvent = Callable[[str, dict[str, Any]], Awaitable[None]]


async def launch_component_lectio(
    *, generation_id: str, emit_event: EmitEvent | None = None, title: str | None = None
) -> dict[str, Any]:
    """Load persisted context and execute Component Lectio without Studio routing."""
    state = await load_chunked_state(generation_id)
    plan_raw = state.get("structural_plan")
    context = state.get("context")
    if not isinstance(plan_raw, dict) or not isinstance(context, dict):
        raise ValueError("Persisted Component Lectio context is incomplete")
    signals_raw = context.get("signals")
    form_raw = context.get("form")
    resource_spec = context.get("resource_spec")
    if (
        not isinstance(signals_raw, dict)
        or not isinstance(form_raw, dict)
        or not isinstance(resource_spec, dict)
    ):
        raise ValueError("Persisted Component Lectio context is incomplete")
    signals = V3SignalSummary.model_validate(signals_raw)
    form = V3InputForm.model_validate(form_raw)
    display_title = title or state.get("display_title") or form.topic
    return await run_component_lectio_execution(
        generation_id=generation_id,
        plan=adapt_legacy_structural_plan(
            plan_raw, source=f"generation:{generation_id}:component_lectio"
        ),
        signals=signals,
        form=form,
        resource_spec=resource_spec,
        emit_event=emit_event,
        title=display_title,
    )


__all__ = ["launch_component_lectio"]

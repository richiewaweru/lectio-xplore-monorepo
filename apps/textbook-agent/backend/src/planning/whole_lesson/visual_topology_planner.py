"""Single-attempt typed planner for visual topology decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from core.llm.runner import RetryPolicy, run_llm
from planning.llm_contract_errors import is_transport_error
from planning.whole_lesson.visual_topology import (
    TopologyPlanV1,
    TopologyValidationError,
    validate_topology_plan,
)
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V3_VISUAL_TOPOLOGY_PLANNER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent


class TopologyPlannerRecoverableError(RuntimeError):
    """Provider timeout/transport or invalid topology; safe to retry upstream."""

    code = "TOPOLOGY_PLANNER_RECOVERABLE"

    def __init__(self, reason: str, *, cause: BaseException | None = None):
        self.reason = reason
        self.cause = cause
        super().__init__(reason)


@dataclass(frozen=True)
class TopologyPlannerMetadata:
    generation_id: str
    request_id: str
    trace_id: str
    node: str
    schema_version: str
    source_sha256: str
    plan_sha256: str
    attempt: int = 1


@dataclass(frozen=True)
class TopologyPlannerResult:
    plan: TopologyPlanV1
    metadata: TopologyPlannerMetadata
    raw_response: str


def _canonical_source(source: dict[str, Any]) -> str:
    # Persisted source only: caller supplies this already-authoritative snapshot.
    return json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _prompt(source: dict[str, Any], request: dict[str, Any]) -> str:
    return (
        "Choose only the topology relationships for the persisted visual source.\n"
        "Do not invent labels, evidence, prose, IDs, cues, or exclusions.\n"
        "Use the exact IDs supplied in SOURCE and return JSON matching TopologyPlanV1.\n"
        "Every source label ID must appear exactly once in labels.\n\n"
        "SOURCE\n"
        + _canonical_source(source)
        + "\n\nREQUEST\n"
        + json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


async def run_visual_topology_planner(
    request: dict[str, Any],
    persisted_source: dict[str, Any],
    *,
    generation_id: str,
    request_id: str,
    trace_id: str | None = None,
) -> TopologyPlannerResult:
    """Run one STANDARD Sonnet call and validate before returning anything."""

    node = V3_VISUAL_TOPOLOGY_PLANNER
    source_json = _canonical_source(persisted_source)
    source_sha = hashlib.sha256(source_json.encode("utf-8")).hexdigest()
    effective_trace = trace_id or f"native-visual:{generation_id}:{request_id}:topology:v1"
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node,
        output_type=TopologyPlanV1,
    )
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=(
            "Return only a TopologyPlanV1 JSON object. No renderable free text. "
            "Use closed enums and persisted IDs only."
        ),
        retries=NO_OUTPUT_RETRY,
    )
    try:
        result = await run_llm(
            trace_id=effective_trace,
            caller=node,
            generation_id=generation_id,
            agent=agent,
            user_prompt=_prompt(persisted_source, request),
            model=model,
            slot=get_v3_slot(node),
            spec=spec,
            node=node,
            model_settings=get_v3_model_settings(node),
            retry_policy=RetryPolicy(max_attempts=1, call_timeout_seconds=60.0),
            structured_context=structured_context,
        )
        output = result.output
        raw_text = (
            output.model_dump_json()
            if hasattr(output, "model_dump_json")
            else json.dumps(output, default=str, sort_keys=True)
        )
        plan = validate_topology_plan(output, source=persisted_source)
    except TopologyValidationError as exc:
        raise TopologyPlannerRecoverableError("invalid topology output", cause=exc) from exc
    except Exception as exc:
        # No persistence/render happens in this function. Typed transport and timeout
        # failures are recoverable; all provider failures are conservatively recoverable
        # for this pre-persistence planning node.
        if is_transport_error(exc) or isinstance(exc, (TimeoutError,)):
            raise TopologyPlannerRecoverableError("topology provider unavailable", cause=exc) from exc
        raise TopologyPlannerRecoverableError("topology planner failed", cause=exc) from exc

    plan_sha = hashlib.sha256(
        json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    metadata = TopologyPlannerMetadata(
        generation_id=generation_id,
        request_id=request_id,
        trace_id=effective_trace,
        node=node,
        schema_version="topology-plan-v1",
        source_sha256=source_sha,
        plan_sha256=plan_sha,
    )
    return TopologyPlannerResult(plan=plan, metadata=metadata, raw_response=raw_text)


__all__ = [
    "TopologyPlannerMetadata",
    "TopologyPlannerRecoverableError",
    "TopologyPlannerResult",
    "run_visual_topology_planner",
]

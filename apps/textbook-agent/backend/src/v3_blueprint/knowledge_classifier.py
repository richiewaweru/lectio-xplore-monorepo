from __future__ import annotations

from pathlib import Path
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V3_KNOWLEDGE_TYPE_CLASSIFIER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent


class KnowledgeTypeClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_knowledge_type: Literal["procedural", "conceptual", "factual", "evaluative"]
    secondary_demand: Literal["procedural", "conceptual", "factual", "evaluative"] | None
    confidence: Literal["high", "medium", "low"]
    success_test: str
    note: str | None

    @property
    def requires_teacher_review(self) -> bool:
        return self.confidence == "low"


def classifier_prompt() -> str:
    path = Path(__file__).resolve().parents[2] / "resources" / "knowledge-type-classifier-v1.txt"
    return path.read_text(encoding="utf-8")


async def classify_knowledge_type(
    objective: str,
    *,
    trace_id: str | None = None,
    generation_id: str | None = None,
) -> KnowledgeTypeClassification:
    if not objective.strip():
        raise ValueError("Objective must not be empty")
    node = V3_KNOWLEDGE_TYPE_CLASSIFIER
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=node,
        output_type=KnowledgeTypeClassification,
    )
    slot = get_v3_slot(node)
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=classifier_prompt(),
        retries=NO_OUTPUT_RETRY,
    )
    result = await run_llm(
        trace_id=trace_id or generation_id or str(uuid.uuid4()),
        caller="v2_knowledge_type_classifier",
        generation_id=generation_id,
        agent=agent,
        user_prompt=f"Learning objective:\n{objective}",
        model=model,
        slot=slot,
        spec=spec,
        node=node,
        model_settings=get_v3_model_settings(node),
        retry_policy=RetryPolicy(
            max_attempts=1,
            call_timeout_seconds=float(settings.v3_timeout_stage1_seconds),
        ),
        structured_context=structured_context,
    )
    if isinstance(result.output, KnowledgeTypeClassification):
        return result.output
    if hasattr(result.output, "model_dump"):
        return KnowledgeTypeClassification.model_validate(result.output.model_dump())
    return KnowledgeTypeClassification.model_validate(result.output)

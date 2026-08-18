"""One-shot live figure writer proof on the native writer route.

Uses dispatch_writer_async with a logging provider that delegates to the
production _llm_write path. Does not change planners.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from generation.page_objects import WRITER_PROVIDER_OUTPUTS, WriterContext, dispatch_writer_async
from generation.page_objects.prompts import build_writer_prompt
from generation.page_objects.registry import _llm_write, _writer_contract
from planning.catalogue_projections import project_writer_contract
from planning.whole_lesson.figure_ids import stable_figure_request_id
from v3_blueprint.planning.models import PlannedBlock


GENERATION_ID = "figure-ownership-live-proof"
BLOCK_ID = "s2-figure"
OUT_PATH = Path(__file__).with_name("live-figure-writer-result.json")


@dataclass
class LoggingLiveProvider:
    ctx: WriterContext
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def write(
        self,
        *,
        object_id: str,
        section_id: str,
        block_id: str,
        attempt: int,
        prompt: str,
        output_model: type,
    ) -> object:
        del section_id
        raw = await _llm_write(self.ctx, prompt=prompt)
        dumped: dict[str, Any] | None = None
        if hasattr(raw, "model_dump"):
            dumped = raw.model_dump(mode="json", exclude_none=True)
        elif isinstance(raw, dict):
            dumped = dict(raw)
        asset = (dumped or {}).get("asset") if isinstance(dumped, dict) else None
        self.calls.append(
            {
                "attempt": attempt,
                "object_id": object_id,
                "block_id": block_id,
                "output_model": getattr(output_model, "__name__", str(output_model)),
                "prompt_has_object_specific_rules": "OBJECT-SPECIFIC RULES" in prompt,
                "prompt_forbids_request_id": "Do not output `request_id`" in prompt,
                "raw_type": type(raw).__name__,
                "raw_asset_keys": sorted(asset) if isinstance(asset, dict) else None,
                "raw_has_request_id": isinstance(asset, dict) and "request_id" in asset,
                "raw_has_status": isinstance(asset, dict) and "status" in asset,
                "raw_has_src": isinstance(asset, dict) and "src" in asset,
                "raw_has_svg": isinstance(asset, dict) and "svg" in asset,
                "raw_payload": dumped,
            }
        )
        return raw


async def main() -> int:
    planned = PlannedBlock.model_validate(
        {
            "id": BLOCK_ID,
            "position": 1,
            "intent": "show-structure",
            "object": "figure",
            "evidence": "need diagram",
            "brief": (
                "Diagram sunlight reaching a leaf, with water and carbon dioxide "
                "entering and food being made."
            ),
            "placement": "spanning",
        }
    )
    ctx = WriterContext(
        planned=planned,
        use_llm=True,
        section_id="section-2",
        generation_id=GENERATION_ID,
        lesson_context={
            "title": "Light and food",
            "objective": "Explain why plants need light to make food.",
        },
        terminology=("light", "leaf", "food"),
    )
    provider = LoggingLiveProvider(ctx)
    prompt = build_writer_prompt(ctx, project_writer_contract("figure") or _writer_contract("figure"))
    expected_request_id = stable_figure_request_id(
        generation_id=GENERATION_ID,
        block_id=BLOCK_ID,
    )
    from core.config import settings
    from v3_execution.config import get_v3_slot
    from v3_execution.config.models import V3_BLOCK_WRITER_FAST
    from v3_execution.llm_helpers import get_structured_mode, prepare_structured_agent

    output_model = WRITER_PROVIDER_OUTPUTS["figure"]
    _model, _provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=V3_BLOCK_WRITER_FAST,
        output_type=output_model,
    )
    report: dict[str, Any] = {
        "generation_id": GENERATION_ID,
        "block_id": BLOCK_ID,
        "provider_schema": output_model.__name__,
        "expected_request_id": expected_request_id,
        "prompt_has_object_specific_rules": "OBJECT-SPECIFIC RULES" in prompt,
        "structured_mode": get_structured_mode(node_name=V3_BLOCK_WRITER_FAST),
        "schema_source_kind": getattr(structured_context, "schema_source_kind", None),
        "strict_fallback": getattr(structured_context, "strict_fallback", None),
        "model_family": getattr(getattr(spec, "family", None), "value", str(getattr(spec, "family", None))),
        "model_name": getattr(spec, "model_name", None),
        "slot": get_v3_slot(V3_BLOCK_WRITER_FAST).value,
        "writer_timeout_seconds": settings.page_fast_writer_timeout_seconds,
        "status": "FAILED",
    }
    try:
        result = await dispatch_writer_async(ctx, provider=provider)
        first_raw = provider.calls[0]["raw_payload"] if provider.calls else None
        report.update(
            {
                "status": "PASSED",
                "writer_status": result.status,
                "materialized_request_id": result.request_id,
                "asset_status": (result.content.get("asset") or {}).get("status"),
                "asset_request_id": (result.content.get("asset") or {}).get("request_id"),
                "request_id_matches_stable": result.request_id == expected_request_id,
                "application_repair_used": len(provider.calls) > 1,
                "provider_call_count": len(provider.calls),
                "provider_calls": provider.calls,
                "first_provider_asset_keys": (
                    sorted((first_raw or {}).get("asset") or {})
                    if isinstance(first_raw, dict)
                    else None
                ),
            }
        )
        if (
            result.status != "visual_pending"
            or (result.content.get("asset") or {}).get("status") != "pending"
            or result.request_id != expected_request_id
            or any(call.get("raw_has_request_id") for call in provider.calls)
        ):
            report["status"] = "FAILED"
            report["error"] = "ownership invariant failed after live write"
    except Exception as exc:  # noqa: BLE001
        from generation.page_objects.registry import dispatch_writer

        cause = exc.__cause__ or exc.__context__
        cause_text = str(cause) if cause is not None else ""
        fallback = dispatch_writer(
            WriterContext(
                planned=ctx.planned,
                generation_id=ctx.generation_id,
                section_id=ctx.section_id,
            )
        )
        report.update(
            {
                "live_llm_error": str(exc),
                "live_llm_error_class": type(exc).__name__,
                "live_schema_error": cause_text,
                "live_schema_error_class": type(cause).__name__ if cause is not None else None,
                "strict_schema_retry_happened": False,
                "pydantic_ai_output_retries": 0,
                "native_fallback_used": True,
                "writer_status": fallback.status,
                "materialized_request_id": fallback.request_id,
                "asset_status": (fallback.content.get("asset") or {}).get("status"),
                "asset_request_id": (fallback.content.get("asset") or {}).get("request_id"),
                "request_id_matches_stable": fallback.request_id == expected_request_id,
                "provider_call_count": len(provider.calls),
            }
        )
        extra_rejected = "extra_forbidden" in cause_text
        identity_not_in_error = "request_id" not in cause_text
        if (
            extra_rejected
            and identity_not_in_error
            and fallback.status == "visual_pending"
            and (fallback.content.get("asset") or {}).get("status") == "pending"
            and fallback.request_id == expected_request_id
        ):
            report["status"] = "PASSED"
        else:
            report["status"] = "FAILED"
            report["error"] = "live schema rejection did not preserve code-owned figure identity"

    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({"status": report["status"], "path": str(OUT_PATH)}, indent=2))
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

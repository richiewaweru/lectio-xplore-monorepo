"""Scripted mock writer provider for deterministic native E2E tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class TransportError(RuntimeError):
    """Transport-like failure raised by scripted scenarios."""


@dataclass
class ScriptedCallRecord:
    scenario: str
    section_id: str
    block_id: str
    object_id: str
    attempt: int
    prompt: str
    prompt_hash: str
    result_kind: str
    raw_result: object | None = None
    exception: str | None = None


@dataclass
class ScriptedWriterProvider:
    """Deterministic no-network writer used by native E2E / repair tests."""

    scenarios: dict[str, Any] = field(default_factory=dict)
    scenario_name: str = "valid_first_time"
    default_valid: dict[str, Any] = field(default_factory=dict)
    max_calls: int | None = None
    calls: list[ScriptedCallRecord] = field(default_factory=list)
    _attempt_counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_yaml_dict(
        cls,
        payload: dict[str, Any],
        *,
        scenario_name: str,
        default_valid: dict[str, Any] | None = None,
    ) -> ScriptedWriterProvider:
        raw = payload.get("scenarios") if isinstance(payload, dict) else None
        if raw is None:
            raw = payload
        if isinstance(raw, list):
            scenarios = {
                str(item["name"]): item
                for item in raw
                if isinstance(item, dict) and item.get("name")
            }
        elif isinstance(raw, dict):
            # Support either {name: {...}} or {"scenarios": [..]} nested once.
            if "scenarios" in raw and isinstance(raw["scenarios"], list):
                scenarios = {
                    str(item["name"]): item
                    for item in raw["scenarios"]
                    if isinstance(item, dict) and item.get("name")
                }
            else:
                scenarios = raw
        else:
            scenarios = {}
        return cls(
            scenarios=scenarios,
            scenario_name=scenario_name,
            default_valid=default_valid or {},
        )

    def _scenario(self) -> dict[str, Any]:
        scenarios = self.scenarios
        if "scenarios" in scenarios and isinstance(scenarios["scenarios"], list):
            for item in scenarios["scenarios"]:
                if isinstance(item, dict) and item.get("name") == self.scenario_name:
                    return item
            return {}
        found = scenarios.get(self.scenario_name)
        return found if isinstance(found, dict) else {}

    def _response_for(self, *, block_id: str, attempt: int) -> dict[str, Any] | None:
        scenario = self._scenario()
        responses = scenario.get("responses") or {}
        for key in (block_id, "*", "default"):
            steps = responses.get(key)
            if not isinstance(steps, list):
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                if int(step.get("attempt") or 0) == attempt:
                    return step
        return None

    def _valid_for(self, object_id: str) -> object:
        if object_id in self.default_valid:
            return self.default_valid[object_id]
        # Minimal valid payloads per form when scenario says mode: valid.
        defaults: dict[str, Any] = {
            "prose": {"paragraphs": ["Valid prose."]},
            "list": {
                "style": "unordered",
                "items": [{"text": "One"}, {"text": "Two"}],
            },
            "table": {
                "columns": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                "rows": [{"cells": {"a": "1", "b": "2"}}],
            },
            "figure": {
                "asset": {"kind": "image"},
                "alt_text": "A pending figure",
                "caption": "Caption",
            },
            "aside": {"label": "Note", "body": "Aside body."},
            "worked-example": {
                "problem": "Problem",
                "steps": [{"text": "Step 1"}],
                "answer": "Answer",
            },
            "questions": {
                "items": [{"id": "q1", "prompt": "Why?"}],
            },
            "choices": {
                "stem": "Which?",
                "options": [
                    {"letter": "A", "text": "One"},
                    {"letter": "B", "text": "Two"},
                ],
            },
        }
        return defaults[object_id]

    async def write(
        self,
        *,
        object_id: str,
        section_id: str,
        block_id: str,
        attempt: int,
        prompt: str,
        output_model: type[BaseModel],
    ) -> object:
        if self.max_calls is not None and len(self.calls) >= self.max_calls:
            raise RuntimeError(f"exceeded max_calls={self.max_calls}")

        key = f"{section_id}:{block_id}"
        self._attempt_counts[key] = self._attempt_counts.get(key, 0) + 1
        effective_attempt = attempt or self._attempt_counts[key]

        scenario = self._scenario()
        delays = scenario.get("section_delays_ms") or {}
        delay_ms = delays.get(section_id)
        if delay_ms:
            await asyncio.sleep(float(delay_ms) / 1000.0)

        step = self._response_for(block_id=block_id, attempt=effective_attempt)
        mode = (step or {}).get("mode") or "valid"
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        try:
            if mode == "raise":
                exc_name = str((step or {}).get("exception") or "TransportError")
                if exc_name == "TransportError":
                    raise TransportError("scripted transport failure")
                raise RuntimeError(exc_name)
            if mode == "raw":
                value = (step or {}).get("value", "")
                result: object = value
                result_kind = "raw"
            elif mode == "dict":
                result = (step or {}).get("value") or {}
                result_kind = "dict"
            else:
                # "valid" emulates a successful structured-provider response:
                # it must pass the exact provider-facing model the real LLM sees.
                #
                # "dict" and "raw" intentionally bypass this validation so tests
                # can still inject malformed model output and exercise the
                # application's validation/repair boundary.
                result = output_model.model_validate(self._valid_for(object_id))
                result_kind = "valid"
            self.calls.append(
                ScriptedCallRecord(
                    scenario=self.scenario_name,
                    section_id=section_id,
                    block_id=block_id,
                    object_id=object_id,
                    attempt=effective_attempt,
                    prompt=prompt,
                    prompt_hash=prompt_hash,
                    result_kind=result_kind,
                    raw_result=result,
                )
            )
            return result
        except Exception as exc:
            self.calls.append(
                ScriptedCallRecord(
                    scenario=self.scenario_name,
                    section_id=section_id,
                    block_id=block_id,
                    object_id=object_id,
                    attempt=effective_attempt,
                    prompt=prompt,
                    prompt_hash=prompt_hash,
                    result_kind="exception",
                    exception=type(exc).__name__,
                )
            )
            raise

    def call_count(self) -> int:
        return len(self.calls)

    def prompts(self) -> list[str]:
        return [call.prompt for call in self.calls]

    def repair_prompts(self) -> list[str]:
        return [
            call.prompt
            for call in self.calls
            if "previous_invalid_output" in call.prompt
            or "validation_errors" in call.prompt
        ]

    def evidence(self) -> list[dict[str, Any]]:
        return [
            {
                "scenario": call.scenario,
                "section_id": call.section_id,
                "block_id": call.block_id,
                "object": call.object_id,
                "attempt": call.attempt,
                "result_kind": call.result_kind,
                "prompt_hash": call.prompt_hash,
                "exception": call.exception,
            }
            for call in self.calls
        ]

    def dump_calls_json(self) -> str:
        return json.dumps(self.evidence(), indent=2, sort_keys=True)

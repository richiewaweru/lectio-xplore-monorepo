from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReviewSeverity = Literal["info", "warning", "blocking"]
RepairTargetKind = Literal["node", "task", "figure"]


class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: ReviewSeverity = "blocking"
    path: Literal["print", "learn", "shared", "sourcebook"] | None = None
    node_id: str | None = None
    teaching_block_id: str | None = None
    shared_task_id: str | None = None
    figure_id: str | None = None
    teaching_block_ids: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    sourcebook_refs: list[str] = Field(default_factory=list)
    repair_instruction: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    @property
    def blocking(self) -> bool:
        return self.severity == "blocking"


class RepairTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: RepairTargetKind = "node"
    target_kind: Literal["document_node", "shared_task", "figure_asset"] | None = None
    target_id: str = Field(min_length=1)
    issue_codes: list[str] = Field(default_factory=list)
    instruction: str = Field(min_length=1)
    immutable_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_target_kind(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        target_kind = data.get("target_kind")
        if "kind" not in data and target_kind:
            data["kind"] = {
                "document_node": "node",
                "shared_task": "task",
                "figure_asset": "figure",
            }.get(str(target_kind), "node")
        return data

class CoherenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Literal["print", "learn"]
    teaching_plan_id: str = ""
    teaching_plan_revision: int = Field(default=1, ge=1)
    teaching_plan_hash: str = ""
    deterministic_issues: list[ReviewIssue] = Field(default_factory=list)
    semantic_issues: list[ReviewIssue] = Field(default_factory=list)
    repair_targets: list[RepairTarget] = Field(default_factory=list)
    repair_attempts: int = Field(default=0, ge=0)
    reviewed: bool = False
    status: Literal["pass", "repair_required"] = "pass"
    issues: list[ReviewIssue] = Field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return any(issue.blocking for issue in self.issues)

    @model_validator(mode="after")
    def _normalize_status(self) -> CoherenceReport:
        combined = [*self.deterministic_issues, *self.semantic_issues]
        if self.issues:
            combined = [*self.issues, *combined]
        self.issues = combined
        self.status = "repair_required" if self.blocking else "pass"
        return self


class RepairEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Literal["print", "learn"]
    attempt: int = Field(ge=1)
    target: RepairTarget
    issue_codes: list[str] = Field(default_factory=list)
    status: Literal["started", "completed", "failed"]
    message: str = ""

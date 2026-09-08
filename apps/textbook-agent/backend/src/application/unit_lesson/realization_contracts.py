"""Native realization identity contracts (P03)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from learn.resources.native_policy import LEARN_NATIVE_POLICY_BODY
from print.resources.native_policy import PRINT_NATIVE_POLICY_BODY

NativePath = Literal["print", "learn"]
RealizationStatus = Literal[
    "queued",
    "selecting",
    "writing",
    "validating",
    "assembling",
    "awaiting_assets",
    "exporting",
    "editing",
    "published",
    "ready",
    "stale",
    "read_only",
    "failed_recoverable",
    "failed_terminal",
]

DEFAULT_VARIANT_ID = "everyone"
LEGACY_AMBIGUOUS_VARIANT = "legacy-ambiguous"

# Versioned native admission policies. Hash changes invalidate only that path.
# Bodies live with Print/Learn owners; this module re-exports for admission.
PRINT_NATIVE_POLICY: dict[str, Any] = PRINT_NATIVE_POLICY_BODY
LEARN_NATIVE_POLICY: dict[str, Any] = LEARN_NATIVE_POLICY_BODY

PRINT_PACKAGE_CONTRACT: dict[str, Any] = {
    "package": "@lectio/page",
    "contract_version": "1.1.0",
}
LEARN_PACKAGE_CONTRACT: dict[str, Any] = {
    "package": "@lectio/learn",
    "contract_version": "1.0.0",
}


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def policy_for(path: NativePath) -> tuple[str, str]:
    policy = PRINT_NATIVE_POLICY if path == "print" else LEARN_NATIVE_POLICY
    return str(policy["version"]), canonical_hash(policy)


def package_contract_for(path: NativePath) -> tuple[str, str]:
    contract = PRINT_PACKAGE_CONTRACT if path == "print" else LEARN_PACKAGE_CONTRACT
    return str(contract["contract_version"]), canonical_hash(contract)


def teaching_plan_hash(plan: dict[str, Any] | None, *, preparation_hash: str | None = None) -> str:
    if preparation_hash:
        return preparation_hash
    return canonical_hash(plan or {})


class RealizationIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    realization_id: str
    path: NativePath
    teaching_plan_id: str
    teaching_plan_revision: int = Field(ge=1)
    teaching_plan_hash: str
    variant_id: str = DEFAULT_VARIANT_ID
    native_policy_version: str
    native_policy_hash: str
    package_contract_version: str
    package_contract_hash: str
    realization_revision: int = Field(ge=1)
    status: RealizationStatus
    output_id: str | None = None
    error_summary: str | None = None
    pack_id: str | None = None
    preparation_generation_id: str | None = None
    open_href: str | None = None


class RequestOutputsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_version_id: str
    path_revision: int
    paths: list[NativePath] = Field(min_length=1)
    teaching_plan_id: str
    teaching_plan_revision: int = Field(ge=1)
    teaching_plan_hash: str
    variant_id: str = DEFAULT_VARIANT_ID
    preparation_generation_id: str | None = None
    # Optional overrides for gate/policy tests — production omits these.
    native_policy_version: str | None = None
    native_policy_hash: str | None = None
    package_contract_version: str | None = None
    package_contract_hash: str | None = None


class RealizationRetryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path_version_id: str
    path_revision: int


__all__ = [
    "DEFAULT_VARIANT_ID",
    "LEGACY_AMBIGUOUS_VARIANT",
    "LEARN_NATIVE_POLICY",
    "LEARN_PACKAGE_CONTRACT",
    "NativePath",
    "PRINT_NATIVE_POLICY",
    "PRINT_PACKAGE_CONTRACT",
    "RealizationIdentity",
    "RealizationRetryBody",
    "RealizationStatus",
    "RequestOutputsBody",
    "canonical_hash",
    "package_contract_for",
    "policy_for",
    "teaching_plan_hash",
]

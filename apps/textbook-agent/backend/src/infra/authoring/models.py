from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping, Protocol

AuthoringMode = Literal["generate", "convert-approved"]
AuthoringFailureCode = Literal[
    "MISSING_AUTHORING_DEFINITION",
    "MISSING_AUTHORING_INPUT",
    "INCOMPATIBLE_APPROVED_ITEM",
    "INVALID_PAYLOAD",
    "NO_COMPATIBLE_CAPABILITY",
    "REPAIR_EXHAUSTED",
]


@dataclass(frozen=True)
class AuthoringValidationError:
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


@dataclass(frozen=True)
class AuthoringDefinition:
    capability_id: str
    native_path: str
    modes: tuple[AuthoringMode, ...]
    instructions: str
    payload_schema: Mapping[str, Any]
    required_inputs: tuple[str, ...] = ()
    validator_refs: tuple[str, ...] = ()
    converter_ref: str | None = None
    definition_hash: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthoringRequest:
    work_order_id: str
    definition: AuthoringDefinition | None
    scoped_request: Mapping[str, Any]
    inputs: Mapping[str, Any]
    teaching_revision: int
    source_identities: tuple[str, ...] = ()
    mode: AuthoringMode | None = None
    approved_item: Mapping[str, Any] | None = None
    trace_id: str | None = None
    generation_id: str | None = None


@dataclass(frozen=True)
class AuthoringProvenance:
    work_order_id: str
    source_identities: tuple[str, ...]
    teaching_revision: int
    definition_hash: str
    input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_order_id": self.work_order_id,
            "source_identities": list(self.source_identities),
            "teaching_revision": self.teaching_revision,
            "definition_hash": self.definition_hash,
            "input_hash": self.input_hash,
        }


@dataclass(frozen=True)
class AuthoringResult:
    work_order_id: str
    capability_id: str
    native_path: str
    mode: AuthoringMode
    payload: dict[str, Any]
    provenance: AuthoringProvenance
    transport_attempts: int
    repair_attempts: int


@dataclass(frozen=True)
class AuthoringProviderCall:
    work_order_id: str
    capability_id: str
    native_path: str
    mode: AuthoringMode
    attempt: int
    is_repair: bool
    prompt: str
    output_schema: Mapping[str, Any]


class AuthoringProvider(Protocol):
    async def invoke(self, call: AuthoringProviderCall) -> Any: ...


Validator = Callable[
    [AuthoringDefinition, AuthoringRequest, Mapping[str, Any]],
    list[AuthoringValidationError] | Awaitable[list[AuthoringValidationError] | None] | None,
]
Converter = Callable[[AuthoringDefinition, AuthoringRequest], Mapping[str, Any]]


class AuthoringEngineError(RuntimeError):
    def __init__(
        self,
        code: AuthoringFailureCode,
        message: str,
        *,
        stage: str,
        retryable: bool = False,
        errors: list[AuthoringValidationError] | None = None,
        provenance: AuthoringProvenance | None = None,
        transport_attempts: int = 0,
        repair_attempts: int = 0,
    ) -> None:
        self.code = code
        self.stage = stage
        self.retryable = retryable
        self.errors = list(errors or [])
        self.provenance = provenance
        self.transport_attempts = transport_attempts
        self.repair_attempts = repair_attempts
        super().__init__(f"{code}: {message}")

    def to_failure_record(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stage": self.stage,
            "retryable": self.retryable,
            "errors": [error.to_dict() for error in self.errors],
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "transport_attempts": self.transport_attempts,
            "repair_attempts": self.repair_attempts,
        }


class AuthoringTransportError(RuntimeError):
    """Retryable transport/provider boundary failure."""

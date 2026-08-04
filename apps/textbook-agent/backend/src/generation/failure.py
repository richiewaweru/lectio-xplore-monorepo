from dataclasses import dataclass

from pydantic_ai.exceptions import UserError

from core.errors import (
    PipelineError,
    ProviderConformanceError,
    ProviderRequestError,
)


@dataclass(frozen=True)
class GenerationFailureClassification:
    error_type: str
    error_code: str | None = None


_PROVIDER_CONFIGURATION_ERROR_CODE = "provider_configuration_failed"


def _is_provider_configuration_error_message(message: str) -> bool:
    normalized = message.lower()
    return (
        "api_key" in normalized
        or "api key" in normalized
        or "expects env var" in normalized
        or "environment variable" in normalized
        or ("env var" in normalized and "not set" in normalized)
        or "provider configuration" in normalized
    )


def classify_generation_failure(
    error: Exception | str,
) -> GenerationFailureClassification:
    if isinstance(error, ProviderRequestError):
        return GenerationFailureClassification(
            error_type="provider_error",
            error_code="provider_request_failed",
        )
    if isinstance(error, ProviderConformanceError):
        return GenerationFailureClassification(
            error_type="provider_error",
            error_code="provider_conformance_failed",
        )
    if isinstance(error, PipelineError):
        return GenerationFailureClassification(
            error_type="pipeline_error",
            error_code="pipeline_failed",
        )
    if isinstance(error, UserError) and _is_provider_configuration_error_message(str(error)):
        return GenerationFailureClassification(
            error_type="provider_error",
            error_code=_PROVIDER_CONFIGURATION_ERROR_CODE,
        )
    return classify_generation_error_message(str(error))


def classify_generation_error_message(message: str) -> GenerationFailureClassification:
    if _is_provider_configuration_error_message(message):
        return GenerationFailureClassification(
            error_type="provider_error",
            error_code=_PROVIDER_CONFIGURATION_ERROR_CODE,
        )
    return GenerationFailureClassification(
        error_type="unknown_error",
        error_code=None,
    )

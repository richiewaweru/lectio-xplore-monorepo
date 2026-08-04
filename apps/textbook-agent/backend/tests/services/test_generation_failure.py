from __future__ import annotations

from pydantic_ai.exceptions import UserError

from generation.failure import (
    classify_generation_error_message,
    classify_generation_failure,
)


def test_classify_generation_error_message_for_missing_provider_env_var() -> None:
    classification = classify_generation_error_message(
        "Model spec for 'claude-sonnet-4-6' expects env var 'ANTHROPIC_API_KEY', but it is not set."
    )

    assert classification.error_type == "provider_error"
    assert classification.error_code == "provider_configuration_failed"


def test_classify_generation_failure_for_provider_user_error() -> None:
    classification = classify_generation_failure(
        UserError(
            "Set the `ANTHROPIC_API_KEY` environment variable or pass it via "
            "`AnthropicProvider(api_key=...)` to use the Anthropic provider."
        )
    )

    assert classification.error_type == "provider_error"
    assert classification.error_code == "provider_configuration_failed"


import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when a pipeline node fails after retries."""

    def __init__(self, node_name: str, reason: str) -> None:
        self.node_name = node_name
        self.reason = reason
        super().__init__(f"Pipeline node '{node_name}' failed: {reason}")


class NodeValidationError(PipelineError):
    """Raised when a node's input or output fails Pydantic validation."""

    pass


class ProviderConformanceError(Exception):
    """Raised when an LLM provider cannot return data conforming to the expected schema."""

    def __init__(self, provider_name: str, schema_name: str) -> None:
        self.provider_name = provider_name
        self.schema_name = schema_name
        super().__init__(
            f"Provider '{provider_name}' could not conform to schema '{schema_name}'"
        )


class ProviderRequestError(Exception):
    """Raised when an LLM provider rejects a request before returning usable output."""

    def __init__(self, provider_name: str, detail: str) -> None:
        self.provider_name = provider_name
        self.detail = detail
        super().__init__(f"Provider '{provider_name}' request failed: {detail}")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProviderConformanceError)
    async def handle_provider_error(
        request: Request, exc: ProviderConformanceError
    ) -> JSONResponse:
        logger.error("Provider conformance error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={
                "error": str(exc),
                "error_type": "provider_error",
                "detail": f"The LLM provider '{exc.provider_name}' could not produce a valid response for '{exc.schema_name}'.",
            },
        )

    @app.exception_handler(ProviderRequestError)
    async def handle_provider_request_error(
        request: Request, exc: ProviderRequestError
    ) -> JSONResponse:
        logger.error("Provider request error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={
                "error": str(exc),
                "error_type": "provider_error",
                "detail": exc.detail,
            },
        )

    @app.exception_handler(NodeValidationError)
    async def handle_validation_error(
        request: Request, exc: NodeValidationError
    ) -> JSONResponse:
        logger.error("Node validation error: %s", exc)
        return JSONResponse(
            status_code=422,
            content={
                "error": str(exc),
                "error_type": "validation_error",
                "detail": f"Pipeline node '{exc.node_name}' failed validation: {exc.reason}",
            },
        )

    @app.exception_handler(PipelineError)
    async def handle_pipeline_error(
        request: Request, exc: PipelineError
    ) -> JSONResponse:
        logger.error("Pipeline error: %s", exc)
        return JSONResponse(
            status_code=502,
            content={
                "error": str(exc),
                "error_type": "pipeline_error",
                "detail": f"Pipeline node '{exc.node_name}' failed: {exc.reason}",
            },
        )

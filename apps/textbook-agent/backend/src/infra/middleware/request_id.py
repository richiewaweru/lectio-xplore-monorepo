from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("http")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s -> %d",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
            },
        )
        return response

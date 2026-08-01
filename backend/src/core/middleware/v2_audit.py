from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.database.models import V2AuditEventModel
from core.database.session import async_session_factory


logger = logging.getLogger("audit.v2")
_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class V2AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method not in _MUTATION_METHODS or not request.url.path.startswith(
            "/api/v1/units"
        ):
            return response
        metadata: dict[str, Any] = {
            "query": request.url.query or None,
            "client_host": request.client.host if request.client else None,
        }
        try:
            async with async_session_factory() as session:
                session.add(
                    V2AuditEventModel(
                        actor_id=getattr(request.state, "actor_id", None),
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        request_id=getattr(request.state, "request_id", None),
                        event_metadata=metadata,
                    )
                )
                await session.commit()
        except Exception:
            logger.exception(
                "Failed to persist V2 audit event",
                extra={"path": request.url.path, "status_code": response.status_code},
            )
        return response

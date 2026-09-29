"""P13C architecture guard: zero-caller routes deleted for API/frontend
convergence must not reappear.

Superseded surfaces removed in P13C:
  * ``learn.generation.units_routes`` review/approve/retry/open-builder
    endpoints and the ``learn.generation.units_dispatch`` module they alone
    called -- superseded by ``curriculum.routes`` prepare/status plus the
    ``realizations:generate-learn``/``realizations:generate-print`` admission
    endpoints (kept, and asserted still live below).
  * ``application.builder_print.routes`` (Builder-owned ``export/pdf`` and
    ``print-preflight``) -- distinct from the live v3_studio PDF export and
    from the still-live Builder ``print-document`` endpoint.
  * ``core.routes.shares`` (public Lesson Builder share links) -- zero
    frontend or backend callers; ``LessonShareModel``/its table are
    intentionally left alone pending Phase 14 DB cleanup.

Route presence/absence is asserted via real ASGI requests rather than static
``app.routes`` introspection: this app wraps ``include_router`` with an
observability layer (``_IncludedRouter``) whose sub-routes are not visible in
a plain walk of ``app.routes``, so a static path-string check would pass
vacuously for every router-scoped endpoint. An unauthenticated request that
reaches route matching but fails a downstream dependency (auth, capability
gate, body validation) returns something other than 404/405; a request for a
path with no matching route returns 404/405 regardless of auth.
"""

from __future__ import annotations

import importlib

import pytest
from httpx import ASGITransport, AsyncClient

from app import app

RETIRED_MODULES = [
    "learn.generation.units_dispatch",
    "application.builder_print.routes",
    "application.builder_print",
    "core.routes.shares",
]

RETIRED_SYMBOLS = (
    "get_units_generation_status",
    "review_units_generation",
    "approve_units_generation",
    "retry_units_generation",
    "open_units_builder",
    "dispatch_units_generation",
    "units_dispatch_task",
    "export_builder_lesson_pdf",
    "print_preflight_builder_lesson",
    "create_share",
    "get_share",
)

NOT_FOUND = (404, 405)

# (method, path, retired) -- retired paths must 404/405; live neighbour paths
# (kept in the same modules/routers) must NOT 404/405, proving the guard
# isn't vacuously true because a whole router failed to mount.
ROUTE_CASES: list[tuple[str, str, bool]] = [
    ("GET", "/api/v1/units/u1/path/lessons/l1/generation", True),
    ("POST", "/api/v1/units/u1/path/lessons/l1/generation:review", True),
    ("POST", "/api/v1/units/u1/path/lessons/l1/generation:approve", True),
    ("POST", "/api/v1/units/u1/path/lessons/l1/generation:retry", True),
    ("POST", "/api/v1/units/u1/path/lessons/l1/generation:open-builder", True),
    ("POST", "/api/v1/builder/lessons/l1/export/pdf", True),
    ("POST", "/api/v1/builder/lessons/l1/print-preflight", True),
    ("POST", "/api/v1/shares", True),
    ("GET", "/api/v1/shares/s1", True),
    ("POST", "/api/v1/units/u1/path/lessons/l1/realizations:generate-learn", False),
    ("POST", "/api/v1/units/u1/path/lessons/l1/realizations:generate-print", False),
    ("GET", "/api/v1/builder/lessons/l1/print-document", False),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,retired", ROUTE_CASES)
async def test_route_liveness_matches_p13c_deletions(method: str, path: str, retired: bool) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.request(method, path, json={} if method == "POST" else None)

    if retired:
        assert response.status_code in NOT_FOUND, (
            f"retired route still registered: {method} {path} -> {response.status_code}"
        )
    else:
        assert response.status_code not in NOT_FOUND, (
            f"expected live route to match (non-404/405): {method} {path} -> {response.status_code}"
        )


def test_retired_modules_cannot_be_imported() -> None:
    for mod_name in RETIRED_MODULES:
        with pytest.raises(ModuleNotFoundError, match=r"No module named"):
            importlib.import_module(mod_name)


def test_units_routes_does_not_reference_retired_symbols() -> None:
    import learn.generation.units_routes as units_routes

    for symbol in RETIRED_SYMBOLS:
        assert not hasattr(units_routes, symbol), f"{symbol} should be deleted from units_routes"


def test_app_does_not_import_deleted_routers() -> None:
    import app as app_module

    for attr in ("builder_print_router", "shares_router"):
        assert not hasattr(app_module, attr), f"{attr} should be removed from app.py"

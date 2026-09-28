"""P12B architecture guard: dead whole-lesson lifecycle statuses/routes stay gone.

After P11B deleted the ordinary whole-lesson form-planning/writing executor,
``writing_sections``/``writing_blocks`` became unreachable: nothing sets them
(the only code that used to was the deleted executor), and the worker never
reclaims a stale row parked in either any more. This guard fails if:

  * ``states.LEGAL_TRANSITIONS`` gains a transition INTO ``writing_sections``
    or ``writing_blocks`` again (only read-tolerance for old DB rows may
    reference those names — see ``native_status.LEGACY_STATUSES`` — not a
    live transition target);
  * ``states.ACTIVE_STATUSES`` reclaims either status again (that would
    resurrect the worker-side reclaim/execute loop for a stage nothing can
    ever produce new content for);
  * the retired ``/chunked/{generation_id}/retry-section`` route (superseded
    end-to-end by ``POST /generations/{generation_id}/retry-native``) is
    registered on the FastAPI app again.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from print.generation.whole_lesson.states import ACTIVE_STATUSES, LEGAL_TRANSITIONS

RETIRED_STATUSES = frozenset({"writing_sections", "writing_blocks"})

RETIRED_ROUTE_PATH = "/api/v1/v3/chunked/{generation_id}/retry-section"


def test_legal_transitions_has_no_transition_into_retired_statuses() -> None:
    """No status may legally transition into writing_sections/writing_blocks."""
    violations: list[str] = []
    for source, targets in LEGAL_TRANSITIONS.items():
        hit = targets & RETIRED_STATUSES
        if hit:
            violations.append(f"{source!r} -> {sorted(hit)}")

    assert not violations, "\n".join(violations)


def test_active_statuses_no_longer_claims_retired_writing_stages() -> None:
    """The worker must never (re)claim/reclaim a row parked in a retired stage."""
    assert ACTIVE_STATUSES == frozenset({"planning_forms", "assembling"})
    assert not (ACTIVE_STATUSES & RETIRED_STATUSES)


def test_retired_statuses_have_no_outgoing_legal_transitions() -> None:
    """writing_sections/writing_blocks must not even be LEGAL_TRANSITIONS keys.

    P12B removed the transition-logic entries entirely; only
    ``native_status.LEGACY_STATUSES`` may still reference these names, for a
    read-only projection of a pre-P11B DB row.
    """
    for status in RETIRED_STATUSES:
        assert status not in LEGAL_TRANSITIONS, (
            f"{status!r} must not be a LEGAL_TRANSITIONS key any more"
        )


@pytest.mark.asyncio
async def test_retired_retry_section_route_is_not_registered() -> None:
    """The retired /chunked/{id}/retry-section route must 404, not run."""
    from app import app

    matching_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == RETIRED_ROUTE_PATH
    ]
    assert not matching_routes, (
        f"retired route still registered: {[r.path for r in matching_routes]}"
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/v3/chunked/00000000-0000-0000-0000-000000000000/retry-section",
            json={"section_id": "intro"},
        )
    assert response.status_code in (404, 405)

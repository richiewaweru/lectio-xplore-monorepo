"""Phase 02 Commit F: legacy stage2 back half disabled for new lessons."""

from __future__ import annotations

import inspect

from generation.v3_studio import router as studio_router
from v3_blueprint.planning import persistence as persistence_mod


def test_resume_stage2_no_longer_imported_by_studio_router() -> None:
    source = inspect.getsource(studio_router)
    assert "return await resume_stage2" not in source
    assert "Legacy stage2 back half is disabled" in source
    # Historical helper remains available for read-only / tooling, but is not invoked
    # from the new-generation stage2 pipeline entrypoint.
    assert hasattr(persistence_mod, "resume_stage2")

"""D2 Wave A/B: move builder routes + generation Learn seams."""

from __future__ import annotations

from pathlib import Path

SRC = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("wrote", path.relative_to(SRC))


def move_file(src: Path, dest: Path, *, transform=None) -> None:
    text = src.read_text(encoding="utf-8")
    if transform:
        text = transform(text)
    if dest.exists():
        raise SystemExit(f"dest exists: {dest}")
    write(dest, text)


def main() -> None:
    # builder routes
    def transform_builder(text: str) -> str:
        replacements = [
            ("from builder.service import", "from learn.authoring.builder.service import"),
            ("from core.auth.middleware import get_current_user", "from infra.auth.middleware import get_current_user"),
            ("from core.auth.jwt_handler import JWTHandler", "from infra.auth.jwt_handler import JWTHandler"),
            ("from core.dependencies import", "from infra.dependencies import"),
            ("from core.database.session import get_async_session", "from infra.database.session import get_async_session"),
            ("from core.rate_limit import limiter", "from infra.rate_limit import limiter"),
            ("from core.storage.gcs_image_store import GCSImageStore", "from infra.storage.gcs_image_store import GCSImageStore"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    move_file(SRC / "builder" / "routes.py", SRC / "learn" / "authoring" / "builder" / "routes.py", transform=transform_builder)
    write(
        SRC / "builder" / "routes.py",
        '''"""Compatibility shim — use learn.authoring.builder.routes.

Temporary (D2). Remove when all call sites import the learn path.
"""

from __future__ import annotations

from learn.authoring.builder.routes import *  # noqa: F401,F403
from learn.authoring.builder.routes import router  # noqa: F401

__all__ = ["router"]
''',
    )

    # contracts
    move_file(SRC / "generation" / "contracts.py", SRC / "learn" / "generation" / "contracts.py")
    write(
        SRC / "generation" / "contracts.py",
        '''"""Compatibility shim — use learn.generation.contracts.

Temporary (D2).
"""

from __future__ import annotations

from learn.generation.contracts import *  # noqa: F401,F403
''',
    )

    # pipeline_dispatch
    move_file(
        SRC / "generation" / "pipeline_dispatch.py",
        SRC / "learn" / "generation" / "pipeline_dispatch.py",
    )
    write(
        SRC / "generation" / "pipeline_dispatch.py",
        '''"""Compatibility shim — use learn.generation.pipeline_dispatch.

Temporary (D2).
"""

from __future__ import annotations

from learn.generation.pipeline_dispatch import *  # noqa: F401,F403
''',
    )

    # units_routes
    def transform_units(text: str) -> str:
        return (
            text.replace(
                "from generation.units_dispatch import",
                "from learn.generation.units_dispatch import",
            )
            .replace(
                "from builder.service import",
                "from learn.authoring.builder.service import",
            )
            .replace(
                "from planning.models import",
                "from curriculum.models import",
            )
        )

    move_file(
        SRC / "generation" / "units_routes.py",
        SRC / "learn" / "generation" / "units_routes.py",
        transform=transform_units,
    )
    write(
        SRC / "generation" / "units_routes.py",
        '''"""Compatibility shim — use learn.generation.units_routes.

Temporary (D2).
"""

from __future__ import annotations

from learn.generation.units_routes import *  # noqa: F401,F403
from learn.generation.units_routes import router  # noqa: F401

__all__ = ["router"]
''',
    )

    # Update app.py imports to canonical owners
    app = SRC / "app.py"
    app_text = app.read_text(encoding="utf-8")
    app_text2 = (
        app_text.replace(
            "from builder.routes import router as builder_router",
            "from learn.authoring.builder.routes import router as builder_router",
        ).replace(
            "from generation.units_routes import router as units_generation_router",
            "from learn.generation.units_routes import router as units_generation_router",
        )
    )
    if app_text2 != app_text:
        app.write_text(app_text2, encoding="utf-8")
        print("updated app.py")

    # application.builder_print
    bp = SRC / "application" / "builder_print" / "routes.py"
    bp_text = bp.read_text(encoding="utf-8")
    bp_text2 = bp_text.replace(
        "from builder import routes as builder_routes",
        "from learn.authoring.builder import routes as builder_routes",
    )
    if bp_text2 != bp_text:
        bp.write_text(bp_text2, encoding="utf-8")
        print("updated application/builder_print/routes.py")

    # application.unit_lesson.dispatch imports
    disp = SRC / "application" / "unit_lesson" / "dispatch.py"
    dtext = disp.read_text(encoding="utf-8")
    dtext2 = (
        dtext.replace(
            "from generation.pipeline_dispatch import",
            "from learn.generation.pipeline_dispatch import",
        ).replace(
            "from generation.contracts import",
            "from learn.generation.contracts import",
        )
    )
    if dtext2 != dtext:
        disp.write_text(dtext2, encoding="utf-8")
        print("updated application/unit_lesson/dispatch.py")

    # learn component_lectio imports of generation.contracts
    for rel in [
        "learn/generation/component_lectio/launcher.py",
        "learn/generation/component_lectio/service.py",
        "learn/generation/units_dispatch.py",
    ]:
        path = SRC / rel
        text = path.read_text(encoding="utf-8")
        new = (
            text.replace(
                "from generation.contracts import",
                "from learn.generation.contracts import",
            ).replace(
                "from generation.pipeline_dispatch import",
                "from learn.generation.pipeline_dispatch import",
            )
        )
        if new != text:
            path.write_text(new, encoding="utf-8")
            print("updated", rel)


if __name__ == "__main__":
    main()

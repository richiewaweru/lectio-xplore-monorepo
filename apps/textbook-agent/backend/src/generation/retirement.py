"""HTTP retirement contract for the removed Legacy Studio API."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, HTTPException


LEGACY_PIPELINE_RETIRED = {
    "code": "legacy_pipeline_retired",
    "message": "The Legacy Studio pipeline has been retired. Use the Units workflow.",
}


def _raise_legacy_retired() -> NoReturn:
    # Keep the response deliberately generic: retired endpoints must not read
    # or disclose historical lesson/generation data.
    raise HTTPException(status_code=410, detail=LEGACY_PIPELINE_RETIRED)


router = APIRouter(prefix="/v3", tags=["legacy-retired"])


@router.api_route(
    "",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def retire_v3_root() -> None:
    _raise_legacy_retired()


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def retire_v3_path(path: str) -> None:
    _ = path
    _raise_legacy_retired()


__all__ = ["LEGACY_PIPELINE_RETIRED", "router"]

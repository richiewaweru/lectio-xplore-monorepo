from __future__ import annotations

from fastapi import APIRouter, HTTPException

from v3_blueprint.skeletons import (
    SkeletonCatalogError,
    SkeletonPreviewRequest,
    SkeletonPreviewResponse,
    load_skeleton_catalog,
)

router = APIRouter(prefix="/api/v1", tags=["skeletons"])


@router.get("/skeletons")
def list_skeletons() -> dict[str, object]:
    catalog = load_skeleton_catalog()
    return {
        "version": catalog.version,
        "max_slots": catalog.max_slots,
        "skeletons": [catalog.skeletons[skeleton_id] for skeleton_id in catalog.skeleton_ids()],
    }


@router.get("/skeletons/{skeleton_id}")
def get_skeleton(skeleton_id: str) -> dict[str, object]:
    catalog = load_skeleton_catalog()
    skeleton = catalog.skeletons.get(skeleton_id)
    if skeleton is None:
        raise HTTPException(status_code=404, detail="Skeleton not found")
    return {"version": catalog.version, "skeleton": skeleton}


@router.post("/skeletons:preview", response_model=SkeletonPreviewResponse)
def preview_skeletons(request: SkeletonPreviewRequest) -> SkeletonPreviewResponse:
    try:
        return load_skeleton_catalog().preview(request)
    except SkeletonCatalogError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

from __future__ import annotations

from fastapi import APIRouter

from generation.block_generate_routes import block_generate_router
from generation.v3_studio.router import v3_studio_router

router = APIRouter(prefix="/api/v1", tags=["generation"])
router.include_router(v3_studio_router)
router.include_router(block_generate_router)
